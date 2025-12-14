# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from unittest.mock import patch

from synapse_installer.__main__ import main


class TestMain(unittest.TestCase):
    # ----------------------- create command -----------------------
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    @patch("synapse_installer.deploy.setupAndRunDeploy")
    def test_create_command(self, mock_setup, mock_sync, mock_create):
        test_argv = ["prog", "create"]
        with patch.object(sys, "argv", test_argv), patch("sys.exit") as mock_exit:
            main()
        mock_create.assert_called_once()
        mock_sync.assert_not_called()
        mock_setup.assert_not_called()
        mock_exit.assert_called_once_with(0)

    # ----------------------- deploy command -----------------------
    @patch("synapse_installer.deploy.setupAndRunDeploy")
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    def test_deploy_command(self, mock_sync, mock_create, mock_setup):
        test_argv = ["prog", "deploy", "extra", "args"]
        with patch.object(sys, "argv", test_argv), patch("sys.exit") as mock_exit:
            main()
        mock_setup.assert_called_once_with(test_argv[2:])  # args after command
        mock_create.assert_not_called()
        mock_sync.assert_not_called()
        mock_exit.assert_called_once_with(0)

    # ----------------------- sync command -----------------------
    @patch("synapse_installer.sync.sync", return_value=0)
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.deploy.setupAndRunDeploy")
    def test_sync_command(self, mock_setup, mock_create, mock_sync):
        test_argv = ["prog", "sync", "arg1"]
        with patch.object(sys, "argv", test_argv), patch("sys.exit") as mock_exit:
            main()
        mock_sync.assert_called_once_with(test_argv[2:])
        mock_create.assert_not_called()
        mock_setup.assert_not_called()
        mock_exit.assert_called_once_with(0)

    # ----------------------- install command -----------------------
    @patch("synapse_installer.sync.sync", return_value=0)
    @patch("synapse_installer.deploy.setupAndRunDeploy", return_value=0)
    def test_install_command(self, mock_setup, mock_sync):
        test_argv = ["prog", "install", "arg1"]
        with patch.object(sys, "argv", test_argv), patch("sys.exit") as mock_exit:
            main()
        mock_sync.assert_called_once_with(test_argv[2:])
        mock_setup.assert_called_once_with(test_argv[2:])
        mock_exit.assert_called_once_with(0)

    # ----------------------- device add command -----------------------
    @patch("synapse_installer.deploy.addDeviceConfig")
    def test_device_add_command(self, mock_add):
        test_argv = ["prog", "device", "add"]
        with (
            patch.object(sys, "argv", test_argv),
            patch("sys.exit") as mock_exit,
            patch("pathlib.Path.exists", return_value=True),
        ):
            main()
        mock_add.assert_called_once()
        mock_exit.assert_called_once_with(0)

    # ----------------------- device unknown action -----------------------
    @patch("builtins.print")
    def test_device_unknown_action(self, mock_print):
        test_argv = ["prog", "device", "remove"]
        with (
            patch.object(sys, "argv", test_argv),
            patch("sys.exit") as mock_exit,
            patch("pathlib.Path.exists", return_value=True),
        ):
            main()
        mock_exit.assert_called_once_with(1)

    # ----------------------- device no config -----------------------
    @patch("builtins.print")
    def test_device_no_config(self, mock_print):
        test_argv = ["prog", "device", "add"]
        with (
            patch.object(sys, "argv", test_argv),
            patch("sys.exit") as mock_exit,
            patch("pathlib.Path.exists", return_value=False),
        ):
            main()
        mock_exit.assert_called_once_with(1)

    # ----------------------- help command -----------------------
    @patch("builtins.print")
    def test_help_shows_help_and_exits(self, mock_print):
        for flag in ["-h", "--help"]:
            test_argv = ["prog", flag]
            with patch.object(sys, "argv", test_argv), patch("sys.exit") as _:
                main()
            mock_print.assert_any_call(unittest.mock.ANY)  # pyright: ignore

    # ----------------------- unknown command -----------------------
    @patch("builtins.print")
    def test_unknown_command_exits_with_error(self, mock_print):
        test_argv = ["prog", "unknowncmd"]
        with patch.object(sys, "argv", test_argv), patch("sys.exit") as mock_exit:
            main()
        mock_print.assert_any_call(unittest.mock.ANY)  # pyright: ignore
        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
