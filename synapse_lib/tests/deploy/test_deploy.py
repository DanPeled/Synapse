import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from deploy import (
    check_python3_install,
    get_gitignore_specs,
    compile_file,
    build_project,
    deploy,
)

from pathlib import Path


@patch("subprocess.run")
def test_check_python3_install(mock_run):
    # Test if python3 is installed
    mock_run.return_value.returncode = 0
    assert check_python3_install() is True

    # Test if python3 is not installed
    mock_run.return_value.returncode = 1
    assert check_python3_install() is False


def test_get_gitignore_specs():
    spec = get_gitignore_specs(Path(__file__).parent.resolve())
    assert len(spec.patterns) > 0

    spec = get_gitignore_specs(Path("/dummy/"))
    assert len(spec.patterns) == 0


@patch("subprocess.run")
def test_compile_file(mock_run):
    # Simulate successful compilation
    mock_run.return_value.returncode = 0
    assert compile_file("file.py") is True

    # Simulate compilation failure
    mock_run.return_value.returncode = 1
    assert compile_file("file.py") is False


@patch("os.walk")
@patch("deploy.compile_file")
def test_build_project(mock_compile, mock_os_walk):
    # Simulate a project with Python files
    mock_os_walk.return_value = [
        ("/path", [], ["file1.py", "file2.py"]),
    ]
    mock_compile.return_value = True
    build_ok, time = build_project()
    assert build_ok is True
    assert isinstance(time, timedelta)

    # Simulate no Python files
    mock_os_walk.return_value = [
        ("/path", [], ["file1.txt"]),
    ]
    build_ok, time = build_project()
    assert build_ok is False
    assert time == timedelta()


# Test deploy
@patch("paramiko.SSHClient")
@patch("time.sleep")
def test_deploy(mock_sleep, mock_ssh_client):
    hostname = "10.97.38.14"
    port = 22
    username = "orangepi"
    password = "orangepi"
    remote_path = "~/Synapse/"

    mock_ssh = MagicMock()
    mock_ssh_client.return_value = mock_ssh

    mock_ssh.exec_command.return_value = (
        MagicMock(read=MagicMock(return_value=b"Success")),
        None,
        None,
    )
    mock_ssh.open_sftp.return_value = MagicMock()

    # Assuming hostname, username, etc. are defined globally
    deploy(hostname, port, username, password, remote_path)

    # Ensure SSH client is used
    mock_ssh.connect.assert_called_once_with(hostname, port, username, password)
    mock_ssh.exec_command.assert_called()  # Make sure exec_command was called


# Run all tests
if __name__ == "__main__":
    pytest.main()
