# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock

from synapse.core.runtime_handler import CameraHandler


class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()

    def test_getCamera_returns_correct_camera(self):
        mock_camera = MagicMock()
        self.handler.cameras[2] = mock_camera
        self.assertEqual(self.handler.getCamera(2), mock_camera)

    # TODO: add camera tests


if __name__ == "__main__":
    unittest.main()
