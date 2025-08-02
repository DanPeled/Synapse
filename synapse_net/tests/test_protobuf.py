# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
import inspect
import math
import pkgutil
from typing import Any, Callable, Dict, List, Type, Union, get_args, get_origin

from betterproto import Message


def importSubmodules(package_name: str) -> Dict[str, Any]:
    package = importlib.import_module(package_name)
    modules = {}
    if hasattr(package, "__path__"):
        for loader, name, is_pkg in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        ):
            modules[name] = importlib.import_module(name)
    return modules


def defaultValueForType(typ: Any) -> Any:
    origin = get_origin(typ)
    args = get_args(typ)

    if origin is Union and type(None) in args:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return defaultValueForType(non_none_args[0])
        else:
            return None

    if origin in (list, List):
        return []

    if inspect.isclass(typ) and issubclass(typ, Message):
        return createDefaultMessage(typ)

    if typ is int:
        return 42
    if typ is float:
        return 3.14
    if typ is str:
        return "hello"
    if typ is bool:
        return True
    if typ is bytes:
        return b"abc"

    return None


def createDefaultMessage(message_cls: Type[Message]) -> Message:
    kwargs = {}
    annotations = getattr(message_cls, "__annotations__", {})
    for field, typ in annotations.items():
        val = defaultValueForType(typ)
        if val is not None:
            kwargs[field] = val
    return message_cls(**kwargs)


def messagesAreEqual(m1: Message, m2: Message) -> bool:
    """Recursively check betterproto Messages for equality,
    using math.isclose for floats and treating empty/missing lists as equal."""
    if type(m1) is not type(m2):
        return False

    for field in getattr(m1, "__annotations__", {}):
        v1 = getattr(m1, field, None)
        v2 = getattr(m2, field, None)

        # Nested messages
        if isinstance(v1, Message) and isinstance(v2, Message):
            if not messagesAreEqual(v1, v2):
                return False

        # Floats: use isclose with some tolerance
        elif isinstance(v1, float) and isinstance(v2, float):
            if not math.isclose(v1, v2, rel_tol=1e-6, abs_tol=1e-9):
                return False

        # Lists: treat empty/missing as equal
        elif isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            if len(v1) == 0 and len(v2) == 0:
                continue
            if v1 != v2:
                return False

        else:
            if v1 != v2:
                return False

    return True


def generateTestFunction(messageCls: Type[Message]) -> Callable[[], None]:
    def testSerialization() -> None:
        msg = createDefaultMessage(messageCls)
        encoded = bytes(msg)
        decoded = messageCls().parse(encoded)
        assert messagesAreEqual(msg, decoded), (
            f"Mismatch in {messageCls.__name__}: {msg} != {decoded}"
        )

    return testSerialization


modules = importSubmodules("synapse_net.proto")
for mod_name, module in modules.items():
    for name, cls in inspect.getmembers(module, inspect.isclass):
        if issubclass(cls, Message) and cls is not Message:
            test_func = generateTestFunction(cls)
            test_func.__name__ = f"test_serialization_{cls.__name__}"
            globals()[test_func.__name__] = test_func
