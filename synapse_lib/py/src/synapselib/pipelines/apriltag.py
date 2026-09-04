# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ApriltagDetection:
    """
    Represents a single detected AprilTag along with its associated metadata and pose estimates.

    This class contains the tag's ID, detection accuracy metrics, and the estimated
    poses of the camera and tag in multiple coordinate systems. It is typically
    produced by an AprilTag detection pipeline.
    """

    tag_id: int
    """The unique ID of the detected AprilTag."""

    hamming: float
    """The Hamming distance of the detected tag. Lower values indicate a more accurate detection."""

    tagPose_screenSpace: List[float]
    """Estimated pose of the detected AprilTag in screen space."""

    def __hash__(self) -> int:
        return hash(
            (
                self.tag_id,
                self.hamming,
                tuple(self.tagPose_screenSpace),
            )
        )


@dataclass(frozen=True)
class ApriltagResult:
    """
    Represents the result of detecting AprilTags in a single frame or input source.

    This class contains the list of detected tags and an estimate of the camera's
    pose in field space. It is typically produced by an AprilTag pipeline.
    """

    tags: List[ApriltagDetection]
    """The detected AprilTags with their associated detection data."""

    cameraEstimate_fieldSpace: List[float]
    """The estimated camera pose in field space, format (x, y, z, roll, pitch, yaw)."""

    reprojection_error: float
    """The reprojection error of the camera pose estimate. """

    def __hash__(self) -> int:
        return hash(
            (
                tuple(self.tags),
                tuple(self.cameraEstimate_fieldSpace),
                self.reprojection_error,
            )
        )
