# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
from unittest.mock import MagicMock, patch

from cscore import VideoMode
from synapse.core.camera.camera_handle import CameraHandle
from synapse.core.camera.cscore_camera import CsCoreCamera
from synapse.core.settings_api import CameraSettings
from wpiutil import PixelFormat

MJPEG = PixelFormat.MJPEG


class FakeCamera:
    """Minimal camera that counts capability queries and writes."""

    def __init__(self, modes: Optional[List[VideoMode]] = None) -> None:
        self.modes = modes or [
            VideoMode(MJPEG, 640, 480, 30),
            VideoMode(MJPEG, 1920, 1080, 30),
        ]
        self.videoMode = self.modes[0]
        self.meta = {"brightness": {"min": 0, "max": 100, "default": 50}}
        self.values = {"brightness": 50}
        self.enumerateCalls = 0
        self.metaCalls = 0
        self.setVideoModeCalls: List[VideoMode] = []
        self.setPropertyCalls: List[tuple] = []

    def enumerateVideoModes(self) -> List[VideoMode]:
        self.enumerateCalls += 1
        return list(self.modes)

    def getSupportedResolutions(self) -> List[tuple]:
        return [(mode.width, mode.height) for mode in self.enumerateVideoModes()]

    def getPropertyMeta(self) -> dict:
        self.metaCalls += 1
        return self.meta

    def getProperties(self) -> list:
        return []

    def getVideoMode(self) -> VideoMode:
        return self.videoMode

    def getMaxFPS(self) -> float:
        return self.videoMode.fps

    def setVideoMode(self, videoMode: VideoMode) -> None:
        self.setVideoModeCalls.append(videoMode)
        self.videoMode = videoMode

    def getProperty(self, prop: str):
        return self.values.get(prop)

    def setProperty(self, prop: str, value) -> None:
        self.setPropertyCalls.append((prop, value))
        self.values[prop] = value


def makeHandle(camera: FakeCamera) -> CameraHandle:
    with patch.object(CameraHandle, "_startFrameThread"):
        return CameraHandle(camera, "test camera", 0)


def test_cscore_camera_caches_video_modes() -> None:
    camera = CsCoreCamera()
    camera.camera = MagicMock()
    modes = [VideoMode(MJPEG, 640, 480, 30)]
    camera.camera.enumerateVideoModes.return_value = modes

    assert camera.enumerateVideoModes() == modes
    assert camera.enumerateVideoModes() == modes
    assert camera.getSupportedResolutions() == [(640, 480)]

    camera.camera.enumerateVideoModes.assert_called_once_with()


def test_camera_handle_caches_capabilities_across_binds() -> None:
    camera = CsCoreCamera()
    camera.camera = MagicMock()
    camera.camera.enumerateVideoModes.return_value = [VideoMode(MJPEG, 640, 480, 30)]
    camera.camera.getPropertyMeta.return_value = {}
    camera.camera.getProperties.return_value = []
    camera.camera.getVideoMode.return_value = VideoMode(MJPEG, 640, 480, 30)

    makeHandle(camera)  # type: ignore[arg-type]
    settings = CameraSettings()
    settings.fromCamera(camera)
    settings.fromCamera(camera)

    camera.camera.enumerateVideoModes.assert_called_once_with()
    camera.camera.getPropertyMeta.assert_not_called()


def test_property_metadata_is_cached_per_handle() -> None:
    camera = FakeCamera()
    handle = makeHandle(camera)

    assert camera.metaCalls == 1
    handle.setProperty("brightness", 25)

    assert camera.metaCalls == 1
    assert camera.setPropertyCalls == [("brightness", 25)]


def test_unchanged_property_values_are_not_written() -> None:
    camera = FakeCamera()
    handle = makeHandle(camera)

    handle.setProperty("brightness", 50)
    assert camera.setPropertyCalls == []

    handle.setProperty("brightness", 75)
    handle.setProperty("brightness", 75)
    assert camera.setPropertyCalls == [("brightness", 75)]

    handle.setProperty("brightness", 500)
    assert camera.setPropertyCalls[-1] == ("brightness", 100)


def test_unchanged_resolution_does_not_rebuild_buffers() -> None:
    camera = FakeCamera()
    handle = makeHandle(camera)

    with patch("synapse.core.camera.camera_handle.time.sleep") as sleep:
        # The camera is already at 640x480, including on the first write.
        handle.setProperty("resolution", "640x480")
        handle.setProperty("resolution", "640x480")

        assert camera.setVideoModeCalls == []
        originalBuffers = handle._bufferPool

        handle.setProperty("resolution", "1920x1080")
        handle.setProperty("resolution", "1920x1080")

        assert len(camera.setVideoModeCalls) == 1
        assert handle._bufferPool is not originalBuffers
        assert handle._bufferPool[0].shape == (1080, 1920, 3)
        assert sleep.call_count == 1

        handle.setProperty("resolution", "640x480")
        handle.setProperty("resolution", "640x480")

        assert len(camera.setVideoModeCalls) == 2
        assert sleep.call_count == 2


def test_video_mode_comparison_includes_fps_and_pixel_format() -> None:
    camera = FakeCamera(
        modes=[
            VideoMode(MJPEG, 640, 480, 30),
            VideoMode(MJPEG, 640, 480, 60),
        ]
    )
    handle = makeHandle(camera)

    with patch("synapse.core.camera.camera_handle.time.sleep"):
        handle.setVideoMode(VideoMode(MJPEG, 640, 480, 30))
        assert camera.setVideoModeCalls == []

        handle.setVideoMode(VideoMode(MJPEG, 640, 480, 60))
        assert len(camera.setVideoModeCalls) == 1

        handle._activeVideoMode = VideoMode(PixelFormat.YUYV, 640, 480, 60)
        handle.setVideoMode(VideoMode(MJPEG, 640, 480, 60))
        assert len(camera.setVideoModeCalls) == 2
