# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import fields, is_dataclass
from typing import Any, Dict, Type


def from_dict(cls: Type[Any], data: Dict[str, Any]) -> Any:
    """
    Convert a dict into a dataclass instance of type cls.
    Handles nested dataclasses recursively.
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")

    init_kwargs = {}
    for field in fields(cls):
        value = data.get(field.name)
        # Recursively convert nested dataclasses
        if is_dataclass(field.type) and isinstance(value, dict):
            value = from_dict(field.type, value)  # pyright: ignore
        init_kwargs[field.name] = value

    return cls(**init_kwargs)


def dataclass_object_hook(cls: Type[Any]):
    """
    Returns an object_hook for msgpack.unpackb
    that converts dicts to the given dataclass.
    """

    def hook(obj):
        if isinstance(obj, dict):
            try:
                return from_dict(cls, obj)
            except Exception:
                return obj
        return obj

    return hook
