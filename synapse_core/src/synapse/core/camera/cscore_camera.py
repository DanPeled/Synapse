# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from cscore import (
    CameraServer,
    CvSink,
    UsbCamera,
    VideoCamera,
    VideoMode,
    VideoProperty,
    VideoSource,
)
from wpiutil import PixelFormat

from ...stypes import CameraID, PropertyMetaDict, Resolution, Size
from .synapse_camera import SynapseCamera


class CsCoreCamera(SynapseCamera):
    def __init__(self) -> None:
        self.camera: VideoCamera
        self.sink: CvSink
        self._properties: Dict[str, VideoProperty] = {}
        self.propertyMeta: PropertyMetaDict = {}
        self._videoModes: Optional[List[VideoMode]] = None

    def getProperties(self) -> List:
        return list(self._properties.values())

    @classmethod
    def create(
        cls,
        *_,
        path: Union[str, int],
        index: CameraID,
    ) -> "CsCoreCamera":
        inst = CsCoreCamera()

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

        return inst

    def enumerateVideoModes(self) -> List[VideoMode]:
        # Enumerating video modes talks to the camera, so only do it once. The
        # camera handle and settings API both ask for these on every bind.
        if self._videoModes is None:
            self._videoModes = list(self.camera.enumerateVideoModes() or [])
        return self._videoModes

    def getPropertyMeta(self) -> PropertyMetaDict:
        return self.propertyMeta

    def grabFrame(self, buffer: np.ndarray) -> Tuple[int, Optional[np.ndarray]]:
        """Grab the next frame into ``buffer`` using CSCore's decoded BGR path.

        Profiling note from real-camera, multi-camera runs: CSCore's MJPEG ->
        BGR conversion inside this call dominates capture-thread samples (JPEG
        IDCT and YCC conversion). Direct-grab APIs avoid that work but return
        sink-owned compressed bytes without a portable length/ownership
        contract, so they are not a drop-in replacement. Use
        ``scripts/benchmark_multi_camera.py`` for an A/B before changing this
        path, and preserve the configured resolution and FPS in the comparison.
        """
        return self.sink.grabFrame(buffer)

    def isConnected(self) -> bool:
        return self.camera.isConnected()

    def close(self) -> None:
        self.camera.setConnectionStrategy(
            VideoSource.ConnectionStrategy.kConnectionForceClose
        )

    def setProperty(self, prop: str, value: Union[int, float, str]) -> None:
        self._properties[prop].set(value)  # pyright: ignore

    def getProperty(self, prop: str) -> Union[int, float, None]:
        if prop in self._properties:
            return self._properties[prop].get()
        return None

    def setVideoMode(self, videoMode: VideoMode) -> None:
        try:
            self.camera.setVideoMode(
                width=videoMode.width,
                height=videoMode.height,
                fps=videoMode.fps,
                pixelFormat=PixelFormat.MJPEG,
            )
        except Exception:
            try:
                self.camera.setVideoMode(videoMode)
            except Exception:
                raise

    def getResolution(self) -> Resolution:
        videoMode = self.camera.getVideoMode()
        return (videoMode.width, videoMode.height)

    def getMaxFPS(self) -> float:
        return self.camera.getVideoMode().fps

    def getSupportedResolutions(self) -> List[Size]:
        resolutions = []
        for videomode in self.enumerateVideoModes():
            resolutions.append((videomode.width, videomode.height))
        return resolutions

    def getVideoMode(self) -> VideoMode:
        return self.camera.getVideoMode()
