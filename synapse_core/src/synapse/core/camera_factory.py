import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import cv2
import numpy as np
from cscore import (CameraServer, CvSink, UsbCamera, VideoCamera, VideoMode,
                    VideoSource)
from cv2.typing import Size
from ntcore import NetworkTable, NetworkTableEntry, NetworkTableInstance
from synapse.log import err, warn
from synapse.stypes import Frame
from synapse_net.nt_client import NtClient
from wpimath import geometry

PropertMetaDict = Dict[str, Dict[str, Union[int, float]]]


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


def getCameraTableName(index: int) -> str:
    return f"camera{index}"


@dataclass
class CameraConfig:
    """
    Represents the configuration for a single camera.

    Attributes:
        name (str): The unique name or identifier for the camera.
        path (Union[str, int]): The path or device index used to access the camera (e.g., '/dev/video0' or 0).
        transform (geometry.Transform3d): The transformation from the camera to the robot coordinate frame.
        defaultPipeline (int): The default processing pipeline index to use for the camera.
        matrix (List[List[float]]): The intrinsic camera matrix (usually 3x3).
        distCoeff (List[float]): The distortion coefficients for the camera lens.
        measuredRes (Tuple[int, int]): The resolution (width, height) used for camera calibration.
        streamRes (Tuple[int, int]): The resolution (width, height) used for video streaming.
    """

    name: str
    path: str
    transform: geometry.Transform3d
    defaultPipeline: int
    matrix: List[List[float]]
    distCoeff: List[float]
    measuredRes: Tuple[int, int]
    streamRes: Tuple[int, int]


class CameraConfigKey(Enum):
    kName = "name"
    kPath = "path"
    kDefaultPipeline = "default_pipeline"
    kMatrix = "matrix"
    kDistCoeff = "distCoeffs"
    kMeasuredRes = "measured_res"
    kStreamRes = "stream_res"
    kTransform = "transform"


@cache
def getCameraTable(cameraIndex: int) -> NetworkTable:
    return (
        NetworkTableInstance.getDefault()
        .getTable(NtClient.NT_TABLE)
        .getSubTable(getCameraTableName(cameraIndex))
    )


def cscoreToOpenCVProp(prop: str) -> Optional[int]:
    return CSCORE_TO_CV_PROPS.get(prop)


def opencvToCscoreProp(prop: int) -> Optional[str]:
    return CV_TO_CSCORE_PROPS.get(prop)


class SynapseCamera(ABC):
    @classmethod
    @abstractmethod
    def create(
        cls,
        *_,
        devPath: Optional[str] = None,
        usbIndex: Optional[int] = None,
        name: str = "",
    ) -> "SynapseCamera": ...

    def setIndex(self, cameraIndex: int) -> None:
        self.cameraIndex: int = cameraIndex

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
    def getPropertyMeta(self) -> Optional[PropertMetaDict]: ...

    @abstractmethod
    def getMaxFPS(self) -> float: ...

    def getSettingEntry(self, key: str) -> Optional[NetworkTableEntry]:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self.cameraIndex)
            entry: NetworkTableEntry = table.getEntry(key)
            return entry
        return None

    def getSetting(self, key: str, defaultValue: Any) -> Any:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self.cameraIndex)
            entry: NetworkTableEntry = table.getEntry(key)
            if not entry.exists():
                entry.setValue(defaultValue)
            return entry.getValue()
        return None

    def setSetting(self, key: str, value: Any) -> None:
        if hasattr(self, "cameraIndex"):
            table: NetworkTable = getCameraTable(self.cameraIndex)
            entry: NetworkTableEntry = table.getEntry(key)
            entry.setValue(value)

    @property
    def viewID(self) -> str:
        entry = self.getSettingEntry(CameraSettingsKeys.kViewID.value)
        if entry is not None:
            return entry.getString("")
        return ""

    @viewID.setter
    def viewID(self, value: str) -> None:
        self.setSetting(CameraSettingsKeys.kViewID.value, value)

    @property
    def record(self) -> bool:
        entry = self.getSettingEntry(CameraSettingsKeys.kRecord.value)
        if entry is not None:
            return entry.getBoolean(False)
        return False

    @record.setter
    def record(self, value: bool) -> None:
        self.setSetting(CameraSettingsKeys.kViewID.value, value)

    @property
    def pipeline(self) -> int:
        entry = self.getSettingEntry(CameraSettingsKeys.kPipeline.value)
        if entry is not None:
            return entry.getInteger(0)
        return 0

    @pipeline.setter
    def pipeline(self, value: int) -> None:
        self.setSetting(CameraSettingsKeys.kPipeline.value, value)


