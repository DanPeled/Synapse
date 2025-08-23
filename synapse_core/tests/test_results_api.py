# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from math import radians

import msgpack
from synapse.core import results_api as api
from wpimath import geometry

# -------------------
# Dummy PipelineResult subclasses for testing
# -------------------


class PRInt(api.PipelineResult):
    def __init__(self, value):
        self.value = value


class PRFloat(api.PipelineResult):
    def __init__(self, value):
        self.value = value


class PRStr(api.PipelineResult):
    def __init__(self, value):
        self.value = value


class PRBool(api.PipelineResult):
    def __init__(self, value):
        self.value = value


class PRTranslation2d(api.PipelineResult):
    def __init__(self, x, y):
        self.translation = geometry.Translation2d(x, y)


class PRTranslation3d(api.PipelineResult):
    def __init__(self, x, y, z):
        self.translation = geometry.Translation3d(x, y, z)


class PRRotation2d(api.PipelineResult):
    def __init__(self, deg):
        self.rotation = geometry.Rotation2d(radians(deg))


class PRRotation3d(api.PipelineResult):
    def __init__(self, x_deg, y_deg, z_deg):
        self.rotation = geometry.Rotation3d(
            radians(x_deg), radians(y_deg), radians(z_deg)
        )


class PRPose2d(api.PipelineResult):
    def __init__(self, x, y, deg):
        self.pose = geometry.Pose2d(x, y, geometry.Rotation2d(radians(deg)))


class PRPose3d(api.PipelineResult):
    def __init__(self, x, y, z, x_deg, y_deg, z_deg):
        self.pose = geometry.Pose3d(
            x, y, z, geometry.Rotation3d(radians(x_deg), radians(y_deg), radians(z_deg))
        )


class PRTransform2d(api.PipelineResult):
    def __init__(self, x, y, deg):
        self.transform = geometry.Transform2d(
            geometry.Translation2d(x, y), geometry.Rotation2d(radians(deg))
        )


class PRTransform3d(api.PipelineResult):
    def __init__(self, x, y, z, x_deg, y_deg, z_deg):
        self.transform = geometry.Transform3d(
            geometry.Translation3d(x, y, z),
            geometry.Rotation3d(radians(x_deg), radians(y_deg), radians(z_deg)),
        )


class PRTwist2d(api.PipelineResult):
    def __init__(self, dx, dy, dtheta):
        self.twist = geometry.Twist2d(dx, dy, dtheta)


class PRTwist3d(api.PipelineResult):
    def __init__(self, dx, dy, dz, rx, ry, rz):
        self.twist = geometry.Twist3d(dx, dy, dz, radians(rx), radians(ry), radians(rz))


@dataclass
class PRDataclass(api.PipelineResult):
    x: int
    y: str


class PRContainer(api.PipelineResult):
    def __init__(self):
        self.lst = [PRInt(1), PRInt(2)]
        self.dct = {"a": PRInt(10)}


# -------------------
# Tests for primitives
# -------------------


def test_parse_primitives():
    assert api.parsePipelineResult(PRInt(42))["value"] == 42
    assert api.parsePipelineResult(PRFloat(3.14))["value"] == 3.14
    assert api.parsePipelineResult(PRStr("hello"))["value"] == "hello"
    assert api.parsePipelineResult(PRBool(True))["value"] is True


# -------------------
# Tests for geometry types
# -------------------


