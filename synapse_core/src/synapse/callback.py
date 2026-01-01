# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import traceback
from typing import Callable, Generic, List, ParamSpec

from .log import err

P = ParamSpec("P")


class Callback(Generic[P]):
    """Manage a list of callbacks"""

    def __init__(self) -> None:
        self.callbacks: List[Callable[P, None]] = []

    def add(self, callback: Callable[P, None]) -> None:
        """Add a callback"""
        self.callbacks.append(callback)

    def remove(self, callback: Callable[P, None]) -> None:
        """Remove a callback if present."""
        try:
            self.callbacks.remove(callback)
        except ValueError:
            err(f"Callback {callback} not found for removal.")

    def call(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """Call all callbacks"""
        for cb in self.callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as error:
                errString = f"Exception in callback {cb}:\n" + "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )
                err(errString)

    __call__ = call