class OpenCvCamera(SynapseCamera):
    def __init__(self) -> None:
        self.cap: cv2.VideoCapture

    @classmethod
    def create(
        cls,
        *_,
        devPath: Optional[str] = None,
        usbIndex: Optional[int] = None,
        name: str = "",
    ) -> "OpenCvCamera":
        inst = OpenCvCamera()
        if usbIndex is not None:
            inst.cap = cv2.VideoCapture(usbIndex)
        elif devPath is not None:
            inst.cap = cv2.VideoCapture(devPath, cv2.CAP_V4L2)
        else:
            err("No USB Index or Dev Path was provided for camera!")

        return inst

    def getPropertyMeta(self) -> Optional[PropertMetaDict]:
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
    def __init__(self) -> None:
        self.camera: VideoCamera
        self.frameBuffer: np.ndarray
        self.sink: CvSink
        self.propertyMeta: PropertMetaDict = {}
        self._properties: Dict[str, Any] = {}
        self._videoModes: List[Any] = []
        self._validVideoModes: List[VideoMode] = []

        self._frameQueue: queue.Queue[Tuple[bool, Optional[np.ndarray]]] = queue.Queue(
            maxsize=5
        )
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def create(
        cls,
        *_,
        devPath: Optional[str] = None,
        usbIndex: Optional[int] = None,
        name: str = "",
    ) -> "CsCoreCamera":
        inst = CsCoreCamera()

        if usbIndex is not None:
            inst.camera = UsbCamera(devPath or f"USB Camera {usbIndex}", usbIndex)
        elif devPath is not None:
            inst.camera = UsbCamera(name, devPath)
        else:
            raise ValueError(
                "Camera initialization failed: no USB Index or Dev Path provided."
            )

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
        inst._validVideoModes = [mode for mode in inst._videoModes]

        # Initialize frame buffer to current resolution
        mode = inst.camera.getVideoMode()
        inst.frameBuffer = np.zeros((mode.height, mode.width, 3), dtype=np.uint8)

        # Start background frame grabbing thread
        inst._startFrameThread()

        return inst

    def getPropertyMeta(self) -> Optional[PropertMetaDict]:
        return self.propertyMeta

    def _startFrameThread(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._frameGrabberLoop, daemon=True)
        self._thread.start()

    def _frameGrabberLoop(self) -> None:
        while not self.isConnected():
            time.sleep(0.1)
        while self._running:
            result = self.sink.grabFrame(self.frameBuffer)
            if len(result) > 0:
                ret, frame = result
                hasFrame = ret != 0
                if hasFrame:
                    frame_copy = frame.copy()  # Make a deep copy
                    try:
                        self._frameQueue.put_nowait((hasFrame, frame_copy))
                    except queue.Full:
                        try:
                            self._frameQueue.get_nowait()  # drop oldest frame
                        except queue.Empty:
                            pass
                        self._frameQueue.put_nowait((hasFrame, frame_copy))
                else:
                    self._waitForNextFrame()
            self._waitForNextFrame()

    def _waitForNextFrame(self):
        if self.isConnected():
            time.sleep(1.0 / self.getMaxFPS() / 2.0)  # Half the expected frame interval

    def grabFrame(self) -> Tuple[bool, Optional[np.ndarray]]:
        try:
            return self._frameQueue.get_nowait()
        except queue.Empty:
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

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        if prop in self._properties:
            meta = self.propertyMeta[prop]
            value = int(np.clip(value, meta["min"], meta["max"]))
            self._properties[prop].set(value)

    def getProperty(self, prop: str) -> Union[int, float, None]:
        if prop in self._properties:
            return self._properties[prop].get()
        return None

    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        pixelFormat = VideoMode.PixelFormat.kMJPEG

        for mode in self._validVideoModes:
            if (
                width == mode.width
                and height == mode.height
                and mode.pixelFormat == pixelFormat
            ):
                self.camera.setVideoMode(
                    width=width,
                    height=height,
                    fps=mode.fps,
                    pixelFormat=pixelFormat,
                )
                self.frameBuffer = np.zeros((height, width, 3), dtype=np.uint8)
                return
        else:
            warn(
                f"Invalid video mode (width={width}, height={height}). Using default settings."
            )

    def getResolution(self) -> Tuple[int, int]:
        videoMode = self.camera.getVideoMode()
        return (videoMode.width, videoMode.height)

    def getMaxFPS(self) -> float:
        return self.camera.getVideoMode().fps


class CameraFactory:
    kOpenCV: Type[SynapseCamera] = OpenCvCamera
    kCameraServer: Type[SynapseCamera] = CsCoreCamera
    kDefault: Type[SynapseCamera] = kCameraServer

    @classmethod
    def create(
        cls,
        *_,
        cameraType: Type[SynapseCamera] = kDefault,
        cameraIndex: int,
        devPath: Optional[str] = None,
        usbIndex: Optional[int] = None,
        name: str = "",
    ) -> "SynapseCamera":
        cam: SynapseCamera = cameraType.create(
            devPath=devPath,
            usbIndex=usbIndex,
            name=name,
        )
        cam.setIndex(cameraIndex)
        return cam
