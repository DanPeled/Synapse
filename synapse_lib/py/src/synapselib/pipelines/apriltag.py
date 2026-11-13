# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Optional

from wpimath.geometry import Pose3d, Rotation3d, Translation3d


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

    hamming: int
    """The Hamming distance of the detected tag. Lower values indicate a more accurate detection."""

    tagPose_screenSpace: List[float]
    """Center of the detected tag in screen space, as ``[x, y]`` pixels."""

    @property
    def tx(self) -> float:
        """Returns the tag's horizontal position in screen space."""
        return self.tagPose_screenSpace[0]

    @property
    def ty(self) -> float:
        """Returns the tag's vertical position in screen space."""
        return self.tagPose_screenSpace[1]

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

    cameraEstimate_fieldSpace: Optional[List[float]]
    """The estimated camera pose in field space as ``[x, y, z, roll, pitch, yaw]``.

    ``None`` when the pipeline could not estimate a pose for the frame.
    """

    reprojection_error: float
    """The reprojection error of the camera pose estimate. ``0.0`` when unavailable."""

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
            rotation=Rotation3d(estimate[3], estimate[4], estimate[5]),
        )

    def __hash__(self) -> int:
        estimate = (
            tuple(self.cameraEstimate_fieldSpace)
            if self.cameraEstimate_fieldSpace is not None
            else None
        )
        return hash((tuple(self.tags), estimate, self.reprojection_error))
