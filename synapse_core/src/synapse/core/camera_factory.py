from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import cv2
import numpy as np
from cscore import CameraServer, CvSink, UsbCamera, VideoCamera, VideoMode
from cv2.typing import Size
from ntcore import NetworkTable, NetworkTableEntry, NetworkTableInstance
from synapse.log import err
from synapse.stypes import Frame
from synapse_net.nt_client import NtClient
from wpimath import geometry


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


class CsCoreCamera(SynapseCamera):
    def __init__(self) -> None:
        self.camera: VideoCamera
        self.frameBuffer: np.ndarray
        self.sink: CvSink
        self.property_meta: Dict = {}

    @classmethod
    def create(
        cls,
        *_,
        devPath: Optional[str] = None,
        usbIndex: Optional[int] = None,
        name: str = "",
    ) -> "CsCoreCamera":
        inst = CsCoreCamera()
        inst.frameBuffer = np.zeros((1920, 1080, 3), dtype=np.uint8)
        if usbIndex is not None:
            inst.camera = UsbCamera(devPath or f"USB Camera {usbIndex}", usbIndex)
        elif devPath is not None:
            inst.camera = UsbCamera(f"{name}", devPath)
        else:
            err("No USB Index or Dev Path was provided for camera!")

        if inst.camera is not None:
            inst.sink = CameraServer.getVideo(inst.camera)

        inst.property_meta = {}
        for prop in inst.camera.enumerateProperties():
            inst.property_meta[prop.getName()] = {
                "min": prop.getMin(),
                "max": prop.getMax(),
                "default": prop.getDefault(),
            }

        return inst

    def grabFrame(self) -> Tuple[bool, Optional[Frame]]:
        if self.camera is not None:
            ret, frame = self.sink.grabFrame(self.frameBuffer)
            return ret != 0, frame
        return False, None

    def isConnected(self) -> bool:
        return self.camera.isConnected()

    def close(self) -> None: ...

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        if (
            isinstance(prop, str)
            and self.camera
            and isinstance(value, int)
            and prop in self.property_meta.keys()
        ):
            self.camera.getProperty(prop).set(
                max(
                    min(value, self.property_meta[prop]["max"]),
                    self.property_meta[prop]["min"],
                )
            )

    def getProperty(self, prop: str) -> Union[int, float, None]:
        if isinstance(prop, str) and self.camera:
            prop_obj = self.camera.getProperty(prop)
            if prop_obj:
                return prop_obj.get()
        return None

    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        if self.camera:
            valid_modes = []

            for mode in self.camera.enumerateVideoModes():
                valid_modes.append(
                    (
                        mode.width,
                        mode.height,
                    )
                )

            if (width, height) in valid_modes:
                self.camera.setVideoMode(
                    width=width,
                    height=height,
                    fps=fps,
                    pixelFormat=VideoMode.PixelFormat.kMJPEG,
                )
            else:
                err(
                    f"Warning: Invalid video mode (width={width}, height={height}). Using default settings."
                )

    def getResolution(self) -> Size:
        videoMode = self.camera.getVideoMode()
        return (videoMode.width, videoMode.height)


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
