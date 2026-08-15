# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from typing import List

import robotpy_apriltag as rpy_apriltag
from typing_extensions import Buffer

from .apriltag_detector import (AprilTagDetection, AprilTagDetector,
                                ApriltagPoseEstimate, ApriltagPoseEstimator,
                                makeCorners)


class RobotpyApriltagDetector(AprilTagDetector):
    def __init__(self) -> None:
        self.detector: rpy_apriltag.AprilTagDetector = rpy_apriltag.AprilTagDetector()
        self.lock = threading.Lock()
        self.cornersTemplate = makeCorners()

    def detect(self, frame: Buffer) -> List[AprilTagDetection]:
        with self.lock:
            detections_raw = self.detector.detect(frame)

            detections = []
            for detection in detections_raw:
                center = detection.getCenter()

                detections.append(
                    AprilTagDetection(
                        tagID=detection.getId(),
                        homography=detection.getHomography(),
                        corners=detection.getCorners(self.cornersTemplate),
                        center=(int(center.x), int(center.y)),
                        hamming=detection.getHamming(),
                    )
                )

        return detections

    def setFamily(self, fam: str) -> None:
        with self.lock:
            self.detector.clearFamilies()
            self.detector.addFamily(fam)

    def setConfig(self, config: AprilTagDetector.Config) -> None:
        with self.lock:
            rpy_config = rpy_apriltag.AprilTagDetector.Config()

            rpy_config.quadDecimate = float(config.quadDecimate)
            rpy_config.quadSigma = config.quadSigma
            rpy_config.refineEdges = config.refineEdges
            rpy_config.numThreads = config.numThreads

            quad_params = self.detector.getQuadThresholdParameters()
            quad_params.criticalAngle = config.criticalAngle
            quad_params.deglitch = config.deglitch
            quad_params.maxLineFitMSE = config.maxLineFitMSE
            quad_params.maxNumMaxima = config.maxNumMaxima
            quad_params.minClusterPixels = config.minClusterPixels
            quad_params.minWhiteBlackDiff = config.minWhiteBlackDiff

            self.detector.setConfig(rpy_config)
            self.detector.setQuadThresholdParameters(quad_params)

    def getConfig(self) -> AprilTagDetector.Config:
        with self.lock:
            config = self.detector.getConfig()

            return self.Config(
                config.numThreads,
                config.refineEdges,
                config.quadDecimate,
                config.quadSigma,
            )


class RobotpyApriltagPoseEstimator(ApriltagPoseEstimator):
    def __init__(self, config: ApriltagPoseEstimator.Config) -> None:
        self.estimator = rpy_apriltag.AprilTagPoseEstimator(
            rpy_apriltag.AprilTagPoseEstimator.Config(
                config.tagSize,
                config.fx,
                config.fy,
                config.cx,
                config.cy,
            )
        )
        self.lock = threading.Lock()

    def estimate(
        self, tagDetection: AprilTagDetection, nIters: int
    ) -> ApriltagPoseEstimate:
        with self.lock:
            estimate = self.estimator.estimateOrthogonalIteration(
                tagDetection.homography,
                tagDetection.corners,
                nIters,
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
        with self.lock:
            estimatorConfig = self.estimator.getConfig()
            estimatorConfig.tagSize = config.tagSize
            estimatorConfig.fx = config.fx
            estimatorConfig.fy = config.fy
            estimatorConfig.cx = config.cx
            estimatorConfig.cy = config.cy
            self.estimator.setConfig(estimatorConfig)

    def getConfig(self) -> ApriltagPoseEstimator.Config:
        with self.lock:
            config = self.estimator.getConfig()

            return ApriltagPoseEstimator.Config(
                config.cx,
                config.cy,
                config.fx,
                config.fy,
                config.tagSize,
            )
