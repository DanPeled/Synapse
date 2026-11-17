# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for shutting runtime resources down in a predictable order."""

import threading
import time
from typing import Callable, List, Optional, Tuple

import synapse.log as log


class ShutdownStack:
    """Runs registered cleanup callbacks exactly once, in reverse order.

    Resources are registered as they are started, so shutting down is the
    inverse of startup. A failure in one callback is logged and does not stop
    the remaining resources from being released.
    """

    def __init__(self) -> None:
        self._callbacks: List[Tuple[str, Callable[[], None]]] = []
        self._lock = threading.Lock()
        self._shutdownStarted = False

    def register(self, name: str, callback: Callable[[], None]) -> None:
        """Register a resource cleanup callback.

        Args:
            name (str): Human-readable resource name used in error messages.
            callback (Callable[[], None]): Callback that releases the resource.
        """
        with self._lock:
            if self._shutdownStarted:
                raise RuntimeError(
                    f"Cannot register {name!r}: shutdown has already started"
                )
            self._callbacks.append((name, callback))

    def shutdown(self) -> None:
        """Run all registered callbacks once, in reverse registration order."""
        with self._lock:
            if self._shutdownStarted:
                return
            self._shutdownStarted = True
            callbacks = list(reversed(self._callbacks))
            self._callbacks.clear()

        for name, callback in callbacks:
            log.info(f"Shutting down {name}...")
            start = time.perf_counter()
            try:
                callback()
            except Exception as error:
                elapsed = time.perf_counter() - start
                log.err(f"Failed to shut down {name} after {elapsed:.2f}s: {error}")
            else:
                elapsed = time.perf_counter() - start
                log.info(f"Finished shutting down {name} ({elapsed:.2f}s)")


def joinThread(
    thread: Optional[threading.Thread],
    name: str,
    timeout: float,
) -> bool:
    """Join a thread with a bounded wait.

    Args:
        thread (Optional[threading.Thread]): Thread to join. ``None`` is a no-op.
        name (str): Human-readable thread name used in warnings.
        timeout (float): Maximum seconds to wait for the thread to stop.

    Returns:
        bool: ``True`` if the thread stopped (or was not running), else ``False``.
    """
    if thread is None or thread is threading.current_thread():
        return True

    thread.join(timeout)
    if thread.is_alive():
        log.warn(f"Thread {name} did not stop within {timeout:.1f}s")
        return False
    return True
