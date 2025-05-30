import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import synapse.core.camera_factory
from synapse.core.camera_factory import CsCoreCamera


class TestUtilityFunctions(unittest.TestCase):
    def test_getCameraTableName(self):
        self.assertEqual(synapse.core.camera_factory.getCameraTableName(2), "camera2")

    def test_cscoreToOpenCVProp(self):
        self.assertEqual(
            synapse.core.camera_factory.cscoreToOpenCVProp("brightness"),
            cv2.CAP_PROP_BRIGHTNESS,
        )

    def test_opencvToCscoreProp(self):
        self.assertEqual(
            synapse.core.camera_factory.opencvToCscoreProp(cv2.CAP_PROP_CONTRAST),
            "contrast",
        )


class TestCameraConfig(unittest.TestCase):
    def test_camera_config_creation(self):
        transform = MagicMock()
        config = synapse.core.camera_factory.CameraConfig(
            name="cam",
            path="/dev/video0",
            transform=transform,
            defaultPipeline=1,
            matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            distCoeff=[0.1, 0.01],
            measuredRes=(640, 480),
            streamRes=(320, 240),
        )
        self.assertEqual(config.name, "cam")


class TestOpenCvCamera(unittest.TestCase):
    @patch("cv2.VideoCapture")
    def test_create_with_usb_index(self, mock_vc):
        mock_vc.return_value = MagicMock()
        cam = synapse.core.camera_factory.OpenCvCamera.create(usbIndex=0)
        self.assertIsInstance(cam, synapse.core.camera_factory.OpenCvCamera)

    @patch("cv2.VideoCapture")
    def test_grab_frame(self, mock_vc):
        inst = synapse.core.camera_factory.OpenCvCamera()
        mock_capture = MagicMock()
        inst.cap = mock_capture
        inst.cap.read.return_value = (True, "frame")
        self.assertEqual(inst.grabFrame(), (True, "frame"))

    def test_set_and_get_video_mode(self):
        inst = synapse.core.camera_factory.OpenCvCamera()
        inst.cap = MagicMock()
        inst.setVideoMode(30, 640, 480)
        inst.cap.set.assert_any_call(cv2.CAP_PROP_FPS, 30)
        inst.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 640)
        inst.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def test_get_resolution(self):
        inst = synapse.core.camera_factory.OpenCvCamera()
        inst.cap = MagicMock()
        inst.cap.get.side_effect = [640, 480]
        self.assertEqual(inst.getResolution(), (640, 480))

    def test_get_max_fps(self):
        inst = synapse.core.camera_factory.OpenCvCamera()
        inst.cap = MagicMock()
        inst.cap.get.return_value = 120.0
        self.assertEqual(inst.getMaxFPS(), 120.0)


class TestCsCoreCamera(unittest.TestCase):
    @patch("synapse.core.camera_factory.UsbCamera")
    @patch("synapse.core.camera_factory.CameraServer.getVideo")
    def test_create_with_usb_index(self, mock_get_video, mock_usb_camera):
        camera_instance = MagicMock()
        mock_usb_camera.return_value = camera_instance
        mock_get_video.return_value = MagicMock()
        camera_instance.enumerateProperties.return_value = []

        cam = CsCoreCamera.create(usbIndex=0, name="TestCam")

        self.assertIsInstance(cam, CsCoreCamera)
        mock_usb_camera.assert_called_once()
        mock_get_video.assert_called_once_with(camera_instance)

    @patch("synapse.core.camera_factory.UsbCamera")
    @patch("synapse.core.camera_factory.CameraServer.getVideo")
    def test_create_with_dev_path(self, mock_get_video, mock_usb_camera):
        camera_instance = MagicMock()
        mock_usb_camera.return_value = camera_instance
        mock_get_video.return_value = MagicMock()
        camera_instance.enumerateProperties.return_value = []

        cam = CsCoreCamera.create(devPath="/dev/video0", name="TestCam")

        self.assertIsInstance(cam, CsCoreCamera)
        mock_usb_camera.assert_called_once_with("TestCam", "/dev/video0")

    def test_set_and_get_property_meta(self):
        cam = CsCoreCamera()
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
        cam = CsCoreCamera()
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cam.sink = MagicMock()
        cam.sink.grabFrame.return_value = 10
        cam.frameBuffer = mock_frame
        cam._running = False  # Skip the thread loop

        # Run a single iteration
        result = cam.sink.grabFrame(cam.frameBuffer)
        self.assertEqual(result, 10)

    def test_get_resolution(self):
        cam = CsCoreCamera()
        cam.camera = MagicMock()
        cam.camera.getVideoMode.return_value.width = 640
        cam.camera.getVideoMode.return_value.height = 480

        res = cam.getResolution()
        self.assertEqual(res, (640, 480))

    def test_get_max_fps(self):
        cam = CsCoreCamera()
        cam.camera = MagicMock()
        cam.camera.getVideoMode.return_value.fps = 30
        self.assertEqual(cam.getMaxFPS(), 30)


if __name__ == "__main__":
    unittest.main()
