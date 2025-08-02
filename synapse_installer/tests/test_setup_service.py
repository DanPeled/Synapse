# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import mock

import pytest
from synapse_installer.setup_service import (SERVICE_NAME, isServiceSetup,
                                             restartService)


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
