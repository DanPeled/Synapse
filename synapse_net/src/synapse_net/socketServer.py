import asyncio
from enum import Enum
from re import sub
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

    def camelToSnake(name):
        # Converts 'PipelineProto' -> 'pipeline_proto'
        s1 = sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    datatypeName = type(data).__name__  # e.g. PipelineProto
    snakeName = camelToSnake(datatypeName)  # e.g. pipeline_proto

    possibleFieldNames = [
        snakeName.replace("_proto", ""),
        snakeName.replace("_proto", "") + "_info",
        snakeName.replace("_proto", "") + "_metrics",
    ]

    for field_name in possibleFieldNames:
        if hasattr(message, field_name):
            setattr(message, field_name, data)
            break
    else:
        raise ValueError(
            f"Cannot find matching field in MessageProto for {datatypeName}"
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
