# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

import robotpy_apriltag as rpy_apriltag
from typing_extensions import Buffer

from .apriltag_detector import (AprilTagDetection, AprilTagDetector,
                                ApriltagPoseEstimate, ApriltagPoseEstimator,
                                makeCorners)


class RobotpyApriltagDetector(AprilTagDetector):
    def __init__(self) -> None:
        self.detector: rpy_apriltag.AprilTagDetector = rpy_apriltag.AprilTagDetector()

    def detect(self, frame: Buffer) -> List[AprilTagDetection]:
        return list(
            map(
                lambda detection: AprilTagDetection(
                    tagID=detection.getId(),
                    homography=detection.getHomography(),
                    corners=detection.getCorners(makeCorners()),
                    center=(int(detection.getCenter().x), int(detection.getCenter().y)),
                    hamming=detection.getHamming(),
                ),
                self.detector.detect(frame),
            )
        )

    def setFamily(self, fam: str) -> None:
        self.detector.clearFamilies()
        self.detector.addFamily(fam)

    def setConfig(self, config: AprilTagDetector.Config) -> None:
        rpy_config = rpy_apriltag.AprilTagDetector.Config()

        rpy_config.quadDecimate = config.quadDecimate
        rpy_config.quadSigma = config.quadSigma
        rpy_config.refineEdges = config.refineEdges
        rpy_config.numThreads = config.numThreads

        self.detector.setConfig(rpy_config)

    def getConfig(self) -> AprilTagDetector.Config:
        config = self.detector.getConfig()
        return self.Config(
            config.numThreads, config.refineEdges, config.quadDecimate, config.quadSigma
        )


class RobotpyApriltagPoseEstimator(ApriltagPoseEstimator):
    def __init__(self, config: ApriltagPoseEstimator.Config) -> None:
        self.estimator: rpy_apriltag.AprilTagPoseEstimator = (
            rpy_apriltag.AprilTagPoseEstimator(
                rpy_apriltag.AprilTagPoseEstimator.Config(
                    config.tagSize, config.fx, config.fy, config.cx, config.cy
                )
            )
        )

    def estimate(
        self, tagDetection: AprilTagDetection, nIters: int
    ) -> ApriltagPoseEstimate:
        estimate = self.estimator.estimateOrthogonalIteration(
            tagDetection.homography, tagDetection.corners, nIters
        )
        rejected, rejectedErr = estimate.pose1, estimate.error1
        accepted, acceptedErr = estimate.pose2, estimate.error2
        if estimate.error1 < estimate.error2:
            rejected, rejectedErr = estimate.pose2, estimate.error2
            accepted, acceptedErr = estimate.pose1, estimate.error1

        return ApriltagPoseEstimate(
            estimate.getAmbiguity(),
            acceptedPose=accepted,
            acceptedError=acceptedErr,
            rejectedPose=rejected,
            rejectedError=rejectedErr,
        )

    def setConfig(self, config: ApriltagPoseEstimator.Config) -> None:
        estimatorConfig = self.estimator.getConfig()
        estimatorConfig.tagSize = config.tagSize
        estimatorConfig.fx = config.fx
        estimatorConfig.fy = config.fy
        estimatorConfig.cx = config.cx
        estimatorConfig.cy = config.cy

    def getConfig(self) -> ApriltagPoseEstimator.Config:
        config = self.estimator.getConfig()
        return ApriltagPoseEstimator.Config(
            config.cx, config.cy, config.fx, config.fy, config.tagSize
        )
