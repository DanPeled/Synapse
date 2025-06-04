import unittest
from unittest.mock import MagicMock, patch

from synapse.core.runtime_handler import \
    CameraHandler  # adjust import if needed


class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()

    @patch("synapse.core.runtime_handler.GlobalSettings.getCameraConfigMap")
    def test_createCameras_adds_cameras(self, mock_getCameraConfigMap):
        mock_getCameraConfigMap.return_value = {
            0: MagicMock(path="/dev/video0", name="TestCam")
        }

        with patch("synapse.core.runtime_handler.CameraFactory.create") as mock_create:
            mock_camera = MagicMock()
            mock_camera.isConnected.return_value = True
            mock_create.return_value = mock_camera

            self.handler.createCameras()
            self.assertIn(0, self.handler.cameras)

    @patch("synapse.core.runtime_handler.GlobalSettings.getCameraConfig")
    @patch("synapse.core.runtime_handler.cs.CameraServer.putVideo")
    def test_getCameraOutputs_with_config(self, mock_putVideo, mock_getCameraConfig):
        mock_getCameraConfig.return_value = MagicMock(streamRes=(640, 480))
        self.handler.cameras = {0: MagicMock()}
        mock_putVideo.return_value = MagicMock()

        outputs = self.handler.getCameraOutputs()
        self.assertIn(0, outputs)
        self.assertEqual(self.handler.streamSizes[0], (640, 480))

    def test_addCamera_invalid_config(self):
        self.handler.cameraBindings = {}  # empty config
        result = self.handler.addCamera(1)
        self.assertFalse(result)

    def test_getCamera_returns_correct_camera(self):
        mock_camera = MagicMock()
        self.handler.cameras[2] = mock_camera
        self.assertEqual(self.handler.getCamera(2), mock_camera)

    @patch("synapse.core.runtime_handler.cv2.VideoWriter")
    def test_generateRecordingOutputs_valid(self, mock_writer):
        camera_mock = MagicMock()
        camera_mock.getResolution.return_value = (320, 240)
        self.handler.cameras = {0: camera_mock}

        writer_instance = MagicMock()
        mock_writer.return_value = writer_instance

        result = self.handler.generateRecordingOutputs([0])
        self.assertEqual(result[0], writer_instance)

    def test_publishFrame_pushes_to_output(self):
        camera = MagicMock()
        camera.cameraIndex = 0
        camera.getSetting.return_value = True

        frame = MagicMock()
        self.handler.streamSizes[0] = (320, 240)
        self.handler.outputs[0] = MagicMock()
        self.handler.recordingOutputs[0] = MagicMock()

        with patch("synapse.core.runtime_handler.cv2.resize", return_value=frame):
            self.handler.publishFrame(frame, camera)
            self.handler.outputs[0].putFrame.assert_called_with(frame)
            self.handler.recordingOutputs[0].write.assert_called_with(frame)

    def test_cleanup_closes_resources(self):
        mock_record = MagicMock()
        mock_camera = MagicMock()

        self.handler.recordingOutputs = {0: mock_record}
        self.handler.cameras = {0: mock_camera}

        self.handler.cleanup()
        mock_record.release.assert_called_once()
        mock_camera.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
