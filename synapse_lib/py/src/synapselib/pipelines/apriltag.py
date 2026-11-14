# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generated from schema/synapse_lib.json. Do not edit by hand.
# Run `python tools/generate_synapse_lib.py` to regenerate.

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Optional

from wpimath.geometry import Pose3d, Rotation3d, Translation3d


def _hashable(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((_hashable(k), _hashable(v)) for k, v in value.items()))
    return value


@dataclass(frozen=True)
class ApriltagDetection:
    """Represents a single detected AprilTag, including its screen-space position."""

    tag_id: int
    """The unique ID of the detected AprilTag."""

    hamming: int
    """The Hamming distance of the detection. Lower values are more accurate."""

    tagPose_screenSpace: List[float]
    """The center of the tag in screen space, as [x, y] pixels."""

    def __hash__(self) -> int:
        return hash((self.tag_id, self.hamming, _hashable(self.tagPose_screenSpace)))

    @property
    def tx(self) -> float:
        """Returns the tag's horizontal position in screen space."""
        return self.tagPose_screenSpace[0]

    @property
    def ty(self) -> float:
        """Returns the tag's vertical position in screen space."""
        return self.tagPose_screenSpace[1]


@dataclass(frozen=True)
class ApriltagResult:
    """Represents the result of detecting AprilTags in a single frame."""

    tags: List[ApriltagDetection]
    """The detected AprilTags."""

    cameraEstimate_fieldSpace: Optional[List[float]]
    """The camera pose as [x, y, z, roll, pitch, yaw] in degrees, or null when unavailable."""

    reprojection_error: float
    """The reprojection error of the camera pose estimate. 0.0 when unavailable."""

    def __hash__(self) -> int:
        return hash(
            (
                _hashable(self.tags),
                _hashable(self.cameraEstimate_fieldSpace),
                self.reprojection_error,
            )
        )

    @property
    def cameraEstimate_fieldSpace3d(self) -> Optional[Pose3d]:
        """Returns the camera's estimated pose in field space as a 3D pose."""
        estimate = self.cameraEstimate_fieldSpace
        if estimate is None:
            return None
        if len(estimate) < 6:
            raise ValueError(
                "cameraEstimate_fieldSpace must contain [x, y, z, roll, pitch, yaw]"
            )
        return Pose3d(
            translation=Translation3d(estimate[0], estimate[1], estimate[2]),
            # The runtime serializes roll/pitch/yaw in degrees, but the
            # Rotation3d constructor expects radians.
            rotation=Rotation3d(
                math.radians(estimate[3]),
                math.radians(estimate[4]),
                math.radians(estimate[5]),
            ),
        )
