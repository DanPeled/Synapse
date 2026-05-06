# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import fields, is_dataclass
from typing import Any

import msgpack
from wpimath import (Pose2d, Pose3d, Rotation2d, Rotation3d, Transform2d,
                     Transform3d, Translation2d, Translation3d, Twist2d,
                     Twist3d)


class PipelineResult: ...


# -------------------
# Geometry serializers
# -------------------


def serializeTranslation2d(obj: Translation2d):
    return [obj.X(), obj.Y()]


def serializeTranslation3d(obj: Translation3d):
    return [obj.X(), obj.Y(), obj.Z()]


def serializeRotation2d(obj: Rotation2d):
    return obj.degrees()


def serializeRotation3d(obj: Rotation3d):
    return [obj.x_degrees, obj.y_degrees, obj.z_degrees]


def serializePose2d(obj: Pose2d):
    t = obj.translation()
    r = obj.rotation()
    return [t.X(), t.Y(), r.degrees()]


def serializePose3d(obj: Pose3d):
    return [
        obj.X(),
        obj.Y(),
        obj.Z(),
        obj.rotation().x_degrees,
        obj.rotation().y_degrees,
        obj.rotation().z_degrees,
    ]


def serializeTransform2d(obj: Transform2d):
    t = obj.translation()
    r = obj.rotation()
    return [t.X(), t.Y(), r.degrees()]


def serializeTransform3d(obj: Transform3d):
    t = obj.translation()
    r = obj.rotation()
    return [t.X(), t.Y(), t.Z(), r.x_degrees, r.y_degrees, r.z_degrees]


def serializeTwist2d(obj: Twist2d):
    return [obj.dx, obj.dy, obj.dtheta]


def serializeTwist3d(obj: Twist3d):
    return [obj.dx, obj.dy, obj.dz, obj.rx, obj.ry, obj.rz]


def parsePipelineResult(result: Any, _cache: dict[int, Any] | None = None) -> Any:
    if _cache is None:
        _cache = {}

    oid = id(result)
    if oid in _cache:
        return _cache[oid]

    # --- Primitive types ---
    if isinstance(result, (int, float, str, bool, type(None))):
        return result

    # --- Geometry types ---
    if isinstance(result, Translation2d):
        out = serializeTranslation2d(result)
    elif isinstance(result, Translation3d):
        out = serializeTranslation3d(result)
    elif isinstance(result, Rotation2d):
        out = serializeRotation2d(result)
    elif isinstance(result, Rotation3d):
        out = serializeRotation3d(result)
    elif isinstance(result, Pose2d):
        out = serializePose2d(result)
    elif isinstance(result, Pose3d):
        out = serializePose3d(result)
    elif isinstance(result, Transform2d):
        out = serializeTransform2d(result)
    elif isinstance(result, Transform3d):
        out = serializeTransform3d(result)
    elif isinstance(result, Twist2d):
        out = serializeTwist2d(result)
    elif isinstance(result, Twist3d):
        out = serializeTwist3d(result)

    # --- Containers ---
    elif isinstance(result, (list, tuple, set)):
        out = [parsePipelineResult(v, _cache) for v in result]
    elif isinstance(result, dict):
        out = {
            parsePipelineResult(k, _cache): parsePipelineResult(v, _cache)
            for k, v in result.items()
        }

    # --- Dataclasses ---
    elif is_dataclass(result):
        out = {
            f.name: parsePipelineResult(getattr(result, f.name), _cache)
            for f in fields(result)
        }

    # --- Other objects (including pybind / properties) ---
    else:
        out = {}
        for attr_name in dir(result):
            if attr_name.startswith("_"):
                continue  # skip internal/private
            try:
                attr_val = getattr(result, attr_name)
                if callable(attr_val):
                    continue
                out[attr_name] = parsePipelineResult(attr_val, _cache)
            except Exception:
                continue
        if not out:  # fallback
            out = str(result)  # or raw object if you prefer

    _cache[oid] = out
    return out


def serializePipelineResult(result: PipelineResult):
    return msgpack.packb(parsePipelineResult(result), use_bin_type=True)
