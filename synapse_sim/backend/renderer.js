// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later

// Headless renderer used by `synapse --sim`.
//
// This page is loaded by Chrome in headless mode. It builds the same field
// scene as the interactive `synapse_sim` viewer, receives camera poses over a
// WebSocket, renders continuously, and streams the raw RGBA pixels back.
//
// The important properties for throughput are:
//   * The renderer never waits for Python. It renders the newest pose it has
//     and the camera thread consumes the newest finished frame.
//   * Pixels are read back through a ring of pixel-pack buffers, so the GPU
//     can render the next frame while the previous readback is in flight.
//   * Frames are sent as raw pixels instead of JPEG/base64. Encoding a
//     1080p JPEG costs ~30 ms per frame; the transfer costs a few ms.

import * as THREE from "three";

import { createFieldScene } from "../components/field-scene.js";

const params = new URLSearchParams(location.search);
const wsPort = params.get("ws");
// Diagnostics are opt-in because they add a WebSocket message per second and
// make the renderer log its GPU information.
const debug = params.get("debug") === "1";

// How many readbacks may be in flight. More depth tolerates longer GPU
// stalls at the cost of a little latency.
const PBO_DEPTH = 5;

// Drop frames instead of building an ever-growing WebSocket backlog. This
// bounds latency when Python consumes slower than the renderer produces.
const MAX_BUFFERED_FRAMES = 2;

const canvas = document.createElement("canvas");
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: false,
  // We read pixels in the same task as render(), so the drawing buffer does
  // not need to be preserved (preserving it costs an extra copy per frame).
  preserveDrawingBuffer: false,
  alpha: false,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;

// Helpful when diagnosing slow software rendering.
const gl = renderer.getContext();
const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
if (debug) {
  console.log(
    "SYNAPSE_GL",
    gl.getParameter(debugInfo?.UNMASKED_VENDOR_WEBGL ?? gl.VENDOR),
    gl.getParameter(debugInfo?.UNMASKED_RENDERER_WEBGL ?? gl.RENDERER),
  );
}
gl.pixelStorei(gl.PACK_ALIGNMENT, 1);

const camera = new THREE.PerspectiveCamera(70, 1, 0.01, 1000);

let scene = null;
let running = true;

// Newest spec per camera. The renderer keeps rendering these even when no new
// pose arrives, so Python can consume frames independently of render speed.
const latestSpecs = new Map();
let cursor = 0;
let frameCounter = 0;

// Readback ring.
let frameBytes = 0;
let buffers = [];
let pbos = [];
let fences = [];
let pending = [];
let droppedFrames = 0;
let renderTime = 0;
let copyTime = 0;
let sendTime = 0;
let timedFrames = 0;

let socket = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Yielding with setTimeout(0) is clamped to ~4 ms once timers are nested,
// which is a large fraction of a frame at high resolutions. A MessageChannel
// task yields to the event loop (so WebSocket messages are processed) without
// the timer clamp.
const yieldChannel = new MessageChannel();
let yieldResolve = null;
yieldChannel.port1.onmessage = () => {
  const resolve = yieldResolve;
  yieldResolve = null;
  if (resolve) {
    resolve();
  }
};

function yieldTask() {
  return new Promise((resolve) => {
    yieldResolve = resolve;
    yieldChannel.port2.postMessage(0);
  });
}

async function post(path, body) {
  const headers = body ? { "Content-Type": "text/plain" } : undefined;
  return fetch(path, { method: "POST", headers, body });
}

function applyIntrinsics(spec, width, height) {
  const intrinsics = spec.intrinsics;
  if (!intrinsics) {
    camera.aspect = width / height;
    camera.fov = Number(spec.fovY) || 70;
    camera.updateProjectionMatrix();
    return;
  }

  const { fx, fy, cx, cy } = intrinsics;
  const near = 0.01;
  const far = 1000;

  // Match the OpenCV camera matrix used by the pipeline calibration exactly.
  // Matrix4.set() takes row-major arguments. The half-pixel terms account for
  // OpenCV measuring from pixel centres while WebGL maps NDC to window edges.
  const projection = new THREE.Matrix4();
  projection.set(
    (2 * fx) / width,
    0,
    1 - (2 * cx + 1) / width,
    0,
    0,
    (2 * fy) / height,
    (2 * cy + 1) / height - 1,
    0,
    0,
    0,
    -(far + near) / (far - near),
    (-2 * far * near) / (far - near),
    0,
    0,
    -1,
    0,
  );
  camera.projectionMatrix.copy(projection);
  camera.projectionMatrixInverse.copy(projection).invert();
}

