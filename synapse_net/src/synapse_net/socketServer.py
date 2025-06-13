import asyncio
import websockets
from enum import Enum
from typing import Callable, Dict, Set


class SocketEvent(Enum):
    kConnect = "connect"
    kMessage = "message"
    kDisconnect = "disconnect"
    kError = "error"


class Messages(Enum):
    kSendDeviceInfo = "send_device_info"


class WebSocketServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.callbacks: Dict[SocketEvent, Callable] = {}
        self.clients: Set[websockets.WebSocketServerProtocol] = set()

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

    async def sendToAll(self, message: str):
        if self.clients:
            await asyncio.gather(
                *(client.send(message) for client in self.clients if client.open)
            )

    async def sendToClient(
        self, client: websockets.WebSocketServerProtocol, message: str
    ):
        if client in self.clients and client.open:
            await client.send(message)

    def start(self):
        return websockets.serve(self.handler, self.host, self.port)


if __name__ == "__main__":
    server = WebSocketServer("localhost", 8765)

    @server.on(SocketEvent.kConnect)
    async def on_connect(ws):
        import socket
        import json
        from synapse.hardware import metrics

        print(f"Client connected: {ws.remote_address}")

        addre = socket.gethostbyname(socket.gethostname())
        await server.sendToClient(
            ws,
            json.dumps(
                {
                    "type": Messages.kSendDeviceInfo.value,
                    "message": {
                        "ip": addre,
                        "platform": metrics.Platform.getCurrentPlatform()
                        .getOSType()
                        .value,
                    },
                }
            ),
        )

    @server.on(SocketEvent.kMessage)
    async def on_message(ws, msg):
        print(f"Message from {ws.remote_address}: {msg}")
        await server.sendToAll(f"Echo: {msg}")

    @server.on(SocketEvent.kDisconnect)
    async def on_disconnect(ws):
        print("Client disconnected:", ws.remote_address)

    @server.on(SocketEvent.kError)
    async def on_error(ws, error_msg):
        print(f"Error with {ws.remote_address}: {error_msg}")

    asyncio.get_event_loop().run_until_complete(server.start())
    print("WebSocket server started on ws://localhost:8765")
    asyncio.get_event_loop().run_forever()
