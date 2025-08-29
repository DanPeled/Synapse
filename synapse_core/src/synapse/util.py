# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
import typing
from typing import Optional, Type

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
