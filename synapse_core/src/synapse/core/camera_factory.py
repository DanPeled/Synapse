# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import queue
import socket
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Dict, Final, List, Optional, Tuple, Type, Union

import cv2
import numpy as np
from cscore import (CameraServer, CvSink, UsbCamera, VideoCamera, VideoMode,
                    VideoSource)
from ntcore import NetworkTable, NetworkTableEntry, NetworkTableInstance
from synapse_net.nt_client import NtClient
from synapse_net.proto.v1 import CalibrationDataProto
from wpimath import geometry

from ..log import err, warn
from ..stypes import CameraID, Frame, Resolution

Size = Tuple[int, int]
PropName = str
PropertyMetaDict = Dict[PropName, Dict[str, Union[int, float]]]
ResolutionString = str


class CameraPropKeys(Enum):
    kBrightness = "brightness"
    kContrast = "contrast"
    kSaturation = "saturation"
    kHue = "hue"
    kGain = "gain"
    kExposure = "exposure"
    kWhiteBalanceTemperature = "white_balance_temperature"
    kSharpness = "sharpness"
    kOrientation = "orientation"


CSCORE_TO_CV_PROPS = {
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "hue": cv2.CAP_PROP_HUE,
    "gain": cv2.CAP_PROP_GAIN,
    "exposure": cv2.CAP_PROP_EXPOSURE,
    "white_balance_temperature": cv2.CAP_PROP_WHITE_BALANCE_BLUE_U,
    "sharpness": cv2.CAP_PROP_SHARPNESS,
}

CV_TO_CSCORE_PROPS = {v: k for k, v in CSCORE_TO_CV_PROPS.items()}


class CameraSettingsKeys(Enum):
    kViewID = "view_id"
    kRecord = "record"
    kPipeline = "pipeline"
    kPipelineType = "pipeline_t"


@dataclass
class CalibrationData:
    matrix: List[float]
    distCoeff: List[float]
    meanErr: float
    measuredRes: Resolution

    def toDict(self) -> Dict[str, Any]:
        return {
            CameraConfigKey.kMatrix.value: self.matrix,
            CameraConfigKey.kDistCoeff.value: self.distCoeff,
            CameraConfigKey.kMeasuredRes.value: self.measuredRes,
            CameraConfigKey.kMeanErr.value: self.meanErr,
        }

    @staticmethod
    def fromDict(data: Dict[str, Any]) -> "CalibrationData":
        return CalibrationData(
            matrix=data[CameraConfigKey.kMatrix.value],
            distCoeff=data[CameraConfigKey.kDistCoeff.value],
            measuredRes=data[CameraConfigKey.kMeasuredRes.value],
            meanErr=data[CameraConfigKey.kMeanErr.value],
        )

    def toProto(self, cameraIndex: CameraID) -> CalibrationDataProto:
        return CalibrationDataProto(
            camera_index=cameraIndex,
            mean_error=self.meanErr,
            resolution="x".join([str(dim) for dim in self.measuredRes]),
            camera_matrix=self.matrix,
            dist_coeffs=self.distCoeff,
        )


@dataclass
class CameraConfig:
    name: str
    id: str
    calibration: Dict[ResolutionString, CalibrationData]
    defaultPipeline: int
    streamRes: Resolution

    def toDict(self) -> Dict[str, Any]:
        return {
            CameraConfigKey.kName.value: self.name,
            CameraConfigKey.kPath.value: self.id,
            CameraConfigKey.kDefaultPipeline.value: self.defaultPipeline,
            CameraConfigKey.kStreamRes.value: list(self.streamRes),
            CameraConfigKey.kCalibration.value: {
                resolution: calib.toDict()
                for resolution, calib in self.calibration.items()
            },
        }

    @staticmethod
    def fromDict(data: Dict[str, Any]) -> "CameraConfig":
        calib = {
            key: CalibrationData.fromDict(calib)
            for key, calib in data.get(CameraConfigKey.kCalibration.value, {}).items()
        }

        return CameraConfig(
            name=data[CameraConfigKey.kName.value],
            id=data[CameraConfigKey.kPath.value],
            streamRes=data[CameraConfigKey.kStreamRes.value],
            defaultPipeline=data[CameraConfigKey.kDefaultPipeline.value],
            calibration=calib,
        )


class CameraConfigKey(Enum):
    kName = "name"
    kPath = "id"
    kDefaultPipeline = "default_pipeline"
    kMatrix = "matrix"
    kDistCoeff = "distCoeffs"
    kMeasuredRes = "measured_res"
    kStreamRes = "stream_res"
    kCalibration = "calibration"
    kMeanErr = "mean_err"


def cscoreToOpenCVProp(prop: str) -> Optional[int]:
    return CSCORE_TO_CV_PROPS.get(prop)


def opencvToCscoreProp(prop: int) -> Optional[str]:
    return CV_TO_CSCORE_PROPS.get(prop)


