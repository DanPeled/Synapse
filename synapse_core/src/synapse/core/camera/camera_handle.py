# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import queue
import threading
import time
from typing import Any, Dict, Final, List, Optional, Tuple

import numpy as np
from cscore import VideoMode
from ntcore import NetworkTable
from synapse.stypes import CameraID, PropertyMetaDict
from wpiutil import PixelFormat

from ...log import warn
from .synapse_camera import SynapseCamera


class CameraHandle:
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

        # The queue holds the capture timestamp and the INDEX of the filled
        # buffer, not a copy of the frame data. The event lets the processing
        # thread wake as soon as a frame is available instead of polling a
        # timeout, which previously added up to 20 ms of pickup jitter.
        self._frameQueue: "queue.Queue[Tuple[int, int]]" = queue.Queue(maxsize=1)
        self._frameReady = threading.Event()
        self._frameMutex = threading.Lock()

        # Buffers are leased to the consumer. The producer may only fill a
        # buffer that the consumer has returned; otherwise a fast camera can
        # overwrite the array while a pipeline is still reading it.
        self._freeBuffers: "queue.Queue[int]" = queue.Queue(maxsize=self._poolSize)
        for index in range(self._poolSize):
            self._freeBuffers.put_nowait(index)
        self._leasedIndex: Optional[int] = None
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
                    self._bufferGeneration += 1
                    self._bufferPool = [
                        np.zeros((H, W, 3), dtype=np.uint8)
                        for _ in range(self._poolSize)
                    ]
                    self._frameQueue = queue.Queue(maxsize=1)
                    self._frameReady.clear()
                    self._freeBuffers = queue.Queue(maxsize=self._poolSize)
                    for index in range(self._poolSize):
                        self._freeBuffers.put_nowait(index)
                    self._leasedIndex = None
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

    def _frameGrabberLoop(self) -> None:
        scratch: Optional[np.ndarray] = None

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

            generation = self._bufferGeneration
            try:
                index = self._freeBuffers.get_nowait()
            except queue.Empty:
                # No free buffer means the consumer is still processing the
                # previous frame. Drain the camera into a scratch buffer and
                # discard the result instead of overwriting a leased buffer.
                try:
                    if scratch is None or scratch.shape != pool[0].shape:
                        scratch = np.empty_like(pool[0])
                    timestamp, _ = self.camera.grabFrame(scratch)
                    if timestamp and timestamp > 0:
                        with self._frameMutex:
                            self._droppedFrames += 1
                            self._staleFrames += 1
                except Exception:
                    pass
                time.sleep(0.002)
                continue

            buffer = pool[index] if index < len(pool) else None
            if buffer is None:
                continue

            # IMPORTANT: no frame mutex while grabbing. CSCore's CvSink is
            # thread-safe, and holding the lock here would stall the consumer.
            try:
                (timestamp, _) = self.camera.grabFrame(buffer)
            except Exception:
                self._returnBuffer(index)
                time.sleep(0.002)
                continue

            if timestamp and timestamp > 0:
                # Keep only the newest frame. The mutex makes the queue, the
                # readiness event, and buffer ownership one atomic handoff.
                with self._frameMutex:
                    if generation != self._bufferGeneration:
                        # A video-mode change rebuilt the pool while this grab
                        # was in flight. Drop the stale frame and its index.
                        continue
                    if self._frameQueue.full():
                        try:
                            staleIndex, _ = self._frameQueue.get_nowait()
                            self._freeBuffers.put_nowait(staleIndex)
                            self._droppedFrames += 1
                            self._staleFrames += 1
                        except queue.Empty:
                            pass
                    try:
                        self._frameQueue.put_nowait((int(timestamp), index))
                        self._frameReady.set()
                        self._capturedFrames += 1
                    except queue.Full:
                        self._freeBuffers.put_nowait(index)
                        self._droppedFrames += 1
            else:
                self._returnBuffer(index)
                # small yield only on failure (prevents CPU spin)
                time.sleep(0.002)

    def _returnBuffer(self, index: int) -> None:
        try:
            self._freeBuffers.put_nowait(index)
        except queue.Full:
            pass

    def _releaseLeaseLocked(self) -> None:
        index = self._leasedIndex
        if index is not None:
            self._leasedIndex = None
            self._returnBuffer(index)

    def _waitForNextFrame(self):
        if self.camera.isConnected():
            mode = self.camera.getVideoMode()
            if mode.fps > 0:
                time.sleep(1.0 / mode.fps / 2.0)

    def grabFrame(
        self, timeout: float = 0.02
    ) -> Tuple[bool, Optional[np.ndarray], float]:
        """Wait for the newest frame and its capture-to-pickup latency in seconds.

        The returned buffer is leased until :meth:`releaseFrame` is called. The
        producer will not overwrite it in the meantime, which matters when the
        pipeline takes longer than the camera's frame period.
        """
        if not self._frameReady.wait(timeout):
            return False, None, 0.0

        try:
            with self._frameMutex:
                if not hasattr(self, "_freeBuffers"):
                    self._freeBuffers = queue.Queue(maxsize=len(self._bufferPool))
                    for index in range(len(self._bufferPool)):
                        self._freeBuffers.put_nowait(index)
                if not hasattr(self, "_leasedIndex"):
                    self._leasedIndex = None
                if not hasattr(self, "_bufferGeneration"):
                    self._bufferGeneration = 0

                try:
                    timestampUs, index = self._frameQueue.get_nowait()
                except queue.Empty:
                    self._frameReady.clear()
                    return False, None, 0.0
                if self._frameQueue.empty():
                    self._frameReady.clear()

                # A second grab without a release means the previous frame is
                # no longer needed. Reclaim it before leasing the new one.
                self._releaseLeaseLocked()
                self._leasedIndex = index
                generation = self._bufferGeneration

            pool = self._bufferPool
            if generation == self._bufferGeneration and index < len(pool):
                # cscore timestamps are monotonic microseconds. Clamp negative
                # values so a clock mismatch can never report negative latency.
                captureLatency = max(0.0, time.monotonic() - timestampUs / 1_000_000.0)
                return True, pool[index], captureLatency

            self.releaseFrame()
        except Exception:
            pass

        return False, None, 0.0

    def releaseFrame(self) -> None:
        """Return the most recently grabbed buffer to the producer."""
        if not hasattr(self, "_freeBuffers") or not hasattr(self, "_leasedIndex"):
            return
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
                "free": self._freeBuffers.qsize(),
                "pool": len(self._bufferPool),
            }

    def close(self):
        self._running = False
        self._frameReady.set()
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
