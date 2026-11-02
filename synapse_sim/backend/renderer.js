// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later

// Headless renderer used by `synapse --sim`.
//
// This page is loaded by Chrome in headless mode. It builds the same field
// scene as the interactive `synapse_sim` viewer, polls the Synapse simulation
// server for camera poses, renders each camera, and posts the JPEG frames back
// to the server. `SimCamera` consumes those frames through the normal camera
// path.

import * as THREE from "three";

import { createFieldScene } from "../components/field-scene.js";

const MAX_FPS = 30;

const canvas = document.createElement("canvas");
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  // Required for canvas.toDataURL() after rendering.
  preserveDrawingBuffer: true,
});
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;

// Helpful when diagnosing slow software rendering.
const gl = renderer.getContext();
const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
console.log(
  "SYNAPSE_GL",
  gl.getParameter(debugInfo?.UNMASKED_VENDOR_WEBGL ?? gl.VENDOR),
  gl.getParameter(debugInfo?.UNMASKED_RENDERER_WEBGL ?? gl.RENDERER),
);

const camera = new THREE.PerspectiveCamera(70, 1, 0.01, 1000);
const inFlight = new Set();
const lastRenderedSeq = new Map();

let scene = null;
let lastFrameTime = 0;

async function post(path, body) {
  const headers = body ? { "Content-Type": "text/plain" } : undefined;
  return fetch(path, {
    method: "POST",
    headers,
    body,
  });
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

function renderCamera(spec) {
  if (!scene || inFlight.has(spec.index)) {
    return;
  }

  if ((lastRenderedSeq.get(spec.index) ?? -1) >= spec.seq) {
    return;
  }
  lastRenderedSeq.set(spec.index, spec.seq);

  const width = Math.max(1, Math.floor(Number(spec.width)));
  const height = Math.max(1, Math.floor(Number(spec.height)));

  renderer.setSize(width, height, false);
  camera.position.fromArray(spec.position);
  camera.quaternion.fromArray(spec.quaternion);
  applyIntrinsics(spec, width, height);
  renderer.render(scene, camera);

  // toDataURL copies the drawing buffer synchronously, so rendering another
  // camera or resizing the canvas immediately afterwards is safe.
  const data = canvas.toDataURL("image/jpeg", 0.9).split(",")[1];

  inFlight.add(spec.index);
  post(`/api/frame/${spec.index}?seq=${spec.seq}`, data)
    .catch((error) => console.error("Failed to publish simulated frame", error))
    .finally(() => inFlight.delete(spec.index));
}

let stopped = false;

async function tick() {
  if (stopped) {
    return;
  }

  const now = performance.now();
  if (scene && now - lastFrameTime >= 1000 / MAX_FPS) {
    lastFrameTime = now;
    try {
      const response = await fetch("/api/specs", { cache: "no-store" });
      if (response.ok) {
        const { cameras = [] } = await response.json();
        for (const spec of cameras) {
          renderCamera(spec);
        }
      }
    } catch (error) {
      // The server disappears when Synapse shuts down; stop polling then.
      if (error instanceof TypeError) {
        stopped = true;
        return;
      }
      console.error("Failed to read simulated camera specs", error);
    }
  }

  // Headless Chrome may throttle requestAnimationFrame when the page is not
  // visible, so drive the loop from a timer instead.
  setTimeout(tick, Math.max(1, 1000 / MAX_FPS - (performance.now() - now)));
}

async function main() {
  const result = await createFieldScene({
    fieldUrl: "/field.glb",
    configUrl: "/apriltag-config.json",
    tagBaseUrl: "/apriltags",
  });
  scene = result.scene;
  await post("/api/ready");
  tick();
}

main().catch((error) => {
  console.error(error);
  post("/api/error", String(error?.stack || error)).catch(() => {});
});
