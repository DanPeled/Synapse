# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Final, List, Optional, Tuple

import numpy as np
from cscore import VideoMode
from ntcore import NetworkTable
from synapse.stypes import CameraID, PropertyMetaDict
from wpiutil import PixelFormat

from ...log import warn
from .synapse_camera import SynapseCamera


class CameraHandle:
    # Native camera connection checks are cheap individually but scale with
    # camera count. Re-checking every 50 ms keeps disconnect handling responsive
    # without adding a native call to every captured frame.
    _CONNECTION_CHECK_INTERVAL: Final[float] = 0.05

    def __init__(self, camera: SynapseCamera, name: str, index: int) -> None:
        self.camera: SynapseCamera = camera
        self.name = name
        self.stream: str = ""
        self.cameraIndex = index

        # Resolved lazily by ``getCameraTable`` and refreshed whenever the
        # camera is renamed so NetworkTables paths never go stale.
        self.ntTable: Optional[NetworkTable] = None
        self.ntTableName: str = ""

        # Video modes and property metadata are stable for the lifetime of a
        # camera. Cache them once here instead of re-querying the camera every
        # time a pipeline is bound to it.
        self._videoModes: List[VideoMode] = list(
            self.camera.enumerateVideoModes() or []
        )
        self._propertyMeta: PropertyMetaDict = self.camera.getPropertyMeta()

        try:
            self._activeVideoMode: Optional[VideoMode] = self.camera.getVideoMode()
        except Exception:
            self._activeVideoMode = None

        initialWidth, initialHeight = 1920, 1080
        if self._activeVideoMode is not None:
            try:
                if self._activeVideoMode.width > 0 and self._activeVideoMode.height > 0:
                    initialWidth = int(self._activeVideoMode.width)
                    initialHeight = int(self._activeVideoMode.height)
            except (TypeError, ValueError):
                pass

        # One buffer can be queued, one leased to the pipeline, and one free for
        # the capture thread. A two-buffer pool stalls as soon as the pipeline
        # is still reading while the next frame is already available.
        self._poolSize: Final[int] = 3
        self._bufferPool: List[np.ndarray] = [
            np.zeros((initialHeight, initialWidth, 3), dtype=np.uint8)
            for _ in range(self._poolSize)
        ]

        # The frame lane and the free list are guarded by one lock. Conditions
        # replace level-triggered events so a wakeup cannot be cleared between
        # a timeout and a state change. Entries carry a buffer generation so a
        # late return from an old video mode is discarded instead of making a
        # new-mode buffer appear free while it is leased.
        self._frameMutex = threading.Lock()
        self._frameCondition = threading.Condition(self._frameMutex)
        self._bufferCondition = threading.Condition(self._frameMutex)

        # Frame entries are (timestamp microseconds, generation, buffer index).
        self._frameQueue: "Deque[Tuple[int, int, int]]" = deque(maxlen=1)
        self._freeBuffers: "Deque[Tuple[int, int]]" = deque()
        for index in range(self._poolSize):
            self._freeBuffers.append((0, index))
        self._leasedIndex: Optional[int] = None
        self._leasedGeneration: Optional[int] = None
        self._bufferGeneration = 0
        self._capturedFrames = 0
        self._droppedFrames = 0
        self._staleFrames = 0

        self._running: bool = True
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._startFrameThread()

    def setVideoMode(self, videoMode: VideoMode) -> None:
        if not self._videoModes:
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

        effectiveMode = VideoMode(pixelFormat, mode.width, mode.height, mode.fps)

        # Applying a video mode can rebuild frame buffers and stall the camera.
        # Avoid both when the camera is already in the requested mode.
        if self._isActiveVideoMode(effectiveMode):
            return

        # Apply it
        try:
            self.camera.setVideoMode(effectiveMode)
        except Exception:
            try:
                # Try to set with exact requested values
                self.camera.setVideoMode(videoMode)
            except Exception:
                return
            effectiveMode = VideoMode(
                pixelFormat, videoMode.width, videoMode.height, videoMode.fps
            )

        H, W = effectiveMode.height, effectiveMode.width

        # Atomically rebuild buffers. The generation counter invalidates any
        # frame already in flight so the consumer cannot use a stale buffer.
        try:
            with self._lock:
                with self._frameMutex:
                    generation = self._bufferGeneration + 1
                    self._bufferGeneration = generation
                    self._bufferPool = [
                        np.zeros((H, W, 3), dtype=np.uint8)
                        for _ in range(self._poolSize)
                    ]
                    self._frameQueue.clear()
                    self._freeBuffers.clear()
                    for index in range(self._poolSize):
                        self._freeBuffers.append((generation, index))
                    self._leasedIndex = None
                    self._leasedGeneration = None
                    self._frameCondition.notify_all()
                    self._bufferCondition.notify_all()
        except Exception:
            return

        self._activeVideoMode = effectiveMode

        # Give camera a moment to start producing frames
        time.sleep(0.01)

    def _isActiveVideoMode(self, mode: VideoMode) -> bool:
        active = self._activeVideoMode
        if active is None:
            return False
        try:
            return (
                active.width == mode.width
                and active.height == mode.height
                and active.fps == mode.fps
                and active.pixelFormat == mode.pixelFormat
            )
        except Exception:
            return False

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
        if prop == "resolution":
            if not isinstance(value, str):
                return
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
            return

        meta = self._propertyMeta.get(prop)
        if meta is None:
            return

        value = int(np.clip(value, meta["min"], meta["max"]))
        try:
            if self.camera.getProperty(prop) == value:
                return
        except Exception:
            pass
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

    def _acquireBufferLocked(self) -> Optional[Tuple[int, int, List[np.ndarray]]]:
        """Take a valid free buffer while ``_frameMutex`` is held."""
        while self._freeBuffers:
            generation, index = self._freeBuffers.popleft()
            if generation == self._bufferGeneration and 0 <= index < len(
                self._bufferPool
            ):
                return generation, index, self._bufferPool
        return None

    def _returnBufferLocked(self, generation: int, index: int) -> None:
        """Return a lease while ``_frameMutex`` is held, rejecting stale modes."""
        if generation != self._bufferGeneration:
            return
        if not 0 <= index < len(self._bufferPool):
            return
        self._freeBuffers.append((generation, index))
        self._bufferCondition.notify()

    def _frameGrabberLoop(self) -> None:
        scratch: Optional[np.ndarray] = None
        lastDrain = 0.0
        lastConnectionCheck = 0.0
        connected = False

        while self._running:
            now = time.monotonic()
            if now - lastConnectionCheck >= self._CONNECTION_CHECK_INTERVAL:
                lastConnectionCheck = now
                try:
                    connected = bool(self.camera.isConnected())
                except Exception:
                    connected = False

            if not connected:
                time.sleep(0.005)
                continue

            acquired: Optional[Tuple[int, int, List[np.ndarray]]] = None
            with self._bufferCondition:
                acquired = self._acquireBufferLocked()
                if acquired is None:
                    # Wait for a lease to return. The predicate is rechecked
                    # after waking, so a return cannot be missed between a
                    # timeout and an event clear.
                    self._bufferCondition.wait(0.005)
                    shouldDrain = time.monotonic() - lastDrain >= 0.02
                    drainPool = self._bufferPool if shouldDrain else None
                else:
                    shouldDrain = False
                    drainPool = None

            if acquired is None:
                # A periodic scratch drain keeps the sink moving and the drop
                # counters honest if the pipeline stays behind for a long time.
                if shouldDrain and drainPool:
                    lastDrain = time.monotonic()
                    try:
                        if scratch is None or scratch.shape != drainPool[0].shape:
                            scratch = np.empty_like(drainPool[0])
                        timestamp, _ = self.camera.grabFrame(scratch)
                        if timestamp and timestamp > 0:
                            with self._frameMutex:
                                self._droppedFrames += 1
                                self._staleFrames += 1
                    except Exception:
                        pass
                continue

            generation, index, pool = acquired
            buffer = pool[index] if index < len(pool) else None
            if buffer is None:
                with self._frameMutex:
                    self._returnBufferLocked(generation, index)
                continue

            # IMPORTANT: no frame mutex while grabbing. CSCore's CvSink is
            # thread-safe, and holding the lock here would stall the consumer.
            try:
                timestamp, _ = self.camera.grabFrame(buffer)
            except Exception:
                with self._frameMutex:
                    self._returnBufferLocked(generation, index)
                time.sleep(0.002)
                continue

            if not (timestamp and timestamp > 0):
                with self._frameMutex:
                    self._returnBufferLocked(generation, index)
                # small yield only on failure (prevents CPU spin)
                time.sleep(0.002)
                continue

            with self._frameMutex:
                if generation != self._bufferGeneration:
                    # A video-mode change rebuilt the pool while this grab was
                    # in flight. The tagged return is discarded so the new pool
                    # cannot receive a stale index.
                    self._returnBufferLocked(generation, index)
                    self._droppedFrames += 1
                    continue

                if self._frameQueue:
                    _, staleGeneration, staleIndex = self._frameQueue.popleft()
                    self._returnBufferLocked(staleGeneration, staleIndex)
                    self._droppedFrames += 1
                    self._staleFrames += 1

                self._frameQueue.append((int(timestamp), generation, index))
                self._capturedFrames += 1
                self._frameCondition.notify()

    def _releaseLeaseLocked(self) -> None:
        index = self._leasedIndex
        generation = self._leasedGeneration
        self._leasedIndex = None
        self._leasedGeneration = None
        if index is not None and generation is not None:
            self._returnBufferLocked(generation, index)

    def grabFrame(
        self, timeout: float = 0.02
    ) -> Tuple[bool, Optional[np.ndarray], float]:
        """Wait for the newest frame and its capture-to-pickup latency in seconds.

        The returned buffer is leased until :meth:`releaseFrame` is called. The
        producer will not overwrite it in the meantime, which matters when the
        pipeline takes longer than the camera's frame period.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        with self._frameCondition:
            while not self._frameQueue and self._running:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None, 0.0
                self._frameCondition.wait(remaining)

            if not self._frameQueue:
                return False, None, 0.0

            timestampUs, frameGeneration, index = self._frameQueue.popleft()

            # A second grab without a release means the previous frame is no
            # longer needed. Reclaim it before leasing the new one.
            self._releaseLeaseLocked()
            self._leasedIndex = index
            self._leasedGeneration = frameGeneration
            generation = self._bufferGeneration
            pool = self._bufferPool

        if frameGeneration == generation and 0 <= index < len(pool):
            # cscore timestamps are monotonic microseconds. Clamp negative
            # values so a clock mismatch can never report negative latency.
            captureLatency = max(0.0, time.monotonic() - timestampUs / 1_000_000.0)
            return True, pool[index], captureLatency

        self.releaseFrame()
        return False, None, 0.0

    def releaseFrame(self) -> None:
        """Return the most recently grabbed buffer to the producer."""
        with self._frameMutex:
            self._releaseLeaseLocked()

    def getCaptureStats(self) -> Dict[str, int]:
        """Return counters useful for diagnosing multi-camera capture drops."""
        if not hasattr(self, "_freeBuffers"):
            return {"captured": 0, "dropped": 0, "stale": 0, "free": 0, "pool": 0}
        with self._frameMutex:
            return {
                "captured": getattr(self, "_capturedFrames", 0),
                "dropped": getattr(self, "_droppedFrames", 0),
                "stale": getattr(self, "_staleFrames", 0),
                "free": len(self._freeBuffers),
                "pool": len(self._bufferPool),
            }

    def resetCaptureStats(self) -> None:
        """Zero capture counters without disturbing buffer ownership."""
        if not hasattr(self, "_freeBuffers"):
            return
        with self._frameMutex:
            self._capturedFrames = 0
            self._droppedFrames = 0
            self._staleFrames = 0

    def close(self):
        with self._frameMutex:
            self._running = False
            self._frameCondition.notify_all()
            self._bufferCondition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self.releaseFrame()

    def setIndex(self, cameraIndex: CameraID) -> None:
        self.cameraIndex = cameraIndex
        self.stream = ""

    def invalidateNtTable(self) -> None:
        """Forget the cached table so the next lookup uses the current name."""
        self.ntTable = None
        self.ntTableName = ""
