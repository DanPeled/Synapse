# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

from synapse_net.nt_client import NtClient, teamNumberToIP


def test_teamNumberToIP() -> None:
    assert teamNumberToIP(254, 5) == "10.2.54.5"
    assert teamNumberToIP(1, 1) == "10.0.01.1"
    assert teamNumberToIP(9999, 255) == "10.99.99.255"


@patch("synapse_net.nt_client.NetworkTableInstance")
@patch("synapse_net.nt_client.time.sleep", return_value=None)
def test_setup_client_success(mock_sleep, mock_nt_instance) -> None:
    mock_instance = MagicMock()
    mock_instance.isConnected.side_effect = [
        False,
        False,
        True,
    ]  # connects after 2 tries
    mock_nt_instance.getDefault.return_value = mock_instance

    client = NtClient()
    result = client.setup(
        teamNumber=1234, name="testClient", isServer=False, isSim=True
    )

    assert result is True
    mock_instance.setServer.assert_called_with("127.0.0.1")
    mock_instance.startClient4.assert_called_with("testClient")


@patch("synapse_net.nt_client.NetworkTableInstance")
def test_setup_server(mock_nt_instance) -> None:
    mock_server_instance = MagicMock()
    mock_nt_instance.create.return_value = mock_server_instance
    mock_nt_instance.getDefault.return_value = mock_server_instance
    mock_server_instance.isConnected.return_value = True

    client = NtClient()
    result = client.setup(teamNumber=0, name="serverNode", isServer=True, isSim=False)

    assert result is True
    mock_server_instance.startServer.assert_called_with("127.0.0.1")
    mock_server_instance.setServer.assert_called_with("127.0.0.1")
    mock_server_instance.startClient4.assert_called_with("serverNode")
