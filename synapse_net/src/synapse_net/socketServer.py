import asyncio
import traceback
from dataclasses import fields
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union

import betterproto
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve
from websockets.typing import Data

from .proto.v1 import MessageProto, MessageTypeProto


class SocketEvent(Enum):
    kConnect = "connect"
    kMessage = "message"
    kDisconnect = "disconnect"
    kError = "error"


@lru_cache
def getMessageDataFieldName(datatypeName: str) -> str:
    for f in fields(MessageProto):
        if f.type == datatypeName:
            return f.name
    raise ValueError(f"No matching field for type {datatypeName}")


def createMessage(
    messageType: MessageTypeProto,
    data: Union[betterproto.Message, List[betterproto.Message]],
) -> bytes:
    message = MessageProto()
    message.type = messageType

    field_name = getMessageDataFieldName(type(data).__name__)
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
        self.callbacks: Dict[SocketEvent, Callable[..., Coroutine]] = {}
        self.clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self.loop: Optional[Any] = None

    def on(self, event: SocketEvent):
        def decorator(func: Callable[..., Coroutine]):
            self.callbacks[event] = func
            return func

        return decorator

    async def _emit(self, event: SocketEvent, *args, **kwargs):
        if event in self.callbacks:
            await self.callbacks[event](*args, **kwargs)

    async def handler(self, websocket: WebSocketServerProtocol, path: str):
        self.clients.add(websocket)
        await self._emit(SocketEvent.kConnect, websocket)

        try:
            async for message in websocket:
                await self._emit(SocketEvent.kMessage, websocket, message)
        except ConnectionClosed:
            pass
        except Exception as error:
            errString = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            await self._emit(SocketEvent.kError, websocket, errString)
        finally:
            self.clients.remove(websocket)
            await self._emit(SocketEvent.kDisconnect, websocket)

    async def sendToAll(self, message: Data):
        if self.clients:
            await asyncio.gather(
                *(client.send(message) for client in self.clients if client.open)
            )

    def sendToAllSync(self, message: Data):
        if self.loop and self.loop.is_running():
            # Submit to the existing background event loop
            asyncio.run_coroutine_threadsafe(self.sendToAll(message), self.loop)
        else:
            # Run in a temporary event loop (e.g. during test or before full setup)
            asyncio.run(self.sendToAll(message))

    async def sendToClient(
        self,
        client: WebSocketServerProtocol,
        message: Data,
    ):
        if client in self.clients and client.open:
            await client.send(message)

    def start(self):
        WebSocketServer.kInstance = self
        return serve(self.handler, self.host, self.port)

    async def close(self):
        if self._server:
            # If _server is a coroutine, await it first
            if asyncio.iscoroutine(self._server):
                self._server = await self._server
            self._server.close()
            await self._server.wait_closed()
