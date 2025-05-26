import socket
import selectors
import threading
from typing import Callable, Dict
from enum import Enum


class SocketEvent(Enum):
    """
    Enum representing possible socket event types.
    """

    kConnect = "connect"
    kMessage = "message"
    kDisconnect = "disconnect"
    kError = "error"


class SocketClient:
    """
    A TCP socket client that supports event-driven communication.
    """

    def __init__(self, host: str, port: int) -> None:
        """
        Initializes the SocketClient with the given host and port.

        Args:
            host: The server address to connect to.
            port: The server port to connect to.
        """
        self.host: str = host
        self.port: int = port
        self.selector: selectors.BaseSelector = selectors.DefaultSelector()
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        self.callbacks: Dict[SocketEvent, Callable[..., None]] = {}
        self.running: bool = False

    def on(
        self, event: SocketEvent
    ) -> Callable[[Callable[..., None]], Callable[..., None]]:
        """
        Registers a callback function for a specific event.

        Args:
            event: The event type (SocketEvent).

        Returns:
            A decorator to wrap the callback function.
        """

        def decorator(func: Callable[..., None]) -> Callable[..., None]:
            self.callbacks[event] = func
            return func

        return decorator

    def _emit(self, event: SocketEvent, *args, **kwargs) -> None:
        """
        Calls the registered callback for the given event, if any.

        Args:
            event: The event type.
            *args: Positional arguments to pass to the callback.
            **kwargs: Keyword arguments to pass to the callback.
        """
        if event in self.callbacks:
            self.callbacks[event](*args, **kwargs)

    def _handleRead(self, conn: socket.socket, mask: int) -> None:
        """
        Internal handler for readable socket events.

        Args:
            conn: The socket connection.
            mask: The event mask from the selector.
        """
        try:
            data = conn.recv(1024)
            if data:
                self._emit(SocketEvent.kMessage, data.decode())
            else:
                self._emit(SocketEvent.kDisconnect)
                self.stop()
        except Exception as e:
            self._emit(SocketEvent.kError, str(e))
            self.stop()

    def start(self) -> None:
        """
        Starts the socket client and connects to the server.
        Begins the event loop in a background thread.
        """
        try:
            self.socket.connect_ex((self.host, self.port))
            self.selector.register(self.socket, selectors.EVENT_READ, self._handleRead)
            self.running = True
            threading.Thread(target=self._runEventLoop, daemon=True).start()
            self._emit(SocketEvent.kConnect)
        except Exception as e:
            self._emit(SocketEvent.kError, str(e))

    def _runEventLoop(self) -> None:
        """
        Internal method that runs the event loop using the selector.
        Processes socket events while the client is running.
        """
        while self.running:
            for key, mask in self.selector.select(timeout=1):
                callback = key.data
                callback(key.fileobj, mask)

    def send(self, message: str) -> None:
        """
        Sends a message to the connected server.

        Args:
            message: The string message to send.
        """
        try:
            self.socket.sendall(message.encode())
        except Exception as e:
            self._emit(SocketEvent.kError, str(e))

    def stop(self) -> None:
        """
        Stops the client, closes the socket, and cleans up the selector.
        """
        self.running = False
        try:
            self.selector.unregister(self.socket)
        except Exception:
            pass
        self.socket.close()
