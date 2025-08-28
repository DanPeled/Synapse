# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

import robotpy_apriltag as rpy_apriltag
from typing_extensions import Buffer

from .apriltag_detector import AprilTagDetection, AprilTagDetector, makeCorners


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
                ),
                self.detector.detect(frame),
            )
        )

    def addFamily(self, fam: str) -> None:
        self.detector.addFamily(fam)

    def setConfig(self, config: AprilTagDetector.Config) -> None:
        rpy_config = rpy_apriltag.AprilTagDetector.Config()

        rpy_config.quadDecimate = config.quadDecimate
        rpy_config.quadSigma = config.quadSigma
        rpy_config.refineEdges = config.refineEdges
        rpy_config.numThreads = config.numThreads

        self.detector.setConfig(rpy_config)