def test_parse_geometry():
    # Translation
    assert api.parsePipelineResult(PRTranslation2d(1, 2))["translation"] == [1, 2]
    assert api.parsePipelineResult(PRTranslation3d(1, 2, 3))["translation"] == [1, 2, 3]

    # Rotation
    r2d_obj = geometry.Rotation2d(radians(45))
    parsed2d = api.parsePipelineResult(PRRotation2d(45))["rotation"]
    assert parsed2d == r2d_obj.degrees()

    r3d_obj = geometry.Rotation3d(radians(10), radians(20), radians(30))
    parsed3d = api.parsePipelineResult(PRRotation3d(10, 20, 30))["rotation"]
    expected3d = [r3d_obj.x_degrees, r3d_obj.y_degrees, r3d_obj.z_degrees]
    assert parsed3d == expected3d

    # Pose
    p2d_obj = geometry.Pose2d(5, 7, geometry.Rotation2d(radians(90)))
    parsed_p2d = api.parsePipelineResult(PRPose2d(5, 7, 90))["pose"]
    assert parsed_p2d == [p2d_obj.X(), p2d_obj.Y(), p2d_obj.rotation().degrees()]

    p3d_obj = geometry.Pose3d(
        1, 2, 3, geometry.Rotation3d(radians(10), radians(20), radians(30))
    )
    parsed_p3d = api.parsePipelineResult(PRPose3d(1, 2, 3, 10, 20, 30))["pose"]
    expected_p3d = [
        p3d_obj.X(),
        p3d_obj.Y(),
        p3d_obj.Z(),
        p3d_obj.rotation().x_degrees,
        p3d_obj.rotation().y_degrees,
        p3d_obj.rotation().z_degrees,
    ]
    assert parsed_p3d == expected_p3d

    # Transform
    t2d_obj = geometry.Transform2d(
        geometry.Translation2d(1, 2), geometry.Rotation2d(radians(90))
    )
    parsed_t2d = api.parsePipelineResult(PRTransform2d(1, 2, 90))["transform"]
    assert parsed_t2d == [
        t2d_obj.translation().X(),
        t2d_obj.translation().Y(),
        t2d_obj.rotation().degrees(),
    ]

    t3d_obj = geometry.Transform3d(
        geometry.Translation3d(1, 2, 3),
        geometry.Rotation3d(radians(10), radians(20), radians(30)),
    )
    parsed_t3d = api.parsePipelineResult(PRTransform3d(1, 2, 3, 10, 20, 30))[
        "transform"
    ]
    expected_t3d = [
        t3d_obj.translation().X(),
        t3d_obj.translation().Y(),
        t3d_obj.translation().Z(),
        t3d_obj.rotation().x_degrees,
        t3d_obj.rotation().y_degrees,
        t3d_obj.rotation().z_degrees,
    ]
    assert parsed_t3d == expected_t3d

    # Twist
    assert api.parsePipelineResult(PRTwist2d(1, 2, 3))["twist"] == [1, 2, 3]
    twist3d_obj = geometry.Twist3d(1, 2, 3, radians(4), radians(5), radians(6))
    parsed_twist3d = api.parsePipelineResult(PRTwist3d(1, 2, 3, 4, 5, 6))["twist"]
    expected_twist3d = [
        twist3d_obj.dx,
        twist3d_obj.dy,
        twist3d_obj.dz,
        twist3d_obj.rx,
        twist3d_obj.ry,
        twist3d_obj.rz,
    ]
    assert parsed_twist3d == expected_twist3d


# -------------------
# Tests for dataclass
# -------------------


def test_parse_dataclass():
    pr = PRDataclass(3, "hello")
    parsed = api.parsePipelineResult(pr)
    assert parsed == {"x": 3, "y": "hello"}


# -------------------
# Tests for containers
# -------------------


def test_parse_containers():
    pr = PRContainer()
    parsed = api.parsePipelineResult(pr)
    assert parsed["lst"][0]["value"] == 1
    assert parsed["lst"][1]["value"] == 2
    assert parsed["dct"]["a"]["value"] == 10


# -------------------
# Test msgpack serialization
# -------------------


def test_serialize_pipeline_result_msgpack():
    pr = PRTranslation2d(1, 2)
    packed = api.serializePipelineResult(pr)
    unpacked = msgpack.unpackb(packed, raw=False)
    assert unpacked["translation"] == [1, 2]
