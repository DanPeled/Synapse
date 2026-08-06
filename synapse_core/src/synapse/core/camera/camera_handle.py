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

from ...log import warn
from .synapse_camera import SynapseCamera


class CameraHandle:
    def __init__(self, camera: SynapseCamera, name: str, index: int) -> None:
        self.camera: SynapseCamera = camera
        self.name = name
        self.stream: str = ""
        self.cameraIndex = index

        self._videoModes = self.camera.enumerateVideoModes()

        self._videoModes: List[VideoMode] = []
        self._validVideoModes: List[VideoMode] = []

        self._poolSize: Final[int] = 2
        self._bufferPool: List[np.ndarray] = []

        # Queue now holds the INDEX of the filled buffer, not a copy of the frame data
        # Tuple[bool, Optional[int]]: (hasFrame, buffer_index)
        self._frameQueue: queue.Queue[Tuple[bool, Optional[int]]] = queue.Queue(
            maxsize=1
        )
        # --- END FIX ---

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def setVideoMode(self, videoMode: VideoMode) -> None:
        if self._videoModes is None or len(self._videoModes) == 0:
            warn(f"No video modes on camera: {self.cameraIndex}")
            return

        pixelFormat = VideoMode.PixelFormat.kMJPEG

        # Always select a valid mode
        mode = self._selectBestVideoMode(
            videoMode.width,
            videoMode.height,
            videoMode.fps,
            pixelFormat,
            self._videoModes,
        )

        assert mode is not None

        # Apply it
        self.camera.setVideoMode(
            VideoMode(
                pixelFormat,
                mode.width,
                mode.height,
                mode.fps,
            )
        )

        H, W = mode.height, mode.width

        # Atomically rebuild buffers
        with self._lock:
            self._bufferPool = [
                np.zeros((H, W, 3), dtype=np.uint8) for _ in range(self._poolSize)
            ]

            with self._frameQueue.mutex:
                self._frameQueue.queue.clear()

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
        pixelFormat: VideoMode.PixelFormat,
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
                    VideoMode.PixelFormat.kMJPEG,
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
        if self._running:
            return

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
        # Wait until camera connects
        while self._running and not self.camera.isConnected():
            time.sleep(0.05)

        buffer_index = 0
        pool_size = len(self._bufferPool)

        while self._running:
            if not self._bufferPool:
                time.sleep(0.05)
                continue

            buffer = self._bufferPool[buffer_index]

            # IMPORTANT: no lock, grabFrame is thread-safe in CSCore
            (timestamp, frame) = self.camera.grabFrame(buffer)

            if timestamp > 0:
                # If queue is full, drop oldest frame
                if self._frameQueue.full():
                    try:
                        self._frameQueue.get_nowait()
                    except queue.Empty:
                        pass

                self._frameQueue.put_nowait((True, buffer_index))

                # advance buffer only on successful frame
                buffer_index = (buffer_index + 1) % pool_size

            else:
                # small yield only on failure (prevents CPU spin)
                time.sleep(0.001)

    def _waitForNextFrame(self):
        if self.camera.isConnected():
            mode = self.camera.getVideoMode()
            if mode.fps > 0:
                time.sleep(1.0 / mode.fps / 2.0)

    def grabFrame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            try:
                hasFrame, index = self._frameQueue.get(timeout=0.1)
                if hasFrame and index is not None and index < len(self._bufferPool):
                    return True, self._bufferPool[index]
            except queue.Empty:
                pass

        return False, None

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def setIndex(self, cameraIndex: CameraID) -> None:
        self.cameraIndex = cameraIndex
        self.stream = ""