class SynapseCamera(ABC):
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.stream: str = ""
        self.cameraIndex: CameraID = -1

    @classmethod
    @abstractmethod
    def create(
        cls,
        *_,
        path: Union[str, int],
        name: str = "",
        index: CameraID,
    ) -> "SynapseCamera": ...

    def setIndex(self, cameraIndex: CameraID) -> None:
        self.cameraIndex: CameraID = cameraIndex
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        self.stream = f"http://{ip}:{1181 + cameraIndex}/?action=stream/stream.mjpeg"

    @abstractmethod
    def grabFrame(self) -> Tuple[bool, Optional[Frame]]: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def isConnected(self) -> bool: ...

    @abstractmethod
    def setProperty(self, prop: str, value: Union[int, float]) -> None: ...

    @abstractmethod
    def getProperty(self, prop: str) -> Union[int, float, None]: ...

    @abstractmethod
    def setVideoMode(self, fps: int, width: int, height: int) -> None: ...

    @abstractmethod
    def getResolution(self) -> Size: ...

    @abstractmethod
    def getSupportedResolutions(self) -> List[Size]: ...

    @abstractmethod
    def getPropertyMeta(self) -> Optional[PropertyMetaDict]: ...

    @abstractmethod
    def getMaxFPS(self) -> float: ...

    def getSettingEntry(self, key: str) -> Optional[NetworkTableEntry]:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self)
            entry: NetworkTableEntry = table.getEntry(key)
            return entry
        return None

    def getSetting(self, key: str, defaultValue: Any) -> Any:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self)
            entry: NetworkTableEntry = table.getEntry(key)
            if not entry.exists():
                entry.setValue(defaultValue)
            return entry.getValue()
        return None

    def setSetting(self, key: str, value: Any) -> None:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self)
            entry: NetworkTableEntry = table.getEntry(key)
            entry.setValue(value)


