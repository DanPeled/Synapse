# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Runs the SynapseSim Three.js field renderer in headless Chrome.

The simulated camera needs the same 3D field and AprilTags that the
interactive ``synapse_sim`` viewer shows. Rather than re-implementing the field
in Python, this module bundles the viewer's Three.js scene into a small page,
serves it from a local HTTP server, and drives it from Chrome's headless mode.

``SimCamera`` publishes the camera pose to the server as a *spec* and waits for
the browser to POST back a rendered JPEG. The camera therefore stays behind the
normal ``SynapseCamera`` interface and pipelines never learn that the frames
were rendered instead of captured.
"""

from __future__ import annotations

import atexit
import base64
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from synapse.log import warn

#: Directory containing the committed viewer bundle and field assets.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

#: How long to wait for the browser to finish loading the field before giving
#: up. The field model is ~18 MB, so the first load can take a few seconds.
STARTUP_TIMEOUT = 60.0

#: How long a camera waits for a rendered frame before reporting no signal.
FRAME_TIMEOUT = 5.0

_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".wasm": "application/wasm",
}


def _isChromePath(path: str) -> bool:
    return bool(path) and Path(path).is_file()


def findChrome() -> Optional[str]:
    """Returns the path to a Chromium-based browser, if one is installed."""
    configured = os.environ.get("SYNAPSE_CHROME") or os.environ.get("CHROME_PATH")
    if configured and _isChromePath(configured):
        return configured

    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ):
        path = shutil.which(name)
        if path:
            return path

    # Common macOS and Windows install locations.
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if _isChromePath(candidate):
            return candidate
    return None


class SimulationViewer:
    """Local render server and headless-browser lifecycle."""

    def __init__(self, assetsDir: Optional[Path] = None) -> None:
        self._assetsDir = Path(assetsDir) if assetsDir else ASSETS_DIR

        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._specs: Dict[int, Dict[str, Any]] = {}
        self._frames: Dict[int, Tuple[int, bytes]] = {}
        self._nextSeq = 0

        self._ready = threading.Event()
        self._error: Optional[str] = None

        self._started = False
        self._startLock = threading.Lock()
        self._closed = False
        self._server: Optional[ThreadingHTTPServer] = None
        self._serverThread: Optional[threading.Thread] = None
        self._browser: Optional[subprocess.Popen] = None
        self._browserLog = None
        self._userDataDir: Optional[tempfile.TemporaryDirectory[str]] = None
        self._url: Optional[str] = None

    # ------------------------------------------------------------------
    # Camera specs and frames
    # ------------------------------------------------------------------

    def setSpec(self, index: int, spec: Dict[str, Any]) -> int:
        """Publishes the current camera spec and returns its sequence number."""
        with self._condition:
            seq = self._nextSeq
            self._nextSeq += 1
            value = dict(spec)
            value["index"] = int(index)
            value["seq"] = seq
            self._specs[int(index)] = value
            self._condition.notify_all()
            return seq

    def removeSpec(self, index: int) -> None:
        with self._condition:
            self._specs.pop(int(index), None)
            self._frames.pop(int(index), None)
            self._condition.notify_all()

    def specs(self) -> Iterable[Dict[str, Any]]:
        with self._lock:
            return [dict(spec) for spec in self._specs.values()]

    def _storeFrame(self, index: int, seq: int, data: bytes) -> None:
        with self._condition:
            current = self._frames.get(int(index))
            if current is None or seq > current[0]:
                self._frames[int(index)] = (int(seq), data)
            self._condition.notify_all()

    def waitForFrame(
        self,
        index: int,
        seq: int,
        timeout: float = FRAME_TIMEOUT,
    ) -> bytes:
        """Waits until a frame rendered for ``seq`` (or newer) is available."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                self._raiseIfFailed()
                latest = self._frames.get(int(index))
                if latest is not None and latest[0] >= seq:
                    return latest[1]
                if latest is not None and self._closed:
                    return latest[1]

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if latest is not None:
                        # The renderer may be slower than expected; a slightly
                        # stale frame is better than dropping the camera.
                        return latest[1]
                    raise TimeoutError(
                        "Timed out waiting for the simulated camera renderer"
                    )

                self._condition.wait(remaining)

    def _raiseIfFailed(self) -> None:
        self._checkBrowser()
        if self._error is not None:
            raise RuntimeError(self._error)
        if self._closed:
            raise RuntimeError("Simulation renderer is closed")

    # ------------------------------------------------------------------
    # Server / browser lifecycle
    # ------------------------------------------------------------------

    def ensureStarted(self, timeout: float = STARTUP_TIMEOUT) -> None:
        """Starts the HTTP server and headless browser once."""
        with self._startLock:
            if not self._started:
                assetsDir = self._assetsDir
                index = assetsDir / "index.html"
                bundle = assetsDir / "viewer.bundle.js"
                if not index.is_file() or not bundle.is_file():
                    raise RuntimeError(
                        "Simulation viewer assets are missing. Build them with "
                        "`npm run build:headless` in synapse_sim."
                    )

                self._startServer()
                try:
                    self._startBrowser()
                except Exception:
                    self._shutdownServer()
                    raise
                self._started = True

        if not self._ready.wait(timeout):
            self._raiseIfFailed()
            raise TimeoutError(
                "Timed out waiting for the simulated field renderer to load"
            )
        self._raiseIfFailed()

    def _startServer(self) -> None:
        class Handler(_ViewerRequestHandler):
            pass

        Handler.viewer = self
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server.viewer = self  # type: ignore[attr-defined]
        self._server = server

        thread = threading.Thread(
            target=server.serve_forever,
            name="sim-viewer-http",
            daemon=True,
        )
        thread.start()
        self._serverThread = thread

        port = server.server_address[1]
        self._url = f"http://127.0.0.1:{port}/index.html"

    def _startBrowser(self) -> None:
        chrome = findChrome()
        if chrome is None:
            raise RuntimeError(
                "Simulation requires Google Chrome or Chromium, but no browser "
                "was found. Install one or set SYNAPSE_CHROME to its path."
            )

        self._userDataDir = tempfile.TemporaryDirectory(prefix="synapse-sim-")
        self._browserLog = tempfile.TemporaryFile(mode="w+b")

        # Prefer the GPU-backed Vulkan backend, but allow headless CI or
        # machines without a Vulkan driver to force SwiftShader.
        angleBackend = os.environ.get("SYNAPSE_SIM_ANGLE", "vulkan").strip()
        angleBackend = angleBackend or "vulkan"

        args = [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--no-first-run",
            "--no-default-browser-check",
            "--mute-audio",
            "--hide-scrollbars",
            "--window-size=1920,1080",
            "--enable-unsafe-swiftshader",
            "--use-gl=angle",
            f"--use-angle={angleBackend}",
            "--ignore-gpu-blocklist",
            "--enable-gpu",
            f"--user-data-dir={self._userDataDir.name}",
            "--allow-insecure-localhost",
            self._url or "about:blank",
        ]

        try:
            self._browser = subprocess.Popen(
                args,
                stdout=self._browserLog,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            raise RuntimeError(
                f"Failed to start the simulation browser {chrome}: {error}"
            ) from error

    def _browserOutput(self) -> str:
        if self._browserLog is None:
            return ""
        try:
            self._browserLog.flush()
            self._browserLog.seek(0)
            data = self._browserLog.read()
            return data.decode("utf-8", "replace")[-4000:]
        except Exception:
            return ""

    def _shutdownServer(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._startLock:
            with self._condition:
                if self._closed:
                    return
                self._closed = True
                self._condition.notify_all()

            browser = self._browser
            self._browser = None
            if browser is not None and browser.poll() is None:
                try:
                    browser.terminate()
                    browser.wait(timeout=5)
                except Exception:
                    try:
                        browser.kill()
                    except Exception:
                        pass

            self._shutdownServer()

            if self._browserLog is not None:
                try:
                    self._browserLog.close()
                except Exception:
                    pass
                self._browserLog = None

            if self._userDataDir is not None:
                try:
                    self._userDataDir.cleanup()
                except Exception:
                    pass
                self._userDataDir = None

    # ------------------------------------------------------------------
    # Request callbacks
    # ------------------------------------------------------------------

    def _onReady(self) -> None:
        self._ready.set()

    def _onError(self, message: str) -> None:
        with self._condition:
            if self._error is None:
                self._error = f"Simulated camera renderer failed: {message}"
            self._condition.notify_all()
        self._ready.set()

    def _onFrame(self, index: int, seq: int, body: bytes) -> None:
        try:
            data = base64.b64decode(body, validate=False)
        except Exception as error:
            warn(f"Simulated camera sent an invalid frame: {error}")
            return
        if data:
            self._storeFrame(index, seq, data)

    def _checkBrowser(self) -> None:
        browser = self._browser
        if browser is not None and browser.poll() is not None:
            output = self._browserOutput()
            self._onError(
                f"browser exited with code {browser.returncode}\n{output}".strip()
            )


class _ViewerRequestHandler(BaseHTTPRequestHandler):
    """Serves the viewer bundle and receives rendered frames."""

    viewer: SimulationViewer
    protocol_version = "HTTP/1.1"

    # Keep the Synapse log free of an access line per asset request.
    def log_message(self, format: str, *args: Any) -> None:
        return

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/specs":
            self._sendJson({"cameras": list(self.viewer.specs())})
            return

        if path in ("/", "/index.html"):
            self._sendFile(self.viewer._assetsDir / "index.html")
            return

        relative = path.lstrip("/")
        target = (self.viewer._assetsDir / relative).resolve()
        try:
            target.relative_to(self.viewer._assetsDir.resolve())
        except ValueError:
            self._sendError(403, "Forbidden")
            return

        self._sendFile(target)

    def _sendFile(self, target: Path) -> None:
        if not target.is_file():
            self._sendError(404, "Not found")
            return

        try:
            data = target.read_bytes()
        except OSError as error:
            self._sendError(500, str(error))
            return

        contentType = _MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", contentType)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _sendJson(self, value: Any) -> None:
        data = json.dumps(value).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _sendError(self, status: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------

    def _readBody(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        body = self._readBody()

        if path == "/api/ready":
            self.viewer._onReady()
            self._sendJson({"ok": True})
            return

        if path == "/api/error":
            self.viewer._onError(body.decode("utf-8", "replace"))
            self._sendJson({"ok": True})
            return

        if path.startswith("/api/frame/"):
            try:
                index = int(path.rsplit("/", 1)[-1])
                seq = int(parse_qs(parsed.query).get("seq", ["0"])[0])
            except ValueError:
                self._sendError(400, "Invalid camera index or sequence")
                return
            self.viewer._onFrame(index, seq, body)
            self._sendJson({"ok": True})
            return

        self._sendError(404, "Not found")


_VIEWER: Optional[SimulationViewer] = None
_VIEWER_LOCK = threading.Lock()


def getViewer() -> SimulationViewer:
    """Returns the process-wide simulation viewer."""
    global _VIEWER
    with _VIEWER_LOCK:
        if _VIEWER is None:
            _VIEWER = SimulationViewer()
            atexit.register(_shutdownViewer)
        return _VIEWER


def _shutdownViewer() -> None:
    global _VIEWER
    with _VIEWER_LOCK:
        viewer = _VIEWER
        _VIEWER = None
    if viewer is not None:
        viewer.close()
