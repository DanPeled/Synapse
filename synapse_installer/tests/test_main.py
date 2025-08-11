# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from unittest.mock import patch

from synapse_installer.__main__ import main


class TestMain(unittest.TestCase):
    @patch("synapse_installer.deploy.setupAndRunDeploy")
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    def test_deploy_command(
        self, mock_sync, mock_createProject, mock_setupAndRunDeploy
    ):
        test_argv = ["prog", "deploy", "extra", "args"]
        with patch.object(sys, "argv", test_argv):
            main()
        mock_setupAndRunDeploy.assert_called_once_with(test_argv[1:])
        mock_createProject.assert_not_called()
        mock_sync.assert_not_called()

    @patch("synapse_installer.deploy.setupAndRunDeploy")
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    def test_create_command(
        self, mock_sync, mock_createProject, mock_setupAndRunDeploy
    ):
        test_argv = ["prog", "create"]
        with patch.object(sys, "argv", test_argv):
            main()
        mock_createProject.assert_called_once()
        mock_setupAndRunDeploy.assert_not_called()
        mock_sync.assert_not_called()

    @patch("synapse_installer.deploy.setupAndRunDeploy")
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    def test_sync_command(self, mock_sync, mock_createProject, mock_setupAndRunDeploy):
        test_argv = ["prog", "sync", "arg1"]
        with patch.object(sys, "argv", test_argv):
            main()
        mock_sync.assert_called_once_with(test_argv[1:])
        mock_createProject.assert_not_called()
        mock_setupAndRunDeploy.assert_not_called()

    @patch("synapse_installer.deploy.setupAndRunDeploy")
    @patch("synapse_installer.create.createProject")
    @patch("synapse_installer.sync.sync")
    def test_install_command(
        self, mock_sync, mock_createProject, mock_setupAndRunDeploy
    ):
        test_argv = ["prog", "install", "arg1"]
        with patch.object(sys, "argv", test_argv):
            main()
        mock_sync.assert_called_once_with(test_argv[1:])
        mock_setupAndRunDeploy.assert_called_once_with(test_argv[1:])
        mock_createProject.assert_not_called()


if __name__ == "__main__":
    unittest.main()