class OpenCvCamera(SynapseCamera):
    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.cap: cv2.VideoCapture

    @classmethod
    def create(
        cls,
        *_,
        name: str = "",
        path: Union[str, int],
        index: CameraID,
    ) -> "OpenCvCamera":
        inst = OpenCvCamera(name)
        assert isinstance(path, int) or isinstance(path, str), (
            f"No valid path for camera {index}"
        )

        if isinstance(path, int):
            inst.cap = cv2.VideoCapture(path)
        if isinstance(path, str):
            inst.cap = cv2.VideoCapture(path, cv2.CAP_V4L2)

        return inst

    def getSupportedResolutions(self) -> List[Size]:
        return [self.getResolution()]

    def getPropertyMeta(self) -> Optional[PropertyMetaDict]:
        return None

    def grabFrame(self) -> Tuple[bool, Optional[Frame]]:
        return self.cap.read()

    def isConnected(self) -> bool:
        return self.cap.isOpened()

    def close(self) -> None:
        self.cap.release()

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        if isinstance(prop, int) and self.cap:
            propInt = cscoreToOpenCVProp(prop)
            if propInt is not None:
                self.cap.set(propInt, value)

    def getProperty(self, prop: str) -> Union[int, float, None]:
        if isinstance(prop, int) and self.cap:
            propInt = cscoreToOpenCVProp(prop)
            if propInt is not None:
                return self.cap.get(propInt)
            else:
                return None
        return None

    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def getResolution(self) -> Size:
        return (
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def getMaxFPS(self) -> float:
        desired_fps = 120
        self.cap.set(cv2.CAP_PROP_FPS, desired_fps)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        return actual_fps


class CsCoreCamera(SynapseCamera):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.camera: VideoCamera
        self.sink: CvSink
        self.propertyMeta: PropertyMetaDict = {}
        self._properties: Dict[str, Any] = {}
        self._videoModes: List[Any] = []
        self._validVideoModes: List[VideoMode] = []

        # --- FIX: Memory Recycling Implementation ---
        # Pool of pre-allocated frame buffers
        self._poolSize: Final[int] = 5
        self._bufferPool: List[np.ndarray] = []

        # Queue now holds the INDEX of the filled buffer, not a copy of the frame data
        # Tuple[bool, Optional[int]]: (hasFrame, buffer_index)
        self._frameQueue: queue.Queue[Tuple[bool, Optional[int]]] = queue.Queue(
            maxsize=self._poolSize
        )
        # --- END FIX ---

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

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
        inst.sink.getProperty("auto_exposure").set(0)

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
        inst._validVideoModes = [mode for mode in inst._videoModes]

        # This will call setVideoMode, which now initializes the buffer pool.
        inst.setVideoMode(1000, 1920, 1080)

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
        # Wait until the camera reports connected
        while self._running and not self.isConnected():
            time.sleep(0.1)

        buffer_index = 0

        while self._running:
            # ---- HARD SAFETY GUARD ----
            if not self._bufferPool:
                time.sleep(0.1)
                continue

            # Get current video mode (used for pacing)
            mode = self.camera.getVideoMode()
            fps = mode.fps if mode and mode.fps > 0 else 30

            # Select buffer (safe: bufferPool is non-empty)
            try:
                buffer = self._bufferPool[buffer_index]
            except IndexError:
                # Pool changed while running (video mode switch)
                buffer_index = 0
                time.sleep(0.01)
                continue

            # Grab frame into pre-allocated buffer
            with self._lock:
                timestamp = self.sink.grabFrame(buffer)

            if timestamp != 0:
                # Push buffer index (drop oldest if queue full)
                try:
                    self._frameQueue.put_nowait((True, buffer_index))
                except queue.Full:
                    try:
                        self._frameQueue.get_nowait()
                    except queue.Empty:
                        pass
                    self._frameQueue.put_nowait((True, buffer_index))

                # Advance buffer index circularly
                buffer_index = (buffer_index + 1) % len(self._bufferPool)

            # ---- FRAME PACING (NO SPINNING) ----
            # Sleep for half-frame period to reduce latency
            sleep_time = max(0.002, 1.0 / fps / 2.0)
            time.sleep(sleep_time)

    def _waitForNextFrame(self):
        if self.isConnected():
            mode = self.camera.getVideoMode()
            if mode.fps > 0:
                time.sleep(1.0 / mode.fps / 2.0)

    def grabFrame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            try:
                hasFrame, index = self._frameQueue.get_nowait()
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
        # 1. Exact match
        if self._videoModes is None or len(self._videoModes) == 0:
            return None

        for mode in self._validVideoModes:
            if (
                mode.width == width
                and mode.height == height
                and mode.pixelFormat == pixelFormat
            ):
                return mode

        # 2. Same resolution, closest FPS
        same_res = [
            m
            for m in self._validVideoModes
            if m.width == width and m.height == height and m.pixelFormat == pixelFormat
        ]
        if same_res:
            return max(same_res, key=lambda m: m.fps)

        # 3. Closest resolution by area
        def area(m):
            return m.width * m.height

        return max(
            (m for m in self._validVideoModes if m.pixelFormat == pixelFormat),
            key=area,
        )

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


class CameraFactory:
    kOpenCV: Type[SynapseCamera] = OpenCvCamera
    kCameraServer: Type[SynapseCamera] = CsCoreCamera
    kDefault: Type[SynapseCamera] = kCameraServer

    @classmethod
    def create(
        cls,
        *_,
        cameraType: Type[SynapseCamera] = kDefault,
        cameraIndex: CameraID,
        path: Union[str, int],
        name: str = "",
    ) -> "SynapseCamera":
        cam: SynapseCamera = cameraType.create(
            path=path,
            name=name,
            index=cameraIndex,
        )
        cam.setIndex(cameraIndex)
        return cam


@cache
def getCameraTable(camera: SynapseCamera) -> NetworkTable:
    return (
        NetworkTableInstance.getDefault()
        .getTable(NtClient.NT_TABLE)
        .getSubTable(getCameraTableName(camera))
    )


def getCameraTableName(camera: SynapseCamera) -> str:
    return camera.name


def listToTransform3d(dataList: List[List[float]]) -> geometry.Transform3d:
    """
    Converts a 2D list containing position and rotation data into a Transform3d object.

    The input list must contain exactly two sublists:
    - The first sublist represents the translation (x, y, z).
    - The second sublist represents the rotation (roll, pitch, yaw) in degrees.

    Args:
        dataList (List[List[float]]): A list with two elements, each being a list of three floats.

    Returns:
        geometry.Transform3d: The resulting Transform3d object. Returns an identity transform
        if the input list does not contain exactly two elements.
    """
    if len(dataList) != 2:
        err("Invalid transform length")
        return geometry.Transform3d()
    else:
        poseList = dataList[0]
        rotationList = dataList[1]

        return geometry.Transform3d(
            translation=geometry.Translation3d(poseList[0], poseList[1], poseList[2]),
            rotation=geometry.Rotation3d.fromDegrees(
                rotationList[0], rotationList[1], rotationList[2]
            ),
        )


def transform3dToList(transform: geometry.Transform3d) -> List[List[float]]:
    """
    Converts a Transform3d object into a 2D list containing position and rotation data.

    The output list contains two sublists:
    - The first sublist represents the translation (x, y, z).
    - The second sublist represents the rotation (roll, pitch, yaw) in degrees.

    Args:
        transform (geometry.Transform3d): The Transform3d object to convert.

    Returns:
        List[List[float]]: A 2D list with translation and rotation values.
    """
    translation = transform.translation()
    rotation = transform.rotation()

    return [
        [translation.x, translation.y, translation.z],
        [
            rotation.x_degrees,  # Roll
            rotation.y_degrees,  # Pitch
            rotation.z_degrees,  # Yaw
        ],
    ]
