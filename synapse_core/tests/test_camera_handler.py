import unittest
from unittest.mock import MagicMock, patch

from synapse.core.runtime_handler import CameraHandler


class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()

    def test_getCamera_returns_correct_camera(self):
        mock_camera = MagicMock()
        self.handler.cameras[2] = mock_camera
        self.assertEqual(self.handler.getCamera(2), mock_camera)

    def test_publishFrame_pushes_to_output(self):
        camera = MagicMock()
        camera.cameraIndex = 0
        camera.getSetting.return_value = True

        frame = MagicMock()
        self.handler.streamSizes[0] = (320, 240)
        self.handler.streamOutputs[0] = MagicMock()
        self.handler.recordingOutputs[0] = MagicMock()

        with patch("synapse.core.runtime_handler.cv2.resize", return_value=frame):
            self.handler.publishFrame(frame, camera)
            self.handler.streamOutputs[0].putFrame.assert_called_with(frame)
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
