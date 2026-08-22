from dataclasses import dataclass
from typing import Callable, List, Tuple

import cv2
import numpy as np
from synapse.pipelines.apriltag.apriltag_robotpy import AprilTagDetection
from wpimath import units
from wpimath.geometry import Pose3d, Rotation3d, Transform3d, Translation3d
from synapse.pipelines.apriltag.field_loader import TagId


class PnPPoseEstimator:
    @dataclass
    class Config:
        tagSize: units.meters
        cameraMatrix: np.ndarray
        distCoeffs: np.ndarray
        method: int = cv2.SOLVEPNP_IPPE_SQUARE

    def __init__(self, config: Config) -> None:
        self.config = config

    def __getObjectPoints(
        self,
        tagPose: Pose3d,
        tagSize: units.meters,
    ) -> np.ndarray:
        half = tagSize / 2.0

        localCorners = (
            Translation3d(-half, half, 0.0),
            Translation3d(half, half, 0.0),
            Translation3d(half, -half, 0.0),
            Translation3d(-half, -half, 0.0),
        )

        return np.array(
            [
                [
                    tagPose.transformBy(Transform3d(corner, Rotation3d()))
                    .translation()
                    .X(),
                    tagPose.transformBy(Transform3d(corner, Rotation3d()))
                    .translation()
                    .Y(),
                    tagPose.transformBy(Transform3d(corner, Rotation3d()))
                    .translation()
                    .Z(),
                ]
                for corner in localCorners
            ],
            dtype=np.float64,
        )

    def setConfig(self, config: Config) -> None:
        self.config = config

    def estimate(
        self,
        tags: List[AprilTagDetection],
        getTagPose: Callable[[TagId], Pose3d | None],
    ) -> Tuple[np.ndarray, np.ndarray] | None:
        objectPoints = []
        imagePoints = []

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

        success, rvec, tvec = cv2.solvePnP(
            objectPoints,
            imagePoints,
            self.config.cameraMatrix,
            self.config.distCoeffs,
            flags=self.config.method,
        )

        if not success:
            return None

        return rvec, tvec
