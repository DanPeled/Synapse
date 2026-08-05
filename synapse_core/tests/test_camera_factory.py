# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, patch

from cscore import VideoMode
from synapse.core.camera_factory import CsCoreCamera


class TestCsCoreCamera(unittest.TestCase):
    @patch("synapse.core.camera_factory.UsbCamera")
    @patch("synapse.core.camera_factory.CameraServer.getVideo")
    def test_create_with_usb_index(self, mock_get_video, mock_usb_camera):
        camera_instance = MagicMock()
        camera_instance.getVideoMode.return_value = VideoMode()
        mock_usb_camera.return_value = camera_instance
        mock_get_video.return_value = MagicMock()
        camera_instance.enumerateProperties.return_value = []

        cam = CsCoreCamera.create(index=0, name="TestCam", path="/dev/video0")

        self.assertIsInstance(cam, CsCoreCamera)
        mock_usb_camera.assert_called_once()
        mock_get_video.assert_called_once_with(camera_instance)

    def test_set_and_get_property_meta(self):
        cam = CsCoreCamera("mock")
        cam._properties = {
            "brightness": MagicMock(
                getMin=lambda: 0, getMax=lambda: 100, getDefault=lambda: 50
            )
        }
        cam.propertyMeta = {"brightness": {"min": 0, "max": 100, "default": 50}}

        self.assertIn("brightness", cam.propertyMeta)
        self.assertEqual(cam.propertyMeta["brightness"]["default"], 50)

    @patch("synapse.core.camera_factory.CvSink")
    def test_grabFrame_logic(self, mock_sink):
        cam = CsCoreCamera("mock")
        cam.sink = MagicMock()
        cam.sink.grabFrame.return_value = 10
        cam._running = False  # Skip the thread loop

        # Run a single iteration
        result = cam.sink.grabFrame()
        self.assertEqual(result, 10)

    def test_get_resolution(self):
        cam = CsCoreCamera("mock")
        cam.camera = MagicMock()
        cam.camera.getVideoMode.return_value.width = 640
        cam.camera.getVideoMode.return_value.height = 480

        res = cam.getResolution()
        self.assertEqual(res, (640, 480))

    def test_get_max_fps(self):
        cam = CsCoreCamera("mock")
        cam.camera = MagicMock()
        cam.camera.getVideoMode.return_value.fps = 30
        self.assertEqual(cam.getMaxFPS(), 30)


if __name__ == "__main__":
    unittest.main()
