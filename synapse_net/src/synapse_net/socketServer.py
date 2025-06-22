import asyncio
import websockets
from enum import Enum
from typing import Callable, Dict, Optional, Set
from synapse_net.proto.v1 import message_pb2
from google.protobuf.any_pb2 import Any as AnyProto


class SocketEvent(Enum):
    kConnect = "connect"
    kMessage = "message"
    kDisconnect = "disconnect"
    kError = "error"


class Messages(Enum):
    kSendDeviceInfo = "send_device_info"


def createMessage(type: str, data: AnyProto) -> bytes:
    message = message_pb2.MessageProto()  # pyright: ignore
    message.type = type

    # Pack the message into the Any field
    packed = AnyProto()
    packed.Pack(data)
    message.payload.CopyFrom(packed)

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
