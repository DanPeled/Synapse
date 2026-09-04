# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from typing import List

import robotpy_apriltag as rpy_apriltag
from typing_extensions import Buffer

from .apriltag_detector import AprilTagDetection, AprilTagDetector, makeCorners


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
