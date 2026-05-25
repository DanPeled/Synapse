# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import AsyncMock

import pytest
from synapse_net.generated.messages.v1 import MessageProto
from synapse_net.socketServer import (SocketEvent, WebSocketServer,
                                      getMessageDataFieldName)


def test_getMessageDataFieldName_valid():
    for f in MessageProto.__dataclass_fields__.values():
        datatype_name = f.type if isinstance(f.type, str) else f.type.__name__
        if datatype_name != "str":
            name = getMessageDataFieldName(datatype_name)
            assert isinstance(name, str)
            break


def test_getMessageDataFieldName_invalid():
    with pytest.raises(ValueError):
        getMessageDataFieldName("NonExistentTypeName")


@pytest.mark.asyncio
async def test_WebSocketServer_emit_and_callbacks():
    server = WebSocketServer("localhost", 8765)

    called_events = {}

    @server.on(SocketEvent.kConnect)
    async def on_connect(ws):
        called_events["connect"] = True

    @server.on(SocketEvent.kMessage)
    async def on_message(ws, msg):
        called_events["message"] = msg

    @server.on(SocketEvent.kDisconnect)
    async def on_disconnect(ws):
        called_events["disconnect"] = True

    @server.on(SocketEvent.kError)
    async def on_error(ws, err):
        called_events["error"] = err

    await server._emit(SocketEvent.kConnect, "client")
    assert called_events.get("connect") is True

    await server._emit(SocketEvent.kMessage, "client", "hello")
    assert called_events.get("message") == "hello"

    await server._emit(SocketEvent.kDisconnect, "client")
    assert called_events.get("disconnect") is True

    await server._emit(SocketEvent.kError, "client", "error_message")
    assert called_events.get("error") == "error_message"

    # test _emit with no callback registered (should not error)
    server.callbacks.pop(SocketEvent.kConnect, None)
    await server._emit(SocketEvent.kConnect, "client")


@pytest.mark.asyncio
async def test_handler_adds_and_removes_clients():
    server = WebSocketServer("localhost", 8765)

    websocket = AsyncMock()
    websocket.__aiter__.return_value = iter(["msg1", "msg2"])
    websocket.open = True

    events = []

    @server.on(SocketEvent.kConnect)
    async def on_connect(ws):
        events.append(("connect", ws))

    @server.on(SocketEvent.kMessage)
    async def on_message(ws, msg):
        events.append(("message", msg))

    @server.on(SocketEvent.kDisconnect)
    async def on_disconnect(ws):
        events.append(("disconnect", ws))

    await server.handler(websocket, "/path")

    assert websocket not in server.clients
    assert events[0][0] == "connect"
    assert events[1][0] == "message"
    assert events[2][0] == "message"
    assert events[-1][0] == "disconnect"


@pytest.mark.asyncio
async def test_sendToAll_and_sendToClient():
    server = WebSocketServer("localhost", 8765)

    client1 = AsyncMock()
    client1.open = True
    client1.send = AsyncMock()

    client2 = AsyncMock()
    client2.open = False

    server.clients.update({client1, client2})

    message = b"test"
    await server.sendToAll(message)
    client1.send.assert_awaited_once_with(message)
    client2.send.assert_not_called()

    client1.send.reset_mock()
    await server.sendToClient(client1, message)
    client1.send.assert_awaited_once_with(message)

    await server.sendToClient(client2, message)
    client2.send.assert_not_called()


def test_sendToAllSync_calls_asyncio_run(monkeypatch):
    server = WebSocketServer("localhost", 8765)

    called = {}

    async def mock_sendToAll(message):
        called["called"] = True

    monkeypatch.setattr(server, "sendToAll", mock_sendToAll)
    server.sendToAllSync(b"message")
    assert called.get("called") is True


@pytest.mark.asyncio
async def test_close_calls_close_and_wait_closed(monkeypatch):
    server = WebSocketServer("localhost", 8765)

    close_called = False
    wait_closed_called = False

    class DummyServer:
        def close(self):
            nonlocal close_called
            close_called = True

        async def wait_closed(self):
            nonlocal wait_closed_called
            wait_closed_called = True

    async def dummy_serve(handler, host, port):
        return DummyServer()

    monkeypatch.setattr("synapse_net.socketServer.serve", dummy_serve)

    server._server = await dummy_serve(server.handler, server.host, server.port)

    await server.close()
    assert close_called
    assert wait_closed_called
