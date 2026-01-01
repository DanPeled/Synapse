# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from synapse_net.proto.v1 import AlertProto, AlertTypeProto, MessageTypeProto
from synapse_net.socketServer import WebSocketServer, createMessage


def alert(alertType: AlertTypeProto, message: str) -> None:
    assert alertType != AlertTypeProto.UNSPECIFIED

    if WebSocketServer.kInstance is not None:
        msg = createMessage(
            MessageTypeProto.ALERT, AlertProto(type=alertType, message=message)
        )
        WebSocketServer.kInstance.sendToAllSync(msg)
