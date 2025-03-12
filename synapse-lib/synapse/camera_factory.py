from abc import ABC, abstractmethod
from typing import Optional, Tuple, Union, override
import cv2
from synapse.log import err
from synapse.stypes import Frame
import numpy as np
from cscore import CameraServer, VideoCamera, VideoMode

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


def cscore_to_cv(prop: str) -> Optional[int]:
    return CSCORE_TO_CV_PROPS.get(prop)


def cv_to_cscore(prop: int) -> Optional[str]:
    return CV_TO_CSCORE_PROPS.get(prop)


class CameraFactory: ...  # TODO


class SynapseCamera(ABC):
    @abstractmethod
    def create(
        self, *_, devPath: Optional[str] = None, usbIndex: Optional[int] = None
    ) -> None: ...

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
    def setFPS(self, fps: int) -> None: ...


class OpenCvCamera(SynapseCamera):
    @override
    def create(
        self, *_, devPath: Optional[str] = None, usbIndex: Optional[int] = None
    ) -> None:
        if usbIndex is not None:
            self.cap = cv2.VideoCapture(usbIndex)
        elif devPath is not None:
            self.cap = cv2.VideoCapture(devPath, cv2.CAP_V4L2)
        else:
            err("No USB Index or Dev Path was provided for camera!")

    @override
    def grabFrame(self) -> Tuple[bool, Optional[Frame]]:
        return self.cap.read()

    @override
    def isConnected(self) -> bool:
        return self.cap.isOpened()

    @override
    def close(self) -> None:
        self.cap.release()

    @override
    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        if isinstance(prop, int) and self.cap:
            propInt = cscore_to_cv(prop)
            if propInt is not None:
                self.cap.set(propInt, value)

    @override
    def getProperty(self, prop: str) -> Union[int, float, None]:
        if isinstance(prop, int) and self.cap:
            propInt = cscore_to_cv(prop)
            if propInt is not None:
                return self.cap.get(propInt)
            else:
                return None
        return None

    @override
    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        if self.cap:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


class CsCoreCamera(SynapseCamera):
    @override
    def create(
        self, *_, devPath: Optional[str] = None, usbIndex: Optional[int] = None
    ) -> None:
        self.frameBuffer = np.zeros((1920, 1080, 3), dtype=np.uint8)
        if usbIndex is not None:
            self.camera: VideoCamera = CameraServer.startAutomaticCapture(
                devPath or f"USB Camera {usbIndex}", usbIndex
            )
        elif devPath is not None:
            self.camera: VideoCamera = CameraServer.startAutomaticCapture(
                devPath, devPath
            )
        else:
            err("No USB Index or Dev Path was provided for camera!")

        if self.camera is not None:
            self.sink = CameraServer.getVideo(self.camera)

    @override
    def grabFrame(self) -> Tuple[bool, Optional[Frame]]:
        if self.camera is not None:
            ret, frame = self.sink.grabFrame(self.frameBuffer)
            return ret != 0, frame
        return False, None

    @override
    def isConnected(self) -> bool:
        return self.camera is not None

    @override
    def close(self) -> None: ...

    @override
    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        if isinstance(prop, str) and self.camera and isinstance(value, int):
            self.camera.getProperty(prop).set(value)

    @override
    def getProperty(self, prop: str) -> Union[int, float, None]:
        if isinstance(prop, str) and self.camera:
            prop_obj = self.camera.getProperty(prop)
            if prop_obj:
                return prop_obj.get()
        return None

    @override
    def setVideoMode(self, fps: int, width: int, height: int) -> None:
        if self.camera:
            self.camera.setVideoMode(
                width=width,
                height=height,
                fps=fps,
                pixelFormat=VideoMode.PixelFormat.kMJPEG,
            )
