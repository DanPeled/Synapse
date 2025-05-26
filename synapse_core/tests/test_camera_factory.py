import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from synapse.core.camera_factory import (CameraFactory, CsCoreCamera,
                                         OpenCvCamera, opencvToCscoreProp)


class TestCsCoreCamera(unittest.TestCase):
    @patch("synapse.core.camera_factory.UsbCamera")
    @patch("synapse.core.camera_factory.CameraServer")
    def test_create_with_usb_index(self, mock_camera_server, mock_usb_camera):
        mock_camera = MagicMock()
        mock_usb_camera.return_value = mock_camera

        # Mock getVideo
        mock_sink = MagicMock()
        mock_camera_server.getVideo.return_value = mock_sink

        # Mock enumerateProperties
        mock_prop = MagicMock()
        mock_prop.getName.return_value = "brightness"
        mock_prop.getMin.return_value = 0
        mock_prop.getMax.return_value = 100
        mock_prop.getDefault.return_value = 50
        mock_camera.enumerateProperties.return_value = [mock_prop]

        camera = CsCoreCamera.create(usbIndex=0)

        self.assertEqual(camera.property_meta["brightness"]["min"], 0)
        self.assertEqual(camera.sink, mock_sink)
        mock_usb_camera.assert_called_once()
        mock_camera_server.getVideo.assert_called_with(mock_camera)

    def test_set_property_within_range(self):
        camera = CsCoreCamera()
        camera.camera = MagicMock()

        # Fake property metadata
        camera.property_meta = {"brightness": {"min": 0, "max": 100, "default": 50}}

        # Mock camera.getProperty("brightness").set()
        mock_prop = MagicMock()
        camera.camera.getProperty.return_value = mock_prop

        camera.setProperty("brightness", 75)
        mock_prop.set.assert_called_with(75)

    def test_get_property(self):
        camera = CsCoreCamera()
        camera.camera = MagicMock()

        mock_prop = MagicMock()
        mock_prop.get.return_value = 42
        camera.camera.getProperty.return_value = mock_prop

        val = camera.getProperty("brightness")
        self.assertEqual(val, 42)

    def test_grab_frame_success(self):
        camera = CsCoreCamera()
        camera.sink = MagicMock()
        camera.camera = MagicMock()

        dummy_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        camera.frameBuffer = dummy_frame
        camera.sink.grabFrame.return_value = (1, dummy_frame)

        ok, frame = camera.grabFrame()
        self.assertTrue(ok)
        self.assertIsNotNone(frame)


class TestOpenCvCamera(unittest.TestCase):
    @patch("synapse.core.camera_factory.cv2.VideoCapture")
    def test_create_with_usb_index(self, mock_VideoCapture):
        mock_cap = MagicMock()
        mock_VideoCapture.return_value = mock_cap

        camera = OpenCvCamera.create(usbIndex=0)

        mock_VideoCapture.assert_called_with(0)
        self.assertEqual(camera.cap, mock_cap)

    @patch("synapse.core.camera_factory.cv2.VideoCapture")
    def test_create_with_dev_path(self, mock_VideoCapture):
        mock_cap = MagicMock()
        mock_VideoCapture.return_value = mock_cap

        camera = OpenCvCamera.create(devPath="/dev/video0")

        mock_VideoCapture.assert_called_with("/dev/video0", cv2.CAP_V4L2)
        self.assertEqual(camera.cap, mock_cap)

    def test_grab_frame(self):
        camera = OpenCvCamera()
        mock_cap = MagicMock()
        dummy_frame = object()
        mock_cap.read.return_value = (True, dummy_frame)
        camera.cap = mock_cap

        ok, frame = camera.grabFrame()
        self.assertTrue(ok)
        self.assertEqual(frame, dummy_frame)

    def test_is_connected(self):
        camera = OpenCvCamera()
        camera.cap = MagicMock()
        camera.cap.isOpened.return_value = True

        self.assertTrue(camera.isConnected())
        camera.cap.isOpened.assert_called_once()

    def test_close(self):
        camera = OpenCvCamera()
        camera.cap = MagicMock()

        camera.close()
        camera.cap.release.assert_called_once()

    @patch("synapse.core.camera_factory.cscoreToOpenCVProp")
    def test_set_property(self, mock_cscoreToOpenCVProp):
        camera = OpenCvCamera()
        camera.cap = MagicMock()

        mock_cscoreToOpenCVProp.return_value = cv2.CAP_PROP_BRIGHTNESS
        camera.setProperty(opencvToCscoreProp(cv2.CAP_PROP_BRIGHTNESS) or "", 50)
        self.assertEqual(
            camera.getProperty(opencvToCscoreProp(cv2.CAP_PROP_BRIGHTNESS) or ""), None
        )

    @patch("synapse.core.camera_factory.cscoreToOpenCVProp")
    def test_get_property(self, mock_cscoreToOpenCVProp):
        camera = OpenCvCamera()
        camera.cap = MagicMock()

        result = camera.getProperty(opencvToCscoreProp(cv2.CAP_PROP_CONTRAST) or "")
        self.assertEqual(result, None)

    def test_set_video_mode(self):
        camera = OpenCvCamera()
        camera.cap = MagicMock()

        camera.setVideoMode(fps=30, width=640, height=480)
        camera.cap.set.assert_any_call(cv2.CAP_PROP_FPS, 30)
        camera.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def test_get_resolution(self):
        camera = OpenCvCamera()
        camera.cap = MagicMock()
        camera.cap.get.side_effect = [640, 480]

        res = camera.getResolution()
        self.assertEqual(res, (640, 480))
        camera.cap.get.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH)
        camera.cap.get.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT)


class TestCameraFactory(unittest.TestCase):
    @patch.object(OpenCvCamera, "create")
    def test_create_opencv_camera(self, mock_create):
        mock_cam_instance = MagicMock()
        mock_create.return_value = mock_cam_instance

        cam = CameraFactory.create(
            cameraType=OpenCvCamera,
            cameraIndex=1,
            devPath="/dev/video0",
            name="TestCam",
        )

        mock_create.assert_called_once_with(
            devPath="/dev/video0", usbIndex=None, name="TestCam"
        )
        mock_cam_instance.setIndex.assert_called_once_with(1)
        self.assertEqual(cam, mock_cam_instance)

    @patch.object(CsCoreCamera, "create")
    def test_create_cscore_camera(self, mock_create):
        mock_cam_instance = MagicMock()
        mock_create.return_value = mock_cam_instance

        cam = CameraFactory.create(
            cameraType=CsCoreCamera, cameraIndex=2, usbIndex=0, name="UsbCam"
        )

        mock_create.assert_called_once_with(devPath=None, usbIndex=0, name="UsbCam")
        mock_cam_instance.setIndex.assert_called_once_with(2)
        self.assertEqual(cam, mock_cam_instance)
