# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, mock_open, patch

from synapse.core.synapse import UIHandle


class TestUIHandle(unittest.TestCase):
    @patch("os.kill")
    def test_is_pid_running_true(self, mock_kill):
        self.assertTrue(UIHandle.isPIDRunning(1234))
        mock_kill.assert_called_with(1234, 0)

    @patch("os.kill", side_effect=OSError)
    def test_is_pid_running_false(self, mock_kill):
        self.assertFalse(UIHandle.isPIDRunning(1234))
        mock_kill.assert_called_with(1234, 0)

    @patch("subprocess.Popen")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid")
    @patch("pathlib.Path.touch")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("importlib.util.find_spec")
    def test_start_ui_with_invalid_pid(
        self, mock_find_spec, mock_exists, mock_touch, mock_open_file, mock_popen
    ):
        mock_spec = MagicMock()
        mock_spec.origin = "/fake/path/synapse_ui/__init__.py"
        mock_find_spec.return_value = mock_spec
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        UIHandle.startUI()

        mock_find_spec.assert_called_with("synapse_ui")
        mock_touch.assert_not_called()
        mock_popen.assert_called()


if __name__ == "__main__":
    unittest.main()
