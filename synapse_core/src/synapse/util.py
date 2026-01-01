# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
import typing
from typing import Any, List, Optional, Type, Union

from ntcore import (BooleanArrayPublisher, BooleanPublisher,
                    DoubleArrayPublisher, DoublePublisher, NetworkTable,
                    RawPublisher, StringArrayPublisher, StringPublisher)

from .core.pipeline import Pipeline


def getIP() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ip: Optional[str] = None
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"

    s.close()

    return ip or "127.0.0.1"


def resolveGenericArgument(cls) -> Optional[Type]:
    orig_bases = getattr(cls, "__orig_bases__", ())
    for base in orig_bases:
        if typing.get_origin(base) is Pipeline:
            args = typing.get_args(base)
            if args:
                return args[0]
    return None


# -------- Publisher Union Type --------

Publisher = Union[
    BooleanPublisher,
    DoublePublisher,
    StringPublisher,
    RawPublisher,
    BooleanArrayPublisher,
    DoubleArrayPublisher,
    StringArrayPublisher,
]


# -------- Public API --------


def getPublisher(table: NetworkTable, key: str, value: Any) -> Publisher:
    """
    Create and return a NetworkTables publisher for `key`,
    inferring and locking the type from `value`.

    This MUST be called only once per key.
    """

    # ----- Scalars -----
    if isinstance(value, bool):
        return table.getBooleanTopic(key).publish()

    if isinstance(value, (int, float)):
        return table.getDoubleTopic(key).publish()

    if isinstance(value, str):
        return table.getStringTopic(key).publish()

    if isinstance(value, (bytes, bytearray)):
        return table.getRawTopic(key).publish("raw")

    # ----- Arrays -----
    if isinstance(value, list):
        return _getArrayPublisher(table, key, value)

    if isinstance(value, tuple):
        return _getArrayPublisher(table, key, list(value))

    raise TypeError(f"Unsupported NetworkTables type {type(value)} for key '{key}'")


# -------- Internal Helpers --------


def _getArrayPublisher(
    table: NetworkTable,
    key: str,
    values: List[Any],
) -> Publisher:
    """
    Infer array topic type from first element.
    NetworkTables arrays MUST be homogeneous.
    """

    if not values:
        raise ValueError(
            f"Cannot infer NetworkTables array type from empty list for key '{key}'"
        )

    first = values[0]

    if isinstance(first, bool):
        return table.getBooleanArrayTopic(key).publish()

    if isinstance(first, (int, float)):
        return table.getDoubleArrayTopic(key).publish()

    if isinstance(first, str):
        return table.getStringArrayTopic(key).publish()

    raise TypeError(f"Unsupported array element type {type(first)} for key '{key}'")
