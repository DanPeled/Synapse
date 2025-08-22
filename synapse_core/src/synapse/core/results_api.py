# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import fields, is_dataclass
from typing import Any

import msgpack
from wpimath import geometry


class PipelineResult: ...


# -------------------
# Geometry serializers
# -------------------


def serializeTranslation2d(obj: geometry.Translation2d):
    return {"type": "Translation2d", "value": [obj.X(), obj.Y()]}


def serializeTranslation3d(obj: geometry.Translation3d):
    return {"type": "Translation3d", "value": [obj.X(), obj.Y(), obj.Z()]}


def serializeRotation2d(obj: geometry.Rotation2d):
    return {"type": "Rotation2d", "value": obj.degrees()}


def serializeRotation3d(obj: geometry.Rotation3d):
    return {
        "type": "Rotation3d",
        "value": [obj.x_degrees, obj.y_degrees, obj.z_degrees],
    }


def serializePose2d(obj: geometry.Pose2d):
    return {"type": "Pose2d", "value": [obj.X(), obj.Y(), obj.rotation().degrees()]}


def serializePose3d(obj: geometry.Pose3d):
    return {
        "type": "Pose3d",
        "value": [
            obj.X(),
            obj.Y(),
            obj.Z(),
            obj.rotation().x_degrees,
            obj.rotation().y_degrees,
            obj.rotation().z_degrees,
        ],
    }


def serializeTransform2d(obj: geometry.Transform2d):
    return {
        "type": "Transform2d",
        "value": [
            obj.translation().X(),
            obj.translation().Y(),
            obj.rotation().degrees(),
        ],
    }


def serializeTransform3d(obj: geometry.Transform3d):
    return {
        "type": "Transform3d",
        "value": [
            obj.translation().X(),
            obj.translation().Y(),
            obj.translation().Z(),
            obj.rotation().x_degrees,
            obj.rotation().y_degrees,
            obj.rotation().z_degrees,
        ],
    }


def serializeTwist2d(obj: geometry.Twist2d):
    return {"type": "Twist2d", "value": [obj.dx, obj.dy, obj.dtheta]}


def serializeTwist3d(obj: geometry.Twist3d):
    return {
        "type": "Twist3d",
        "value": [obj.dx, obj.dy, obj.dz, obj.rx, obj.ry, obj.rz],
    }


# -------------------
# Dispatcher with caching
# -------------------


def parsePipelineResult(
    result: PipelineResult, _cache: dict[int, Any] | None = None
) -> Any:
    """
    Recursively convert a PipelineResult (dataclass) into
    plain Python types that are msgpack-serializable,
    including wpimath.geometry types.

    Uses an object-id cache so the same object is only serialized once.
    """
    if _cache is None:
        _cache = {}

    oid = id(result)
    if oid in _cache:
        return _cache[oid]

    # --- Geometry Types ---
    if isinstance(result, geometry.Translation2d):
        out = serializeTranslation2d(result)
    elif isinstance(result, geometry.Translation3d):
        out = serializeTranslation3d(result)
    elif isinstance(result, geometry.Rotation2d):
        out = serializeRotation2d(result)
    elif isinstance(result, geometry.Rotation3d):
        out = serializeRotation3d(result)
    elif isinstance(result, geometry.Pose2d):
        out = serializePose2d(result)
    elif isinstance(result, geometry.Pose3d):
        out = serializePose3d(result)
    elif isinstance(result, geometry.Transform2d):
        out = serializeTransform2d(result)
    elif isinstance(result, geometry.Transform3d):
        out = serializeTransform3d(result)
    elif isinstance(result, geometry.Twist2d):
        out = serializeTwist2d(result)
    elif isinstance(result, geometry.Twist3d):
        out = serializeTwist3d(result)

    # --- Dataclasses ---
    elif is_dataclass(result):
        out = {
            f.name: parsePipelineResult(getattr(result, f.name), _cache)
            for f in fields(result)
        }

    # --- Containers ---
    elif isinstance(result, (list, tuple, set)):
        out = [parsePipelineResult(v, _cache) for v in result]
    elif isinstance(result, dict):
        out = {
            parsePipelineResult(k, _cache): parsePipelineResult(v, _cache)
            for k, v in result.items()
        }

    # --- Primitives ---
    else:
        out = result

    _cache[oid] = out
    return out


def serializePipelineResult(result: PipelineResult):
    return msgpack.packb(parsePipelineResult(result), use_bin_type=True)
