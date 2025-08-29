# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
from synapse.stypes import Frame
from typing_extensions import Buffer
from wpimath.geometry import Pose3d, Rotation3d, Transform3d, Translation3d

Homography = Tuple[float, float, float, float, float, float, float, float, float]
Corners = Tuple[float, float, float, float, float, float, float, float]


@dataclass
class RobotPoseEstimate:
    robotPose_tagSpace: Transform3d
    robotPose_fieldSpace: Pose3d


def makeCorners(
    x0: float = 0.0,
    y0: float = 0.0,
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 0.0,
    y2: float = 0.0,
    x3: float = 0.0,
    y3: float = 0.0,
) -> Corners:
    """
    Constructs a Corners tuple with 8 float values.
    Defaults to all zeros if no arguments are provided.
    """
    return (x0, y0, x1, y1, x2, y2, x3, y3)


@dataclass(frozen=True)
class AprilTagDetection:
    tagID: int
    homography: Homography
    hamming: int
    corners: Corners
    center: Tuple[int, int]


class AprilTagDetector(ABC):
    @dataclass
    class Config:
        numThreads: int = 1
        refineEdges: bool = True
        quadDecimate: float = 2.0
        quadSigma: float = 0.0

    @abstractmethod
    def detect(self, frame: Buffer) -> List[AprilTagDetection]: ...

    @abstractmethod
    def setFamily(self, fam: str) -> None: ...

    @abstractmethod
    def setConfig(self, config: Config) -> None: ...


def drawTagDetectionMarker(
    tag: AprilTagDetection,
    img: Frame,
) -> None:
    """Draws a 2D bounding box for the AprilTag using corners as a flat tuple."""
    # Convert flat tuple to 4 (x, y) points
    corners = np.array(tag.corners, dtype=int).reshape(4, 2)

    # Draw the boundary
    for i in range(4):
        pt1 = tuple(corners[i])
        pt2 = tuple(corners[(i + 1) % 4])
        cv2.line(img, pt1, pt2, color=(0, 255, 0), thickness=2)

    # Draw the center
    center_x = int(sum(c[0] for c in corners) / 4)
    center_y = int(sum(c[1] for c in corners) / 4)
    cv2.circle(img, (center_x, center_y), radius=4, color=(0, 0, 255), thickness=-1)

    # Draw the tag ID above the tag
    tag_id = tag.tagID
    cv2.putText(
        img,
        str(tag_id),
        (center_x - 10, center_y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )


def tagToRobotPose(
    tagFieldPose: Pose3d,
    cameraToRobotTransform: Transform3d,
    cameraToTagTransform: Transform3d,
) -> RobotPoseEstimate:
    """
    Computes the robot's pose on the field based on the tag's pose in field coordinates.
    It transforms the pose through the camera and robot coordinate systems.
    """
    robotInTagSpace: Transform3d = (
        cameraToTagTransform.inverse() + cameraToRobotTransform
    )
    robotInField: Pose3d = tagFieldPose.transformBy(robotInTagSpace)
    return RobotPoseEstimate(robotInTagSpace, robotInField)


def opencvToWPI(opencv: Transform3d) -> Transform3d:
    return Transform3d(  # NOTE: Should be correct
        translation=Translation3d(
            x=opencv.X(),
            y=opencv.Z(),
            z=opencv.Y(),
        ),
        rotation=Rotation3d(
            roll=opencv.rotation().Z(),
            pitch=opencv.rotation().X(),
            yaw=opencv.rotation().Y(),
        ),
    )
