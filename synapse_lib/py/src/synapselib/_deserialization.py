# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for converting MessagePack-decoded mappings into result dataclasses."""

from dataclasses import MISSING, fields, is_dataclass
from types import UnionType
from typing import (Any, Dict, List, Type, Union, cast, get_args, get_origin,
                    get_type_hints)


def _convertValue(value: Any, annotation: Any) -> Any:
    """Recursively convert *value* to the type described by *annotation*."""
    if value is None or annotation is Any or annotation is None:
        return value

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[X] / X | None / general unions. Prefer the first non-None
    # member that can handle the value so new runtime fields remain readable.
    if origin is Union or origin is UnionType:
        for option in args:
            if option is type(None):
                continue
            try:
                return _convertValue(value, option)
            except (TypeError, ValueError):
                continue
        return value

    if origin in (list, List, tuple, set):
        itemType = args[0] if args else Any
        converted = [_convertValue(item, itemType) for item in value]
        if origin is tuple:
            return tuple(converted)
        if origin is set:
            return set(converted)
        return converted

    if origin is dict:
        keyType, valueType = args if len(args) == 2 else (Any, Any)
        return {
            _convertValue(key, keyType): _convertValue(item, valueType)
            for key, item in value.items()
        }

    if is_dataclass(annotation) and isinstance(value, dict):
        return from_dict(cast(Type[Any], annotation), value)

    # MessagePack stores all numbers without a Python type distinction, so an
    # integer may arrive where the dataclass declares a float.
    if annotation is float and isinstance(value, int):
        return float(value)
    if annotation is int and isinstance(value, float) and value.is_integer():
        return int(value)

    return value


def from_dict(cls: Type[Any], data: Dict[str, Any]) -> Any:
    """Convert a mapping into a dataclass instance of type *cls*.

    Nested dataclasses, lists, tuples, dictionaries, and optionals are handled
    recursively. Unknown keys are ignored, and fields missing from *data* fall
    back to their dataclass default (or ``None``) so that a client built for an
    older runtime keeps working with a newer one.
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping for {cls.__name__}, got {type(data)}")

    try:
        typeHints = get_type_hints(cls)
    except Exception:
        # Forward references may not be resolvable in every environment. The
        # raw field annotations are still good enough for the common cases.
        typeHints = {}

    initKwargs = {}
    for field in fields(cls):
        annotation = typeHints.get(field.name, field.type)
        if field.name in data:
            initKwargs[field.name] = _convertValue(data[field.name], annotation)
        elif field.default is not MISSING:
            initKwargs[field.name] = field.default
        elif field.default_factory is not MISSING:  # pyright: ignore[reportAttributeAccessIssue]
            initKwargs[field.name] = field.default_factory()  # pyright: ignore[reportAttributeAccessIssue]
        else:
            initKwargs[field.name] = None

    return cls(**initKwargs)


def dataclass_object_hook(cls: Type[Any]):
    """Return a ``msgpack`` object hook that builds *cls* from mappings.

    .. deprecated::
        Prefer :func:`from_dict` with the fully unpacked payload. The hook is
        kept for backwards compatibility with older client code.
    """

    def hook(obj):
        if isinstance(obj, dict):
            try:
                return from_dict(cls, obj)
            except Exception:
                return obj
        return obj

    return hook
