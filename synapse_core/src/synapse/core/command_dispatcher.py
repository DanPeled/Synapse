# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Single-worker dispatcher for commands that must not run on the websocket loop.

A single FIFO queue keeps state mutations ordered without creating an unbounded
number of threads. Callers only parse/enqueue; every potentially blocking
handler runs on the dedicated worker thread.
"""

import queue
import threading
from typing import Callable, Generic, Optional, TypeVar, Union, cast

T = TypeVar("T")

_STOP = object()


class CommandDispatcher(Generic[T]):
    """Run submitted commands sequentially on one dedicated thread.

    Args:
        handler: Called once per submitted item, in submission order.
        on_error: Called when ``handler`` raises.
        name: Thread name used for diagnostics.
    """

    def __init__(
        self,
        handler: Callable[[T], None],
        on_error: Callable[[Exception], None],
        *,
        name: str = "SynapseCommand",
    ) -> None:
        self._handler = handler
        self._on_error = on_error
        self._queue: "queue.Queue[Union[T, object]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._name = name

    def start(self) -> None:
        """Start the worker thread. Calling this more than once is a no-op."""
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run,
                name=self._name,
                daemon=True,
            )
            self._thread.start()

    def submit(self, command: T) -> None:
        """Enqueue a command. Safe to call from the websocket event loop."""
        with self._lock:
            if self._stopping.is_set():
                return
            self._queue.put_nowait(command)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Stop after draining commands already in the queue.

        This is idempotent and safe to call from the worker thread (the worker
        simply will not join itself).
        """
        with self._lock:
            if self._thread is None:
                return
            self._stopping.set()
            self._queue.put_nowait(_STOP)
            thread = self._thread

        if thread is threading.current_thread():
            return
        thread.join(timeout)

    def _run(self) -> None:
        while True:
            command = self._queue.get()
            try:
                if command is _STOP:
                    return
                self._handler(cast(T, command))
            except Exception as error:
                self._on_error(error)
            finally:
                self._queue.task_done()
