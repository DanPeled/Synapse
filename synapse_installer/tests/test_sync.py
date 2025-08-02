# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, patch

from synapse_installer.sync import syncRequirements


class TestSyncRequirements(unittest.TestCase):
    @patch("paramiko.SSHClient")
    @patch("importlib.metadata.distribution")
    def test_skip_already_installed_packages(
        self, mock_distribution, mock_ssh_client_cls
    ):
        # Mock distribution.requires to return a list of requirements
        mock_distribution.return_value.requires = ["package1", "package2"]

        # Setup mocks for SSHClient
        mock_client = MagicMock()
        mock_ssh_client_cls.return_value = mock_client

        mock_client.connect.return_value = None
        mock_client.get_transport.return_value = True

        # Mock pip freeze output: package1 is installed, package2 is not
        mock_stdout_freeze = MagicMock()
        mock_stdout_freeze.read.return_value = b"package1==1.0.0\n"

        def exec_command_side_effect(cmd, *args, **kwargs):
            if "pip freeze" in cmd:
                return (None, mock_stdout_freeze, MagicMock())
            else:
                # For pip install commands: simulate empty stderr (no error)
                mock_stderr = MagicMock()
                mock_stderr.read.return_value = b""
                return (None, MagicMock(), mock_stderr)

        mock_client.exec_command.side_effect = exec_command_side_effect

        # Call the function — package1 should be skipped, package2 installed
        syncRequirements("host", "password", "1.2.3.4", ["package1", "package2"])

        calls = [call[0][0] for call in mock_client.exec_command.call_args_list]

        self.assertIn("pip freeze", calls[0])
        self.assertTrue(any("pip install package2" in c for c in calls))
        self.assertFalse(any("pip install package1" in c for c in calls[1:]))

    @patch("paramiko.SSHClient")
    @patch("importlib.metadata.distribution")
    def test_install_failure_logs_error(self, mock_distribution, mock_ssh_client_cls):
        mock_distribution.return_value.requires = ["badpackage"]

        mock_client = MagicMock()
        mock_ssh_client_cls.return_value = mock_client

        mock_client.connect.return_value = None
        mock_client.get_transport.return_value = True

        # pip freeze empty -> no packages installed
        mock_stdout_freeze = MagicMock()
        mock_stdout_freeze.read.return_value = b""

        # Simulate error on install
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"ERROR: Could not install package"

        def exec_command_side_effect(cmd, *args, **kwargs):
            if "pip freeze" in cmd:
                return (None, mock_stdout_freeze, MagicMock())
            else:
                return (None, MagicMock(), mock_stderr)

        mock_client.exec_command.side_effect = exec_command_side_effect

        with (
            patch("synapse.log.err") as mock_log_err,
            patch("builtins.print") as _,
            patch("synapse_installer.deploy.fprint") as _,
        ):
            syncRequirements("host", "password", "1.2.3.4", ["badpackage"])

        # No exception raised, so no call to log.err expected here
        mock_log_err.assert_not_called()


if __name__ == "__main__":
    unittest.main()
