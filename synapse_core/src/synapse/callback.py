# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import traceback
from typing import Callable, Generic, List, ParamSpec

from .log import err

P = ParamSpec("P")


class Callback(Generic[P]):
    """Manage a list of callbacks.

    Callbacks are registered from setup, scanner and command threads and
    invoked from worker and NetworkTables listener threads. Registration and
    dispatch are therefore serialized, and dispatch iterates a snapshot so a
    callback can safely add or remove another callback while running.
    """

    def __init__(self) -> None:
        self.callbacks: List[Callable[P, None]] = []
        self._lock = threading.RLock()

    def add(self, callback: Callable[P, None]) -> None:
        """Add a callback"""
        with self._lock:
            self.callbacks.append(callback)

    def remove(self, callback: Callable[P, None]) -> None:
        """Remove a callback if present."""
        with self._lock:
            try:
                self.callbacks.remove(callback)
            except ValueError:
                err(f"Callback {callback} not found for removal.")

    def call(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """Call all callbacks"""
        with self._lock:
            callbacks = tuple(self.callbacks)

        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as error:
                errString = f"Exception in callback {cb}:\n" + "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )
                err(errString)

    __call__ = call
