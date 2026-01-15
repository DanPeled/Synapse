# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

import pytest
from synapse_net.stdout_streamer import (JournalctlNotAvailableError,
                                         SshConnectionError,
                                         SystemdServiceLogStreamer)


@pytest.fixture
def mock_ssh_client():
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    return client


def test_init_raises_on_no_transport():
    client = MagicMock()
    client.get_transport.return_value = None
    with pytest.raises(SshConnectionError):
        SystemdServiceLogStreamer(client, "myservice")


def test_check_journalctl_installed(mock_ssh_client):
    channel_mock = MagicMock()
    channel_mock.recv_exit_status.return_value = 0

    mock_ssh_client.get_transport.return_value.open_session.return_value = channel_mock

    streamer = SystemdServiceLogStreamer(mock_ssh_client, "myservice")
    # Should not raise
    streamer._checkJournalctl()
    channel_mock.exec_command.assert_called_with("command -v journalctl")
    channel_mock.close.assert_called_once()


def test_check_journalctl_not_installed_raises(mock_ssh_client):
    channel_mock = MagicMock()
    channel_mock.recv_exit_status.return_value = 1  # Simulate not installed

    mock_ssh_client.get_transport.return_value.open_session.return_value = channel_mock

    streamer = SystemdServiceLogStreamer(mock_ssh_client, "myservice")
    with pytest.raises(JournalctlNotAvailableError):
        streamer._checkJournalctl()


def test_build_journalctl_command_no_sudo():
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport

    streamer = SystemdServiceLogStreamer(client, "myservice")
    cmd = streamer._buildJournalctlCommand()
    assert cmd == "journalctl -u myservice --output=cat -f"


def test_build_journalctl_command_with_sudo_and_user_service():
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport

    streamer = SystemdServiceLogStreamer(
        client, "myservice", useSudo=True, userService=True
    )
    cmd = streamer._buildJournalctlCommand()
    assert cmd == "sudo -n journalctl --user -u myservice --output=cat -f"
