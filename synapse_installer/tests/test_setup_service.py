from unittest import mock

import pytest
from synapse_installer.setup_service import (SERVICE_NAME, isServiceSetup,
                                             restartService,
                                             setupServiceOnConnectedClient)


@pytest.fixture
def mock_ssh_client():
    return mock.MagicMock()


@pytest.fixture
def mock_sftp_client():
    return mock.MagicMock()


def test_is_service_setup_exists(mock_ssh_client):
    mock_stdout = mock.Mock()
    mock_stdout.read.return_value = b"exists\n"
    mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)

    result = isServiceSetup(mock_ssh_client, SERVICE_NAME)
    assert result is True
    mock_ssh_client.exec_command.assert_called_once()


def test_is_service_setup_missing(mock_ssh_client):
    mock_stdout = mock.Mock()
    mock_stdout.read.return_value = b"missing\n"
    mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)

    result = isServiceSetup(mock_ssh_client, SERVICE_NAME)
    assert result is False


def test_restart_service(mock_ssh_client):
    mock_stdout = mock.Mock()
    mock_stdout.read.return_value = b"service restarted"
    mock_stderr = mock.Mock()
    mock_stderr.read.return_value = b""

    mock_ssh_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

    stdout, stderr = restartService(mock_ssh_client, SERVICE_NAME)
    assert "service restarted" in stdout
    assert stderr == ""


@mock.patch("tempfile.NamedTemporaryFile")
@mock.patch("os.remove")
def test_setup_service_on_connected_client(
    mock_os_remove, mock_tempfile, mock_ssh_client, mock_sftp_client
):
    # Prepare mocked stdout for Python path discovery
    python_path = "/usr/bin/python3.10"
    mock_stdout = mock.Mock()
    mock_stdout.read.return_value = python_path.encode()
    mock_stderr = mock.Mock()
    mock_stderr.read.return_value = b""

    # Fake temp file
    fake_temp_file = mock.MagicMock()
    fake_temp_file.__enter__.return_value.name = "/tmp/fakefile"
    mock_tempfile.return_value = fake_temp_file

    # Setup exec_command side effect
    def exec_command_side_effect(cmd):
        if "compgen" in cmd:
            return None, mock_stdout, mock_stderr
        elif "sudo" in cmd:
            out = mock.Mock()
            err = mock.Mock()
            out.read.return_value = b""
            err.read.return_value = b""
            return None, out, err
        return None, mock.Mock(read=lambda: b""), mock.Mock(read=lambda: b"")

    mock_ssh_client.exec_command.side_effect = exec_command_side_effect
    mock_ssh_client.open_sftp.return_value = mock_sftp_client

    setupServiceOnConnectedClient(mock_ssh_client, "user")

    # Ensure service file was transferred and chmod was called
    mock_sftp_client.chmod.assert_called_once_with("/home/user/main.py", 0o755)
    mock_sftp_client.put.assert_called_once_with(
        "/tmp/fakefile", f"/home/user/{SERVICE_NAME}.service"
    )
    mock_sftp_client.close.assert_called_once()
    mock_os_remove.assert_called_once_with("/tmp/fakefile")
