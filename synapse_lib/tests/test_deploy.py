import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import paramiko
import pytest
from deploy import (add_files_to_tar, check_python3_install, deploy,
                    get_gitignore_specs)


# Mock SSH client and related methods
@pytest.fixture
def mock_ssh():
    ssh = MagicMock(spec=paramiko.SSHClient)
    ssh.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())
    return ssh


# Test for check_python3_install function
def test_check_python3_install(mock_ssh):
    mock_ssh.exec_command.return_value[
        1
    ].channel.recv_exit_status.return_value = 0  # Success
    assert check_python3_install(mock_ssh) is True

    mock_ssh.exec_command.return_value[
        1
    ].channel.recv_exit_status.return_value = 1  # Failure
    assert check_python3_install(mock_ssh) is False


def test_get_gitignore_specs():
    gitignore_spec = get_gitignore_specs(Path("."))
    assert gitignore_spec is not None
    assert len(gitignore_spec.patterns) > 0

    gitignore_spec = get_gitignore_specs(Path(__file__).parent)
    assert len(gitignore_spec.patterns) == 0


# Test for add_files_to_tar function
def test_add_files_to_tar(mock_ssh):
    mock_tar = MagicMock()
    mock_gitignore_spec = MagicMock()
    mock_gitignore_spec.match_file.return_value = (
        False  # Mock that no files are ignored
    )

    # Mock os.walk to simulate walking through the file system
    with patch("os.walk") as mock_walk:
        mock_walk.return_value = [
            ("root", ["dir"], ["file1.py", "file2.py"]),
        ]
        add_files_to_tar(mock_tar, "root", mock_gitignore_spec)

    assert mock_tar.add.call_count == 2  # Two files should be added to the tar


@patch("paramiko.SSHClient.exec_command")
@patch("paramiko.SSHClient.open_sftp")
def test_deploy(mock_sftp, mock_exec_command, mock_ssh):
    mock_ssh.exec_command.return_value[1].channel.recv_exit_status.return_value = 0
    mock_sftp.return_value.put.return_value = None

    deploy(mock_ssh, "/tmp/deploy.tar.gz", "/remote/path", "")

    mock_ssh.exec_command.assert_any_call("mkdir -p /remote/path")
    mock_ssh.exec_command.assert_any_call("tar -xzf /tmp/deploy.tar.gz -C /remote/path")
    mock_ssh.exec_command.assert_any_call("rm /tmp/deploy.tar.gz")
    mock_ssh.exec_command.any_call(
        "echo 'orangepi' | sudo -S systemctl restart synapse"
    )
