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
        self._name: str = "Disconnected camera"
        self._index: CameraID = -1

    @classmethod
    def create(
        cls, *_, path: Union[str, int] = 0, name: str = "", index: CameraID = -1
    ) -> "NoSignalCamera":
        inst = NoSignalCamera()
        if name:
            inst._name = name
        if index != -1:
            inst._index = index
        return inst

    def getVideoMode(self) -> VideoMode:
        return VideoMode(
            VideoMode.PixelFormat.kMJPEG, self.resolution[0], self.resolution[1], 30
        )

    def enumerateVideoModes(self) -> List[VideoMode]:
        return [
            VideoMode(VideoMode.PixelFormat.kMJPEG, w, h, 30)
            for w, h in [
                (1920, 1080),
                (1280, 720),
                (640, 480),
                (320, 240),
            ]
        ]

    def grabFrame(self, buffer) -> Tuple[float, Optional[Frame]]:
        try:
            frame = generateNoSignalFrame(self._name, self._index, self.resolution)
            if buffer is not None and frame is not None:
                h, w = frame.shape[:2]
                bh, bw = buffer.shape[:2]
                if h == bh and w == bw:
                    buffer[:] = frame
                    return time(), buffer
                # Resize if needed
                resized = cv2.resize(frame, (bw, bh), interpolation=cv2.INTER_AREA)
                buffer[:] = resized
                return time(), buffer
            return time(), frame
        except Exception:
            return time(), None

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
        try:
            self.resolution = (int(videoMode.width), int(videoMode.height))
        except Exception:
            pass

    def getResolution(self) -> Size:
        return self.resolution

    def getSupportedResolutions(self) -> List[Size]:
        # Only support the current resolution
        return [self.resolution]

    def getPropertyMeta(self) -> PropertyMetaDict:
        return {}

    def getMaxFPS(self) -> float:
        return 30.0


def generateNoSignalFrame(
    name: CameraName, cameraIndex: CameraID, size: Resolution = (640, 480)
) -> Frame:
    try:
        width, height = int(size[0]), int(size[1])
        if width <= 0 or height <= 0:
            width, height = 640, 480
    except Exception:
        width, height = 640, 480

    frame = np.zeros((height, width, 3), dtype=np.uint8)

    colors = [
        (255, 255, 255),  # white
        (0, 255, 255),  # yellow
        (255, 255, 0),  # cyan
        (255, 0, 255),  # magenta
        (0, 0, 255),  # red
        (255, 0, 0),  # blue
    ]

    bar_width = max(1, width // len(colors))
    for i, color in enumerate(colors):
        start_x = i * bar_width
        end_x = (i + 1) * bar_width if i < len(colors) - 1 else width
        frame[:, start_x:end_x] = color

    try:
        noise_intensity = int(np.random.randint(10, 40))
        noise = np.random.randint(0, noise_intensity, frame.shape, dtype=np.uint8)
        frame = cv2.add(frame, noise)
    except Exception:
        pass

    try:
        for y in range(0, height, 2):
            frame[y : y + 1, :] = (frame[y : y + 1, :] * 0.6).astype(np.uint8)
    except Exception:
        pass

    try:
        if np.random.rand() > 0.7:
            glitch_y = np.random.randint(0, height)
            glitch_height = np.random.randint(5, min(20, height))
            shift = np.random.randint(-30, 30)
            if glitch_height > 0:
                roi = frame[glitch_y : glitch_y + glitch_height]
                if roi.size > 0:
                    frame[glitch_y : glitch_y + glitch_height] = np.roll(roi, shift, axis=1)
    except Exception:
        pass

    try:
        text = f"NO SIGNAL | {name} (#{cameraIndex})"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(width, height) / 800.0
        thickness = max(1, int(font_scale * 2))
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = max(0, (width - text_size[0]) // 2)
        text_y = max(text_size[1], (height + text_size[1]) // 2)

        # Black outline
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            font,
            font_scale,
            (0, 0, 0),
            thickness + 2,
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
    except Exception:
        pass

    return frame
