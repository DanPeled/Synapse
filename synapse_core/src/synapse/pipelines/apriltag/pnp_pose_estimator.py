# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from dataclasses import dataclass
from typing import Callable, List, Optional

import cv2
import numpy as np
from synapse.pipelines.apriltag.apriltag_detector import CameraPoseEstimate
from synapse.pipelines.apriltag.apriltag_robotpy import AprilTagDetection
from synapse.pipelines.apriltag.field_loader import TagId
from wpimath import Pose3d, Rotation3d, Transform3d, Translation3d, units


class PnPPoseEstimator:
    @dataclass
    class Config:
        tagSize: units.meters
        cameraMatrix: np.ndarray
        distCoeffs: np.ndarray
        method: int = cv2.SOLVEPNP_SQPNP

    def __init__(self, config: Config) -> None:
        self.config = config

    def __getObjectPoints(
        self,
        tagPose: Pose3d,
        tagSize: units.meters,
    ) -> List:
        """Return field corners in upstream AprilTag order.

        Detections expose corners as bottom-left, bottom-right, top-right,
        top-left. In WPILib tag-local coordinates, +Y points left and +Z points
        up, so bottom-left is at positive local Y and negative local Z.
        """
        halfSize = tagSize / 2.0
        corners = (
            (0.0, halfSize, -halfSize),
            (0.0, -halfSize, -halfSize),
            (0.0, -halfSize, halfSize),
            (0.0, halfSize, halfSize),
        )
        return [
            wpilibTranslationToOpenCv(
                (
                    tagPose + Transform3d(Translation3d(*corner), Rotation3d())
                ).translation()
            )
            for corner in corners
        ]

    def setConfig(self, config: Config) -> None:
        self.config = config

    def estimate(
        self,
        tags: List[AprilTagDetection],
        getTagPose: Callable[[TagId], Pose3d | None],
    ) -> Optional[CameraPoseEstimate]:
        objectPoints = []
        imagePoints = []

        if len(tags) == 0:
            return None

        for tag in tags:
            tagPose = getTagPose(tag.tagID)

            if tagPose is None:
                continue

            objectPoints.extend(self.__getObjectPoints(tagPose, self.config.tagSize))

            imagePoints.extend(tag.corners)

        if len(objectPoints) < 4:
            return None

        objectPoints = np.asarray(objectPoints, dtype=np.float64).reshape(-1, 3)
        imagePoints = np.asarray(imagePoints, dtype=np.float64).reshape(-1, 2)

        # IPPE_SQUARE expects a centred square in object space. The object
        # points here are absolute field coordinates and may be rotated with
        # the tag, so it produces an incorrect pose for a single tag. SQPNP
        # handles that case without an initial estimate.
        flags = cv2.SOLVEPNP_SQPNP if len(tags) == 1 else cv2.SOLVEPNP_ITERATIVE
        _, rvecs, tvecs, errors = cv2.solvePnPGeneric(
            objectPoints,
            imagePoints,
            self.config.cameraMatrix,
            self.config.distCoeffs,
            flags=flags,
        )

        errorArray = np.asarray(errors).reshape(-1)
        best = int(np.argmin(errorArray))

        # openCvPoseToWpilib returns the field-to-camera transform; invert it
        # to publish the camera pose in field coordinates.
        fieldToCamera = openCvPoseToWpilib(tvecs[best], rvecs[best])
        cameraPose = Transform3d(
            fieldToCamera.translation(), fieldToCamera.rotation()
        ).inverse()
        return CameraPoseEstimate(
            float(errorArray[best]),
            Pose3d(cameraPose.translation(), cameraPose.rotation()),
        )


def openCvPoseToWpilib(tvec: np.ndarray, rvec: np.ndarray) -> Pose3d:
    """Convert an OpenCV field-to-camera transform to WPILib coordinates."""
    return Pose3d(
        Translation3d(tvec[2][0], -tvec[0][0], -tvec[1][0]),
        Rotation3d(
            np.array([rvec[2][0], -rvec[0][0], -rvec[1][0]]),
            math.sqrt(rvec[0][0] ** 2 + rvec[1][0] ** 2 + rvec[2][0] ** 2),
        ),
    )


def wpilibTranslationToOpenCv(translation: Translation3d) -> List[float]:
    return [-translation.Y(), -translation.Z(), translation.X()]