function releaseBuffers() {
  for (let i = 0; i < pbos.length; i++) {
    if (fences[i]) {
      gl.deleteSync(fences[i]);
    }
    gl.deleteBuffer(pbos[i]);
  }
  buffers = [];
  pbos = [];
  fences = [];
  pending = [];
  frameBytes = 0;
}

function ensureBuffers(width, height) {
  const bytes = width * height * 4;
  if (bytes === frameBytes) {
    return;
  }

  releaseBuffers();
  frameBytes = bytes;

  for (let i = 0; i < PBO_DEPTH; i++) {
    const pbo = gl.createBuffer();
    gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pbo);
    gl.bufferData(gl.PIXEL_PACK_BUFFER, bytes, gl.STREAM_READ);
    pbos.push(pbo);
    fences.push(null);
    buffers.push(new Uint8Array(bytes));
  }
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
}

function publish(entry) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  if (socket.bufferedAmount > frameBytes * MAX_BUFFERED_FRAMES) {
    droppedFrames++;
    return;
  }
  try {
    // Text metadata followed by the binary payload avoids copying the frame
    // just to prepend a header. WebSocket preserves message order.
    const started = performance.now();
    socket.send(`F ${entry.index} ${entry.frameSeq}`);
    socket.send(buffers[entry.slot]);
    sendTime += performance.now() - started;
  } catch {
    // The server is going away; stop trying to publish.
    running = false;
  }
}

function copyReadback(entry) {
  const started = performance.now();
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pbos[entry.slot]);
  gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, buffers[entry.slot]);
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
  copyTime += performance.now() - started;
}

function harvestReady() {
  let i = 0;
  while (i < pending.length) {
    const entry = pending[i];
    const fence = fences[entry.slot];
    if (fence === null) {
      // Defensive: a slot without a fence has no readback to wait for. Calling
      // clientWaitSync(null) hangs Chrome's WebGL implementation, so drop the
      // stale bookkeeping entry instead.
      pending.splice(i, 1);
      continue;
    }

    const status = gl.clientWaitSync(fence, 0, 0);
    if (status !== gl.ALREADY_SIGNALED && status !== gl.CONDITION_SATISFIED) {
      i++;
      continue;
    }

    gl.deleteSync(fence);
    fences[entry.slot] = null;
    copyReadback(entry);
    pending.splice(i, 1);
    publish(entry);
  }
}

function reclaimSlot() {
  // Every slot still has an outstanding readback. Reclaim the oldest one so we
  // never reuse a slot that is still referenced by the pending queue.
  const entry = pending.shift();
  if (entry === undefined) {
    // Unreachable: every outstanding fence is paired with a pending entry.
    return 0;
  }
  const fence = fences[entry.slot];
  if (fence !== null) {
    const status = gl.clientWaitSync(
      fence,
      gl.SYNC_FLUSH_COMMANDS_BIT,
      1_000_000_000,
    );
    if (status === gl.TIMEOUT_EXPIRED) {
      // The GPU didn't finish in time; block once so the buffer is valid.
      gl.finish();
    }
    gl.deleteSync(fence);
    fences[entry.slot] = null;
  }
  copyReadback(entry);
  publish(entry);
  return entry.slot;
}

function freeSlot() {
  for (let i = 0; i < PBO_DEPTH; i++) {
    if (fences[i] === null && !pending.some((entry) => entry.slot === i)) {
      return i;
    }
  }
  return reclaimSlot();
}

function renderSpec(spec) {
  const width = Math.max(1, Math.floor(Number(spec.width)));
  const height = Math.max(1, Math.floor(Number(spec.height)));

  if (width !== canvas.width || height !== canvas.height) {
    // Resizing while a readback is outstanding would invalidate its size.
    while (pending.length > 0) {
      reclaimSlot();
    }
    renderer.setSize(width, height, false);
    ensureBuffers(width, height);
  }

  camera.position.fromArray(spec.position);
  camera.quaternion.fromArray(spec.quaternion);
  applyIntrinsics(spec, width, height);
  const renderStarted = performance.now();
  renderer.render(scene, camera);
  renderTime += performance.now() - renderStarted;

  const slot = freeSlot();
  gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pbos[slot]);
  gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, 0);
  fences[slot] = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
  gl.flush();
  timedFrames++;
  pending.push({ slot, index: spec.index, frameSeq: frameCounter++ });
}

