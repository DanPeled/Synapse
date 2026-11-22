# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

from ntcore import EventFlags
from synapse_net.nt_client import NtClient, teamNumberToIP


class FakeConnectionInfo:
    remote_ip = "10.2.4.2"


def makeConnectedEvent() -> MagicMock:
    event = MagicMock()
    event.data = FakeConnectionInfo()
    event.is_.side_effect = lambda flag: flag == EventFlags.CONNECTED
    return event


def test_teamNumberToIP() -> None:
    assert teamNumberToIP(254, 5) == "10.2.54.5"
    assert teamNumberToIP(1, 1) == "10.0.01.1"
    assert teamNumberToIP(9999, 255) == "10.99.99.255"


def test_setup_client_wakes_on_connection_event() -> None:
    mock_instance = MagicMock()
    mock_instance.isConnected.return_value = False

    def addConnectionListener(initialNotify, listener):
        listener(makeConnectedEvent())

    mock_instance.addConnectionListener.side_effect = addConnectionListener

    with (
        patch("synapse_net.nt_client.ConnectionInfo", FakeConnectionInfo),
        patch("synapse_net.nt_client.NetworkTableInstance") as mock_nt_instance,
    ):
        mock_nt_instance.getDefault.return_value = mock_instance
        client = NtClient()
        result = client.setup(
            teamNumber=1234, name="testClient", isServer=False, isSim=True
        )

    assert result is True
    mock_instance.setServer.assert_called_with("127.0.0.1")
    mock_instance.startClient.assert_called_with("testClient")
    mock_instance.addConnectionListener.assert_called_once()


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
    mock_server_instance.startClient.assert_called_with("serverNode")
