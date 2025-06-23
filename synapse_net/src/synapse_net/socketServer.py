import asyncio
from dataclasses import fields
from enum import Enum
from typing import Callable, Dict, Optional, Set

import betterproto
import websockets

from .proto.v1 import MessageProto, MessageTypeProto


class SocketEvent(Enum):
    kConnect = "connect"
    kMessage = "message"
    kDisconnect = "disconnect"
    kError = "error"


def createMessage(
    messageType: MessageTypeProto,
    data: betterproto.Message,
) -> bytes:
    """
    While this is very clearly not a safe solution or a good one,
    it is good enough for now, and should be refactored later on
    in a more typesafe way
    """
    message = MessageProto()
    message.type = messageType

    datatypeName = type(data).__name__  # e.g. PipelineProto

    field_name = None
    for f in fields(type(message)):
        if f.type == datatypeName:
            field_name = f.name
            break
    else:
        raise ValueError(f"No matching field for type {datatypeName}")

    if field_name:
        if field_name in {f.name for f in fields(message)}:
            setattr(message, field_name, data)
        else:
            raise ValueError(
                f"Cannot find matching field in MessageProto for {field_name} (typeof={type(data).__name__})"
            )

    return message.SerializeToString()


class WebSocketServer:
    kInstance: Optional["WebSocketServer"] = None

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.callbacks: Dict[SocketEvent, Callable] = {}
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self._server = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def on(self, event: SocketEvent):
        def decorator(func: Callable):
            self.callbacks[event] = func
            return func

        return decorator

    async def _emit(self, event: SocketEvent, *args, **kwargs):
        if event in self.callbacks:
            await self.callbacks[event](*args, **kwargs)

    async def handler(self, websocket, path):
        self.clients.add(websocket)
        await self._emit(SocketEvent.kConnect, websocket)

        try:
            async for message in websocket:
                await self._emit(SocketEvent.kMessage, websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            await self._emit(SocketEvent.kError, websocket, str(e))
        finally:
            self.clients.remove(websocket)
            await self._emit(SocketEvent.kDisconnect, websocket)

    async def sendToAll(self, message: websockets.Data):
        if self.clients:
            await asyncio.gather(
                *(client.send(message) for client in self.clients if client.open)
            )

    def sendToAllSync(self, message: websockets.Data):
        asyncio.run(self.sendToAll(message))

    async def sendToClient(
        self, client: websockets.WebSocketServerProtocol, message: websockets.Data
    ):
        if client in self.clients and client.open:
            await client.send(message)

    def start(self):
        WebSocketServer.kInstance = self
        self._server = websockets.serve(self.handler, self.host, self.port)
        return self._server

    async def close(self):
        if self._server:
            server = await self._server
            server.close()
            await server.wait_closed()
