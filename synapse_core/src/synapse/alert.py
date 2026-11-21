# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from synapse_net.generated.messages.v1 import (
    AlertProto,
    AlertTypeProto,
    MessageTypeProto,
)
from synapse_net.socketServer import WebSocketServer, createMessage


def alert(alertType: AlertTypeProto, message: str) -> None:
    assert alertType != AlertTypeProto.UNSPECIFIED

    if WebSocketServer.kInstance is not None:
        alertProto = AlertProto(type=alertType, message=message)

        def buildMessage() -> bytes:
            return createMessage(MessageTypeProto.ALERT, alertProto)

        WebSocketServer.kInstance.sendToAllSync(
            buildMessage, coalesce_key=("alert", alertType)
        )
