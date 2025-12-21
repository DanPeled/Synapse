# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ApriltagPoseEstimate:
    """
    Represents the candidate 3D pose estimates of an AprilTag detection.

    When estimating the pose of an AprilTag, the algorithm may return two possible
    solutions due to perspective ambiguity. This class stores both candidate poses
    along with their associated error metrics, allowing downstream logic to
    determine which pose is more reliable.

    Each pose is represented as a 6-element tuple of floats:
    (x, y, z, roll, pitch, yaw).
    """

    acceptedError: float
    """The error metric associated with `acceptedPose`. Lower values indicate higher confidence."""

    rejectedError: float
    """The error metric associated with `rejectedPose`. Lower values indicate higher confidence."""

    acceptedPose: List[float]
    """The first possible 3D pose of the AprilTag relative to the camera frame."""

    rejectedPose: List[float]
    """The second possible 3D pose, typically the ambiguous alternative."""

    def __hash__(self) -> int:
        return hash(
            (
                self.acceptedError,
                self.rejectedError,
                tuple(self.acceptedPose),
                tuple(self.rejectedPose),
            )
        )


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

    cameraPose_fieldSpace: List[float]
    """The estimated pose of the camera in the field coordinate system."""

    cameraPose_tagSpace: List[float]
    """The estimated pose of the camera relative to the detected tag."""

    tagPose_screenSpace: List[float]
    """The estimated pose of the tag in screen coordinates."""

    tag_estimate: ApriltagPoseEstimate
    """The estimated pose(s) of the detected AprilTag, including multiple hypotheses."""

    def __hash__(self) -> int:
        return hash(
            (
                self.tag_id,
                self.hamming,
                tuple(self.cameraPose_fieldSpace),
                tuple(self.cameraPose_tagSpace),
                tuple(self.tagPose_screenSpace),
                self.tag_estimate,
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

    def __hash__(self) -> int:
        return hash((tuple(self.tags), tuple(self.cameraEstimate_fieldSpace)))
