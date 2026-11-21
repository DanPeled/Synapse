# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import queue
import threading
import time
from typing import Any, Final, List, Optional, Tuple

import numpy as np
from cscore import VideoMode
from synapse.stypes import CameraID
from wpiutil import PixelFormat

from ...log import warn
from .synapse_camera import SynapseCamera


class CameraHandle:
    def __init__(self, camera: SynapseCamera, name: str, index: int) -> None:
        self.camera: SynapseCamera = camera
        self.name = name
        self.stream: str = ""
        self.cameraIndex = index

        self._videoModes: List[VideoMode] = self.camera.enumerateVideoModes()

        self._poolSize: Final[int] = 2
        self._bufferPool: List[np.ndarray] = [
            np.zeros((1920, 1080, 3), dtype=np.uint8) for _ in range(self._poolSize)
        ]

        # The queue holds the capture timestamp and the INDEX of the filled
        # buffer, not a copy of the frame data. The event lets the processing
        # thread wake as soon as a frame is available instead of polling a
        # timeout, which previously added up to 20 ms of pickup jitter.
        self._frameQueue: "queue.Queue[Tuple[int, int]]" = queue.Queue(maxsize=1)
        self._frameReady = threading.Event()
        self._frameMutex = threading.Lock()

        self._running: bool = True
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._startFrameThread()

    def setVideoMode(self, videoMode: VideoMode) -> None:
        if self._videoModes is None or len(self._videoModes) == 0:
            warn(f"No video modes on camera: {self.cameraIndex}")
            return

        pixelFormat = PixelFormat.MJPEG

        # Always select a valid mode
        mode = self._selectBestVideoMode(
            videoMode.width,
            videoMode.height,
            videoMode.fps,
            pixelFormat,
            self._videoModes,
        )

        if mode is None:
            return

        # Apply it
        try:
            self.camera.setVideoMode(
                VideoMode(
                    pixelFormat,
                    mode.width,
                    mode.height,
                    mode.fps,
                )
            )
        except Exception:
            try:
                # Try to set with exact requested values
                self.camera.setVideoMode(videoMode)
            except Exception:
                return

        H, W = mode.height, mode.width

        # Atomically rebuild buffers
        try:
            with self._lock:
                self._bufferPool = [
                    np.zeros((H, W, 3), dtype=np.uint8) for _ in range(self._poolSize)
                ]

                try:
                    with self._frameMutex:
                        with self._frameQueue.mutex:
                            self._frameQueue.queue.clear()
                        self._frameReady.clear()
                except Exception:
                    pass
        except Exception:
            return
        # Give camera a moment to start producing frames
        time.sleep(0.01)

        requested = (mode.width, mode.height, mode.fps)
        selected = (mode.width, mode.height, mode.fps)

        if requested != selected:
            warn(
                f"Using video mode {mode.width}x{mode.height}@{mode.fps} "
                f"(requested {mode.width}x{mode.height}@{mode.fps})"
            )

    def _selectBestVideoMode(
        self,
        width: int,
        height: int,
        fps: int,
        pixelFormat: PixelFormat,
        videoModes: List[VideoMode],
    ) -> Optional[VideoMode]:
        if not videoModes:
            return None

        def score(mode: VideoMode):
            area_diff = abs(mode.width * mode.height - width * height)
            fps_diff = abs(mode.fps - fps)
            exact_res = mode.width == width and mode.height == height
            exact_fmt = mode.pixelFormat == pixelFormat

            # Lower is better
            return (
                0 if exact_fmt else 1,
                0 if exact_res else 1,
                area_diff,
                fps_diff,
            )

        return min(videoModes, key=score)

    def setProperty(self, prop: str, value: Any) -> None:
        if prop == "orientation":
            return
        if prop == "resolution" and isinstance(value, str):
            resolution = value.split("x")
            width = int(resolution[0])
            height = int(resolution[1])
            self.setVideoMode(
                VideoMode(
                    PixelFormat.MJPEG,
                    width,
                    height,
                    int(self.camera.getMaxFPS()),
                )
            )
        meta = self.camera.getPropertyMeta().get(prop)
        if meta is not None:
            value = int(np.clip(value, meta["min"], meta["max"]))
            self.camera.setProperty(prop, value)

    def getProperty(self, prop: str) -> Any:
        return self.camera.getProperty(prop)

    def _startFrameThread(self) -> None:
        if not self._bufferPool:
            warn(f"Camera {self.cameraIndex}: frame thread not started (no buffers)")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._frameGrabberLoop,
            daemon=True,
            name=f"FrameGrabber-{self.cameraIndex}",
        )
        self._thread.start()

    def _frameGrabberLoop(self) -> None:
        buffer_index = 0

        while self._running:
            try:
                if not self.camera.isConnected():
                    time.sleep(0.005)
                    continue
            except Exception:
                time.sleep(0.005)
                continue

            pool = self._bufferPool
            if not pool:
                time.sleep(0.01)
                continue
            pool_size = len(pool)
            if buffer_index >= pool_size:
                buffer_index = 0

            buffer = pool[buffer_index]

            # IMPORTANT: no lock, grabFrame is thread-safe in CSCore
            try:
                (timestamp, frame) = self.camera.grabFrame(buffer)
            except Exception:
                time.sleep(0.002)
                continue

            if timestamp and timestamp > 0:
                # Keep only the newest frame. The mutex makes the queue and the
                # readiness event one atomic handoff so the consumer cannot
                # clear a wakeup for a frame it has not dequeued yet.
                try:
                    with self._frameMutex:
                        if self._frameQueue.full():
                            try:
                                self._frameQueue.get_nowait()
                            except queue.Empty:
                                pass
                        self._frameQueue.put_nowait((int(timestamp), buffer_index))
                        self._frameReady.set()
                except queue.Full:
                    pass

                # advance buffer only on successful frame
                buffer_index = (buffer_index + 1) % pool_size

            else:
                # small yield only on failure (prevents CPU spin)
                time.sleep(0.002)

    def _waitForNextFrame(self):
        if self.camera.isConnected():
            mode = self.camera.getVideoMode()
            if mode.fps > 0:
                time.sleep(1.0 / mode.fps / 2.0)

    def grabFrame(
        self, timeout: float = 0.02
    ) -> Tuple[bool, Optional[np.ndarray], float]:
        """Wait for the newest frame and its capture-to-pickup latency in seconds."""
        if not self._frameReady.wait(timeout):
            return False, None, 0.0

        try:
            with self._frameMutex:
                try:
                    timestampUs, index = self._frameQueue.get_nowait()
                except queue.Empty:
                    self._frameReady.clear()
                    return False, None, 0.0
                if self._frameQueue.empty():
                    self._frameReady.clear()

            pool = self._bufferPool
            if index < len(pool):
                # cscore timestamps are monotonic microseconds. Clamp negative
                # values so a clock mismatch can never report negative latency.
                captureLatency = max(0.0, time.monotonic() - timestampUs / 1_000_000.0)
                return True, pool[index], captureLatency
        except Exception:
            pass

        return False, None, 0.0

    def close(self):
        self._running = False
        self._frameReady.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def setIndex(self, cameraIndex: CameraID) -> None:
        self.cameraIndex = cameraIndex
        self.stream = ""
