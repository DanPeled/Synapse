# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import inspect
import threading
import traceback
from collections import OrderedDict
from dataclasses import fields
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Coroutine, Dict, Hashable, List, Optional, Set, Union

import betterproto
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve
from websockets.typing import Data

from .generated.messages.v1 import MessageProto, MessageTypeProto

# Cache the payload field names once; `createMessage` is called for every log,
# result and metric sent to the UI, so rebuilding this set per message is pure
# overhead.
_MESSAGE_FIELD_NAMES = frozenset(f.name for f in fields(MessageProto))

# A coalesced message can be supplied as a factory so protobuf encoding happens
# only if the value is actually sent. Non-coalesced messages are always ready.
MessageData = Union[Data, Callable[[], Data]]


def _resolveMessage(message: MessageData) -> Data:
    return message() if callable(message) else message


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
    if field_name in _MESSAGE_FIELD_NAMES:
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
        # Background send queue. `sendToAllSync` is called from arbitrary
        # threads (runtime, logging, metrics), so instead of scheduling a new
        # task per message we hand messages to a single long-lived task on the
        # websocket loop. This keeps message ordering and avoids the cost of
        # creating a Task per frame.
        self._sendQueue: Optional[asyncio.Queue] = None
        self._sendTask: Optional[asyncio.Task] = None
        # Coalesced messages are kept by key so a slow UI only ever receives
        # the newest value for a given topic. The queue holds a single wakeup
        # for the whole map instead of one entry per update.
        self._coalesced: "OrderedDict[Hashable, MessageData]" = OrderedDict()
        self._wakeupPending = False
        # Producers coalesce before crossing into the loop. At 4 cameras x 120
        # FPS that turns hundreds of cross-thread wakeups per second into at
        # most one per loop tick.
        self._pending: "OrderedDict[Hashable, MessageData]" = OrderedDict()
        self._pendingLock = threading.Lock()
        self._pendingFlushScheduled = False
        self._clientLock = threading.Lock()
        self._openClientCount = 0
        # Producers read this on every result publish. Maintaining the boolean
        # when the client set changes avoids taking a cross-thread lock in the
        # camera worker just to discover that no UI is connected.
        self._hasClients = False

    @property
    def hasClients(self) -> bool:
        """Whether at least one websocket client is currently open."""
        return self._hasClients

    def registerClient(self, client: WebSocketServerProtocol) -> None:
        """Track a client without scanning the mutable client set per result."""
        with self._clientLock:
            self.clients.add(client)
            if getattr(client, "open", False):
                self._openClientCount += 1
            self._hasClients = self._openClientCount > 0

    def unregisterClient(self, client: WebSocketServerProtocol) -> None:
        with self._clientLock:
            self.clients.discard(client)
            if getattr(client, "open", False):
                self._openClientCount = max(0, self._openClientCount - 1)
            self._hasClients = self._openClientCount > 0

    def on(self, event: SocketEvent):
        def decorator(func: Callable[..., Coroutine]):
            self.callbacks[event] = func
            return func

        return decorator

    async def _emit(self, event: SocketEvent, *args, **kwargs):
        if event in self.callbacks:
            await self.callbacks[event](*args, **kwargs)

    async def handler(self, websocket: WebSocketServerProtocol, path: str):
        self.registerClient(websocket)
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
            self.unregisterClient(websocket)
            await self._emit(SocketEvent.kDisconnect, websocket)

    async def sendToAll(self, message: Data):
        if not self.clients:
            return
        # Avoid creating many tasks if none open
        coros = []
        for client in list(self.clients):
            try:
                if client.open:
                    coros.append(client.send(message))
            except Exception:
                continue
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

    def sendToAllSync(
        self, message: MessageData, *, coalesce_key: Optional[Hashable] = None
    ):
        try:
            if self.loop and self.loop.is_running():
                if coalesce_key is None:
                    # Control messages must not be hidden by a pending result.
                    # Flush the producer-side map first so ordering is kept.
                    with self._pendingLock:
                        pending, self._pending = self._pending, OrderedDict()
                        self._pendingFlushScheduled = False
                    self.loop.call_soon_threadsafe(self._enqueueBatch, pending, message)
                    return

                shouldSchedule = False
                with self._pendingLock:
                    self._pending[coalesce_key] = message
                    if not self._pendingFlushScheduled:
                        self._pendingFlushScheduled = True
                        shouldSchedule = True
                if shouldSchedule:
                    try:
                        self.loop.call_soon_threadsafe(self._enqueuePending)
                    except Exception:
                        with self._pendingLock:
                            self._pendingFlushScheduled = False
                        raise
                return
            # Run in a temporary event loop (e.g. during test or before full setup)
            asyncio.run(self.sendToAll(_resolveMessage(message)))
        except Exception:
            pass

    def _enqueuePending(self) -> None:
        """Move producer-side coalesced values into the loop-side map."""
        with self._pendingLock:
            pending, self._pending = self._pending, OrderedDict()
            self._pendingFlushScheduled = False
        if not pending:
            return
        if self._sendQueue is None:
            self._sendQueue = asyncio.Queue()

        for key, message in pending.items():
            self._coalesced[key] = message
        if not self._wakeupPending:
            self._wakeupPending = True
            self._sendQueue.put_nowait((None, None, True))
        self._ensureSendTask()

    def _enqueueBatch(
        self, pending: "OrderedDict[Hashable, MessageData]", unkeyed: MessageData
    ) -> None:
        """Flush coalesced results followed by an ordered control message."""
        self._enqueuePendingValues(pending)
        if self._sendQueue is None:
            self._sendQueue = asyncio.Queue()
        self._sendQueue.put_nowait((None, _resolveMessage(unkeyed), False))
        self._ensureSendTask()

    def _enqueuePendingValues(
        self, pending: "OrderedDict[Hashable, MessageData]"
    ) -> None:
        if not pending:
            return
        if self._sendQueue is None:
            self._sendQueue = asyncio.Queue()
        for key, message in pending.items():
            self._coalesced[key] = message
        if not self._wakeupPending:
            self._wakeupPending = True
            self._sendQueue.put_nowait((None, None, True))

    def _enqueue(self, message: MessageData, coalesce_key: Optional[Hashable]):
        """Queue a message for the background sender (must run on the loop)."""
        if self._sendQueue is None:
            self._sendQueue = asyncio.Queue()

        if coalesce_key is None:
            self._sendQueue.put_nowait((None, _resolveMessage(message), False))
        else:
            self._coalesced[coalesce_key] = message
            if not self._wakeupPending:
                self._wakeupPending = True
                self._sendQueue.put_nowait((None, None, True))
        self._ensureSendTask()

    def _ensureSendTask(self) -> None:
        if self._sendTask is None or self._sendTask.done():
            self._sendTask = asyncio.get_running_loop().create_task(self._sendLoop())

    async def _sendLoop(self):
        """Drain the send queue sequentially, one message at a time."""
        assert self._sendQueue is not None
        while True:
            _, message, isWakeup = await self._sendQueue.get()
            try:
                if isWakeup:
                    if self._coalesced:
                        _, coalescedMessage = self._coalesced.popitem(last=False)
                        await self.sendToAll(_resolveMessage(coalescedMessage))
                    if self._coalesced:
                        self._sendQueue.put_nowait((None, None, True))
                    else:
                        self._wakeupPending = False
                elif message is not None:
                    await self.sendToAll(message)
            except Exception:
                pass
            finally:
                self._sendQueue.task_done()

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
        if self._sendTask is not None and not self._sendTask.done():
            self._sendTask.cancel()
            try:
                await self._sendTask
            except asyncio.CancelledError:
                pass
        self._sendTask = None
        self._sendQueue = None
        with self._pendingLock:
            self._pending.clear()
            self._pendingFlushScheduled = False
        self._coalesced.clear()
        self._wakeupPending = False
        if self._server:
            # If _server is a coroutine, await it first
            if asyncio.iscoroutine(self._server):
                self._server = await self._server
            self._server.close()
            await self._server.wait_closed()


def assert_set(value: Any) -> Any:
    if value is not None:
        return value

    var_name = "<unknown>"

    try:
        frame = inspect.currentframe()
        if frame is not None:
            caller_frame = frame.f_back
            if caller_frame is not None:
                frame_info = inspect.getframeinfo(caller_frame)
                code_context = frame_info.code_context
                if code_context:
                    line = code_context[0].strip()
                    # Extract argument inside assert_set(...)
                    start = line.find("assert_set(")
                    if start != -1:
                        start += len("assert_set(")
                        end = line.find(")", start)
                        if end != -1:
                            var_name = line[start:end].strip()
    except Exception:
        # Any unexpected error just fallback silently
        pass

    raise AssertionError(f"Value '{var_name}' is None")