function nextSpec() {
  if (latestSpecs.size === 0) {
    return null;
  }
  const target = cursor % latestSpecs.size;
  cursor++;
  let index = 0;
  for (const spec of latestSpecs.values()) {
    if (index++ === target) {
      return spec;
    }
  }
  return null;
}

let lastStatsAt = 0;

function reportStats() {
  if (!debug || !socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  const now = performance.now();
  if (now - lastStatsAt < 1000) {
    return;
  }
  lastStatsAt = now;
  const count = Math.max(1, timedFrames);
  const stats = {
    frames: frameCounter,
    dropped: droppedFrames,
    pending: pending.length,
    buffered: socket.bufferedAmount,
    width: canvas.width,
    height: canvas.height,
    running,
    glError: gl.getError(),
    renderMs: renderTime / count,
    copyMs: copyTime / count,
    sendMs: sendTime / count,
    statsOverFrames: timedFrames,
  };
  renderTime = 0;
  copyTime = 0;
  sendTime = 0;
  timedFrames = 0;
  try {
    socket.send(`S ${JSON.stringify(stats)}`);
  } catch {
    // Diagnostics are best-effort.
  }
}

function onMessage(event) {
  if (typeof event.data !== "string") {
    return;
  }

  let message;
  try {
    message = JSON.parse(event.data);
  } catch {
    return;
  }

  if (message.type !== "specs") {
    return;
  }

  const present = new Set();
  for (const spec of message.cameras ?? []) {
    const index = Number(spec.index);
    present.add(index);

    const current = latestSpecs.get(index);
    if (!current || Number(spec.seq) > Number(current.seq)) {
      latestSpecs.set(index, spec);
    }
  }

  // Cameras removed from the simulation must stop rendering.
  for (const index of latestSpecs.keys()) {
    if (!present.has(index)) {
      latestSpecs.delete(index);
    }
  }
}

function connect() {
  if (!wsPort) {
    return Promise.resolve(null);
  }

  return new Promise((resolve) => {
    let resolved = false;
    const ws = new WebSocket(`ws://127.0.0.1:${wsPort}/`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => {
      resolved = true;
      resolve(ws);
    };
    ws.onmessage = onMessage;
    ws.onerror = () => {
      post("/api/debug", "websocket error").catch(() => {});
      if (!resolved) {
        resolved = true;
        resolve(null);
      }
    };
    ws.onclose = (event) => {
      running = false;
      post(
        "/api/debug",
        `websocket closed code=${event.code} reason=${event.reason} ` +
          `frames=${frameCounter} pending=${pending.length}`,
      ).catch(() => {});
      if (!resolved) {
        resolved = true;
        resolve(null);
      }
    };
  });
}

function backpressured() {
  return (
    socket !== null &&
    socket.readyState === WebSocket.OPEN &&
    socket.bufferedAmount > frameBytes * MAX_BUFFERED_FRAMES
  );
}

async function loop() {
  while (running) {
    harvestReady();
    reportStats();
    if (backpressured()) {
      // Python is still draining a frame; don't queue more work (or more
      // latency) than it can consume.
      await sleep(1);
      continue;
    }

    if (socket && socket.bufferedAmount > frameBytes) {
      // The previous frame is still in the browser's send queue. Rendering
      // another one now would only be dropped, wasting GPU and CPU time that
      // the network path needs, so wait for it to drain first.
      await yieldTask();
      continue;
    }

    if (pending.length >= 2) {
      // Keep at most one readback in flight while the previous frame drains
      // through the WebSocket. Deeper queues only add latency and make the
      // renderer publish bursts that the transport has to drop.
      await yieldTask();
      continue;
    }

    const spec = nextSpec();
    if (spec) {
      renderSpec(spec);
    }
    // Yield so WebSocket messages (new poses) and sends can make progress.
    if (spec) {
      await yieldTask();
    } else {
      await sleep(1);
    }
  }
}

async function main() {
  // Connect first so poses that arrive while the field loads are not lost.
  socket = await connect();
  if (wsPort && !socket) {
    throw new Error("Failed to connect to the simulation renderer socket");
  }

  const result = await createFieldScene({
    fieldUrl: "/field.glb",
    configUrl: "/apriltag-config.json",
    tagBaseUrl: "/apriltags",
  });
  scene = result.scene;
  await post("/api/ready");
  loop();
}

main().catch((error) => {
  console.error(error);
  post("/api/error", String(error?.stack || error)).catch(() => {});
});
