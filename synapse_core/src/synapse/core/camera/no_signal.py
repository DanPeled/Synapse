# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from time import time
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np
from cscore import VideoMode
from synapse.stypes import CameraID, Frame, Resolution

from ...stypes import CameraName, PropertyMetaDict, Size
from .synapse_camera import SynapseCamera


class NoSignalCamera(SynapseCamera):
    def __init__(self) -> None:
        self.resolution: Resolution = (640, 480)

    @classmethod
    def create(
        cls, *_, path: Union[str, int] = 0, name: str = "", index: CameraID = -1
    ) -> "NoSignalCamera":
        inst = NoSignalCamera()
        return inst

    def getVideoMode(self) -> VideoMode:
        return VideoMode(
            VideoMode.PixelFormat.kMJPEG, self.resolution[0], self.resolution[1], 100
        )

    def enumerateVideoModes(self) -> List[VideoMode]:
        return [self.getVideoMode()]

    def grabFrame(self, buffer) -> Tuple[float, Optional[Frame]]:
        return time(), generateNoSignalFrame("Disconnected camera", -1, self.resolution)

    def isConnected(self) -> bool:
        # Pretend the camera is never connected
        return False

    def close(self) -> None:
        pass

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        # Ignore all property changes
        pass

    def getProperty(self, prop: str) -> Union[int, float, None]:
        # No properties exist
        return None

    def setVideoMode(self, videoMode: VideoMode) -> None:
        # Only store resolution for frame generation
        self.resolution = (videoMode.width, videoMode.height)

    def getResolution(self) -> Size:
        return self.resolution

    def getSupportedResolutions(self) -> List[Size]:
        # Only support the current resolution
        return [self.resolution]

    def getPropertyMeta(self) -> PropertyMetaDict:
        return {}

    def getMaxFPS(self) -> float:
        return 0.0


def generateNoSignalFrame(
    name: CameraName, cameraIndex: CameraID, size: Resolution = (640, 480)
) -> Frame:
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

    text = f"NO SIGNAL ? {name} (#{cameraIndex})"
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
