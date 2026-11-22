# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for converting MessagePack-decoded mappings into result dataclasses."""

from collections.abc import Callable, Sequence
from dataclasses import MISSING, fields, is_dataclass
from functools import lru_cache
from types import UnionType
from typing import (
    Any,
    Dict,
    List,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from wpimath import (
    Pose2d,
    Pose3d,
    Rotation2d,
    Rotation3d,
    Transform2d,
    Transform3d,
    Translation2d,
    Translation3d,
    Twist2d,
    Twist3d,
)


def _asSequence(value: Any) -> Sequence[float]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Expected a sequence, got {type(value)}")
    return value


# The runtime sends geometry as plain arrays, with angles in degrees. Register
# converters so custom result dataclasses can declare WPILib geometry fields.
_GEOMETRY_CONVERTERS: Dict[Any, Callable[[Any], Any]] = {
    Translation2d: lambda value: Translation2d(*(_asSequence(value)[0:2])),
    Translation3d: lambda value: Translation3d(*(_asSequence(value)[0:3])),
    Rotation2d: lambda value: Rotation2d.fromDegrees(
        value[0] if isinstance(value, (list, tuple)) else value
    ),
    Rotation3d: lambda value: Rotation3d.fromDegrees(*_asSequence(value)[0:3]),
    Pose2d: lambda value: Pose2d(
        Translation2d(*_asSequence(value)[0:2]),
        Rotation2d.fromDegrees(_asSequence(value)[2]),
    ),
    Pose3d: lambda value: Pose3d(
        Translation3d(*_asSequence(value)[0:3]),
        Rotation3d.fromDegrees(*_asSequence(value)[3:6]),
    ),
    Transform2d: lambda value: Transform2d(
        Translation2d(*_asSequence(value)[0:2]),
        Rotation2d.fromDegrees(_asSequence(value)[2]),
    ),
    Transform3d: lambda value: Transform3d(
        Translation3d(*_asSequence(value)[0:3]),
        Rotation3d.fromDegrees(*_asSequence(value)[3:6]),
    ),
    Twist2d: lambda value: Twist2d(*_asSequence(value)[0:3]),
    Twist3d: lambda value: Twist3d(*_asSequence(value)[0:6]),
}


def _convertValue(value: Any, annotation: Any) -> Any:
    """Recursively convert *value* to the type described by *annotation*."""
    if value is None or annotation is Any or annotation is None:
        return value

    geometryConverter = _GEOMETRY_CONVERTERS.get(annotation)
    if geometryConverter is not None:
        return geometryConverter(value)

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


# -------------------
# Cached conversion metadata
# -------------------

# get_type_hints() evaluates annotations with eval() and was being called for
# every result object (including every item in a list). Cache it per class; on
# failure fall back to raw annotations and retry next time in case the forward
# reference becomes resolvable.
_TYPE_HINTS_CACHE: dict[Type[Any], dict[str, Any]] = {}
_FIELD_SPECS_CACHE: dict[Type[Any], tuple[tuple[str, Any, Any, Any], ...]] = {}


def _typeHints(cls: Type[Any]) -> dict[str, Any]:
    try:
        return _TYPE_HINTS_CACHE[cls]
    except KeyError:
        pass

    try:
        typeHints = get_type_hints(cls)
    except Exception:
        return {}

    _TYPE_HINTS_CACHE[cls] = typeHints
    return typeHints


def _fieldSpecs(cls: Type[Any]) -> tuple[tuple[str, Any, Any, Any], ...]:
    try:
        return _FIELD_SPECS_CACHE[cls]
    except KeyError:
        pass

    typeHints = _typeHints(cls)
    specs = tuple(
        (
            field.name,
            typeHints.get(field.name, field.type),
            field.default,
            field.default_factory,
        )
        for field in fields(cls)
    )
    if typeHints:
        _FIELD_SPECS_CACHE[cls] = specs
    return specs


def _identity(value: Any) -> Any:
    return value


def _toFloat(value: Any) -> Any:
    return float(value) if isinstance(value, int) else value


def _toInt(value: Any) -> Any:
    return int(value) if isinstance(value, float) and value.is_integer() else value


@lru_cache(maxsize=2048)
def _converterForAnnotation(annotation: Any) -> Callable[[Any], Any]:
    """Build (and cache) a converter callable for an evaluated annotation."""
    geometryConverter = _GEOMETRY_CONVERTERS.get(annotation)
    if geometryConverter is not None:
        return geometryConverter

    if annotation is Any or annotation is None:
        return _identity

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Union or origin is UnionType:
        options = tuple(
            _converterForAnnotation(option)
            for option in args
            if option is not type(None)
        )

        def convertUnion(value: Any) -> Any:
            for option in options:
                try:
                    return option(value)
                except (TypeError, ValueError):
                    continue
            return value

        return convertUnion

    if origin in (list, List, tuple, set):
        itemConverter = _converterForAnnotation(args[0] if args else Any)
        if origin is tuple:
            return lambda value: tuple(itemConverter(item) for item in value)
        if origin is set:
            return lambda value: set(itemConverter(item) for item in value)
        return lambda value: [itemConverter(item) for item in value]

    if origin is dict:
        keyConverter = _converterForAnnotation(args[0] if len(args) > 0 else Any)
        valueConverter = _converterForAnnotation(args[1] if len(args) > 1 else Any)
        return lambda value: {
            keyConverter(key): valueConverter(item) for key, item in value.items()
        }

    if is_dataclass(annotation):
        return lambda value: from_dict(cast(Type[Any], annotation), value)

    if annotation is float:
        return _toFloat
    if annotation is int:
        return _toInt

    return _identity


def _converter(annotation: Any) -> Callable[[Any], Any]:
    try:
        return _converterForAnnotation(annotation)
    except TypeError:
        # Rare unhashable annotation: fall back to recursive inspection.
        return lambda value: _convertValue(value, annotation)


def _convert(value: Any, annotation: Any) -> Any:
    """Fast path for a single field, preserving the original None/Any rules."""
    if value is None or annotation is Any or annotation is None:
        return value
    return _converter(annotation)(value)


def from_dict(cls: Type[Any], data: Dict[str, Any]) -> Any:
    """Convert a mapping into a dataclass instance of type *cls*.

    Nested dataclasses, lists, tuples, dictionaries, and optionals are handled
    recursively. Unknown keys are ignored, and fields missing from *data* fall
    back to their dataclass default (or ``None``) so that a client built for an
    older runtime keeps working with a newer one. Type hints and converters are
    cached between calls because results arrive once per frame.
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping for {cls.__name__}, got {type(data)}")

    initKwargs = {}
    for name, annotation, default, defaultFactory in _fieldSpecs(cls):
        if name in data:
            initKwargs[name] = _convert(data[name], annotation)
        elif default is not MISSING:
            initKwargs[name] = default
        elif defaultFactory is not MISSING:  # pyright: ignore[reportAttributeAccessIssue]
            initKwargs[name] = defaultFactory()  # pyright: ignore[reportAttributeAccessIssue]
        else:
            initKwargs[name] = None

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
