import unittest
from unittest.mock import patch, MagicMock
from synapse.nt_client import NtClient


class TestNtClient(unittest.TestCase):
    @patch("synapse.nt_client.NetworkTableInstance")
    @patch("synapse.nt_client.log")
    @patch("synapse.nt_client.err")
    def test_setup_server(self, mock_err, mock_log, mock_nt_instance):
        mock_nt_instance.getDefault.return_value = MagicMock()
        mock_nt_instance.create.return_value = MagicMock()

        client = NtClient()
        result = client.setup(
            teamNumber=1234, name="TestServer", isServer=True, isSim=False
        )

        self.assertTrue(result)
        mock_log.assert_called_with("Server started with name TestServer.")
        mock_nt_instance.create().startServer.assert_called_with("127.0.0.1")
        mock_nt_instance.getDefault().setServer.assert_called_with("127.0.0.1")

    @patch("synapse.nt_client.NetworkTableInstance")
    @patch("synapse.nt_client.log")
    @patch("synapse.nt_client.err")
    def test_setup_client(self, mock_err, mock_log, mock_nt_instance):
        mock_nt_instance.getDefault.return_value = MagicMock()

        client = NtClient()
        result = client.setup(
            teamNumber=1234, name="TestClient", isServer=False, isSim=False
        )

        self.assertTrue(result)
        mock_nt_instance.getDefault().setServerTeam.assert_called_with(1234)
        mock_nt_instance.getDefault().startClient4.assert_called_with("TestClient")
