import queue
import threading
import time
from typing import Dict, Final, List, Optional, Tuple, Union

import numpy as np
from cscore import (CameraServer, CvSink, UsbCamera, VideoCamera, VideoMode,
                    VideoProperty, VideoSource)
from synapse.log import warn

from ...stypes import CameraID, PropertyMetaDict, Resolution, Size
from ..camera_factory import SynapseCamera


class CsCoreCamera(SynapseCamera):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.camera: VideoCamera
        self.sink: CvSink
        self.propertyMeta: PropertyMetaDict = {}
        self._properties: Dict[str, VideoProperty] = {}
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

    def getProperties(self) -> List:
        return list(self._properties.values())

    @classmethod
    def create(
        cls,
        *_,
        path: Union[str, int],
        name: str = "",
        index: CameraID,
    ) -> "CsCoreCamera":
        inst = CsCoreCamera(name)

        if isinstance(path, int):
            inst.camera = UsbCamera(f"USB Camera {index}", path)
        elif isinstance(path, str):
            inst.camera = UsbCamera(f"USB Camera {index}", path)

        inst.sink = CameraServer.getVideo(inst.camera)

        # Cache properties and metadata
        props = inst.camera.enumerateProperties()
        inst._properties = {prop.getName(): prop for prop in props}
        inst.propertyMeta = {
            name: {
                "min": prop.getMin(),
                "max": prop.getMax(),
                "default": prop.getDefault(),
            }
            for name, prop in inst._properties.items()
        }

        # Cache video modes and valid resolutions
        inst._videoModes = inst.camera.enumerateVideoModes()
        inst.camera.setExposureManual(1)
        inst._validVideoModes = [mode for mode in inst._videoModes]

        # # This will call setVideoMode, which now initializes the buffer pool.
        inst.setVideoMode(100, 1920, 1080)

        # Start background frame grabbing thread
        inst._startFrameThread()

        return inst

    def getPropertyMeta(self) -> Optional[PropertyMetaDict]:
        return self.propertyMeta

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
        while self._running and not self.isConnected():
            time.sleep(0.05)

        buffer_index = 0
        pool_size = len(self._bufferPool)

        while self._running:
            if not self._bufferPool:
                time.sleep(0.05)
                continue

            buffer = self._bufferPool[buffer_index]

            # IMPORTANT: no lock, grabFrame is thread-safe in CSCore
            (timestamp, frame) = self.sink.grabFrame(buffer)

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
        if self.isConnected():
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

    def isConnected(self) -> bool:
        return self.camera.isConnected()

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        # Properly close camera connection
        self.camera.setConnectionStrategy(
            VideoSource.ConnectionStrategy.kConnectionForceClose
        )

    def setProperty(self, prop: str, value: Union[int, float, str]) -> None:
        if prop == "orientation":
            return
        if prop == "resolution" and isinstance(value, str):
            resolution = value.split("x")
            width = int(resolution[0])
            height = int(resolution[1])
            self.setVideoMode(int(self.getMaxFPS()), width, height)
        elif prop in self._properties:
            meta = self.propertyMeta[prop]
            value = int(np.clip(value, meta["min"], meta["max"]))
            self._properties[prop].set(value)

    def getProperty(self, prop: str) -> Union[int, float, None]:
        if prop in self._properties:
            return self._properties[prop].get()
        return None

    def _selectBestVideoMode(
        self,
        width: int,
        height: int,
        fps: int,
        pixelFormat: VideoMode.PixelFormat,
    ) -> Optional[VideoMode]:
        if not self._videoModes:
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

        return min(self._videoModes, key=score)

    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        if self._videoModes is None or len(self._videoModes) == 0:
            warn(f"No video modes on camera: {self.cameraIndex}")
            return

        pixelFormat = VideoMode.PixelFormat.kMJPEG

        # Always select a valid mode
        mode = self._selectBestVideoMode(width, height, fps, pixelFormat)

        assert mode is not None

        # Apply it
        self.camera.setVideoMode(
            width=mode.width,
            height=mode.height,
            fps=mode.fps,
            pixelFormat=pixelFormat,
        )

        H, W = mode.height, mode.width

        # Atomically rebuild buffers
        with self._lock:
            self._bufferPool = [
                np.zeros((H, W, 3), dtype=np.uint8) for _ in range(self._poolSize)
            ]

            with self._frameQueue.mutex:
                self._frameQueue.queue.clear()

        requested = (width, height, fps)
        selected = (mode.width, mode.height, mode.fps)

        if requested != selected:
            warn(
                f"Using video mode {mode.width}x{mode.height}@{mode.fps} "
                f"(requested {width}x{height}@{fps})"
            )

    def getResolution(self) -> Resolution:
        videoMode = self.camera.getVideoMode()
        return (videoMode.width, videoMode.height)

    def getMaxFPS(self) -> float:
        return self.camera.getVideoMode().fps

    def getSupportedResolutions(self) -> List[Size]:
        resolutions = []
        for videomode in self._validVideoModes:
            resolutions.append((videomode.width, videomode.height))
        return resolutions
