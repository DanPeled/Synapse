from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from cscore import (
    VideoProperty,
)

from ...stypes import (
    CameraID,
    Frame,
    PropertyMetaDict,
    Resolution,
    Size,
)


class SynapseCamera(ABC):
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.stream: str = ""
        self.cameraIndex: CameraID = -1
        self.isRunning: bool = True

    def generateNoSignalFrame(self, size: Resolution = (640, 480)) -> Frame:
        width, height = size

        frame = np.zeros((height, width, 3), dtype=np.uint8)

        colors = [
            (255, 255, 255),  # white
            (0, 255, 255),  # yellow
            (255, 255, 0),  # cyan (0, 255, 0),  # green
            (255, 0, 255),  # magenta
            (0, 0, 255),  # red
            (255, 0, 0),  # blue
        ]

        bar_width = width // len(colors)
        for i, color in enumerate(colors):
            frame[:, i * bar_width : (i + 1) * bar_width] = color

        noise_intensity = np.random.randint(10, 40)
        noise = np.random.randint(0, noise_intensity, frame.shape, dtype=np.uint8)
        frame = cv2.add(frame, noise)

        for y in range(0, height, 2):
            frame[y : y + 1, :] = (frame[y : y + 1, :] * 0.6).astype(np.uint8)

        if np.random.rand() > 0.7:
            glitch_y = np.random.randint(0, height)
            glitch_height = np.random.randint(5, 20)
            shift = np.random.randint(-30, 30)
            frame[glitch_y : glitch_y + glitch_height] = np.roll(
                frame[glitch_y : glitch_y + glitch_height], shift, axis=1
            )

        text = f"NO SIGNAL ? {self.name} (#{self.cameraIndex})"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(width, height) / 600
        thickness = max(2, int(font_scale * 2))

        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2

        # Black outline
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (0, 0, 0),
            thickness + 3,
            cv2.LINE_AA,
        )

        # White foreground
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        return frame

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
        self.stream = ""

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

    def getProperties(self) -> List[VideoProperty]:
        return []

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
