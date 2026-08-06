# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, patch

from synapse.alert import alert
from synapse_net.generated.messages.v1 import AlertTypeProto


class TestAlertFunction(unittest.TestCase):
    def setUp(self):
        # Patch the WebSocketServer.kInstance before each test
        self.patcher = patch("synapse.alert.WebSocketServer")
        self.mock_ws_class = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.mock_ws_instance = MagicMock()
        self.mock_ws_class.kInstance = self.mock_ws_instance

    def test_alert_unspecified_type_raises(self):
        with self.assertRaises(AssertionError):
            alert(AlertTypeProto.UNSPECIFIED, "This should fail")

    def test_alert_sends_bytes_when_instance_exists(self):
        # Arrange
        alert_type = AlertTypeProto.INFO  # example type
        message = "Test message"

        # Act
        alert(alert_type, message)

        # Assert
        self.mock_ws_instance.sendToAllSync.assert_called_once()
        sent_msg = self.mock_ws_instance.sendToAllSync.call_args[0][0]
        self.assertIsInstance(sent_msg, bytes)
        self.assertGreater(len(sent_msg), 0)  # simple sanity check that bytes were sent

    def test_alert_does_nothing_when_instance_none(self):
        # Arrange
        self.mock_ws_class.kInstance = None

        # Act & Assert
        alert(AlertTypeProto.WARNING, "No instance exists")  # should not raise


if __name__ == "__main__":
    unittest.main()
