# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from synapse.core.camera_handler import CameraHandler


class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()

    def test_getCamera_returns_correct_camera(self):
        mock_camera = MagicMock()
        self.handler.cameraHandles[2] = mock_camera
        self.assertEqual(self.handler.getCameraHandle(2), mock_camera)

    # TODO: add camera tests


class TestPublishFrame(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()
        self.handler.publishInterval = 0.0
        self.handler.streamSizes[0] = (320, 240)

        self.handle = MagicMock()
        self.handle.cameraIndex = 0
        self.handle.name = "cam0"

        self.output = MagicMock()
        self.handler.streamOutputs[0] = self.output

    def test_skips_resize_when_frame_matches_stream_size(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        with patch("synapse.core.camera_handler.cv2.resize") as resize:
            self.handler.publishFrame(frame, self.handle)

        resize.assert_not_called()
        self.output.putFrame.assert_called_once_with(frame)

    def test_resizes_and_reuses_destination_buffer(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.handler.publishFrame(frame, self.handle)
        first = self.output.putFrame.call_args[0][0]

        self.handler.publishFrame(frame, self.handle)
        second = self.output.putFrame.call_args[0][0]

        self.assertEqual(first.shape, (240, 320, 3))
        self.assertIs(first, second)

    def test_recording_resizes_and_releases_buffer(self):
        self.handler.recordingStatus[0] = True
        self.handler.recordingResolutions[0] = (320, 240)
        self.handler.cameraHandles[0] = MagicMock()

        writer = MagicMock()
        self.handler.recordingOutputs[0] = writer
        self.handler.recordFileNames[0] = "records/test.mp4"

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.handler.publishFrame(frame, self.handle)

        written = writer.write.call_args[0][0]
        self.assertEqual(written.shape, (240, 320, 3))
        self.assertIn(0, self.handler._recordFrameBuffers)

        # Stopping recording should free the cached destination buffer.
        self.handler.recordingStatus[0] = False
        self.handler.publishFrame(frame, self.handle)
        self.assertNotIn(0, self.handler._recordFrameBuffers)


if __name__ == "__main__":
    unittest.main()
