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
from wpimath import units
from wpimath.geometry import Pose3d, Rotation3d, Transform3d, Translation3d


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
        corner_0 = tagPose + Transform3d(
            Translation3d(0, tagSize / 2.0, -tagSize / 2.0), Rotation3d()
        )
        corner_1 = tagPose + Transform3d(
            Translation3d(0, -tagSize / 2.0, -tagSize / 2.0), Rotation3d()
        )
        corner_2 = tagPose + Transform3d(
            Translation3d(0, -tagSize / 2.0, tagSize / 2.0), Rotation3d()
        )
        corner_3 = tagPose + Transform3d(
            Translation3d(0, tagSize / 2.0, tagSize / 2.0), Rotation3d()
        )

        return [
            wpilibTranslationToOpenCv(corner_0.translation()),
            wpilibTranslationToOpenCv(corner_1.translation()),
            wpilibTranslationToOpenCv(corner_2.translation()),
            wpilibTranslationToOpenCv(corner_3.translation()),
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

        _, rvecs, tvecs, errors = cv2.solvePnPGeneric(
            objectPoints,
            imagePoints,
            self.config.cameraMatrix,
            self.config.distCoeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
            if len(tags) == 1
            else cv2.SOLVEPNP_ITERATIVE,
        )

        best = int(np.argmin(errors))

        camera_to_field_pose = openCvPoseToWpilib(tvecs[best], rvecs[best])
        camera_to_field = Transform3d(
            camera_to_field_pose.translation(), camera_to_field_pose.rotation()
        )
        field_to_camera = camera_to_field.inverse()
        field_to_camera_pose = Pose3d(
            field_to_camera.translation(), field_to_camera.rotation()
        )

        return CameraPoseEstimate(float(errors[best]), field_to_camera_pose)


def openCvPoseToWpilib(tvec: np.ndarray, rvec: np.ndarray) -> Pose3d:
    return Pose3d(
        Translation3d(tvec[2][0], -tvec[0][0], -tvec[1][0]),
        Rotation3d(
            np.array([rvec[2][0], -rvec[0][0], -rvec[1][0]]),
            math.sqrt(
                math.pow(rvec[0][0], 2)
                + math.pow(rvec[1][0], 2)
                + math.pow(rvec[2][0], 2)
            ),
        ),
    )


def wpilibTranslationToOpenCv(translation: Translation3d) -> List[float]:
    return [-translation.Y(), -translation.Z(), translation.X()]
