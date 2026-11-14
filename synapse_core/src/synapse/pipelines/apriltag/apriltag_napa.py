# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from dataclasses import replace
from typing import List, Optional, cast

import numpy as np
from typing_extensions import Buffer

from .apriltag_detector import (
    AprilTagDetection,
    AprilTagDetector,
    Homography,
    makeCorners,
)


class NapaApriltagDetector(AprilTagDetector):
    """AprilTag detector backed by NAPA (https://github.com/zwatx/NAPA).

    NAPA only performs detection; pose estimation is still handled by the
    pipeline's shared PnP estimator. The native detector is configured at
    construction time, so changing the family or any NAPA-specific setting
    rebuilds it.
    """

    def __init__(
        self,
        family: str = "tag36h11",
        config: Optional[AprilTagDetector.Config] = None,
    ) -> None:
        self.lock = threading.Lock()
        self._family = family
        self._config = replace(config or self.Config())
        self._detector = self._createDetector(self._family, self._config)

    @staticmethod
    def _createDetector(family: str, config: AprilTagDetector.Config):
        # Imported lazily so the rest of Synapse still works when NAPA is not
        # installed (for example when another detector backend is selected).
        from napa_vision import NapaDetector

        return NapaDetector(
            family=family,
            min_tag_px=int(config.minTagPx),
            max_hamming=config.maxHamming,
            min_contrast=int(config.minContrast),
            min_border_cells=int(config.minBorderCells),
            sharpening=float(config.sharpening),
            max_detections=int(config.maxDetections),
        )

    @staticmethod
    def _napaConfigKey(config: AprilTagDetector.Config) -> tuple:
        return (
            config.minTagPx,
            config.maxHamming,
            config.minContrast,
            config.minBorderCells,
            config.sharpening,
            config.maxDetections,
        )

    def _replaceDetector(self, family: str, config: AprilTagDetector.Config) -> None:
        # Build the replacement first so a bad configuration leaves the current
        # detector usable.
        detector = self._createDetector(family, config)
        oldDetector = self._detector

        self._family = family
        self._config = config
        self._detector = detector

        oldDetector.close()

    def detect(self, frame: Buffer) -> List[AprilTagDetection]:
        with self.lock:
            observations = self._detector.detect(np.asarray(frame))

            detections: List[AprilTagDetection] = []
            for observation in observations:
                # NAPA returns corners in OpenCV's AprilTag order
                # (bottom-right, bottom-left, top-left, top-right). WPILib's
                # detectors return them as bottom-left, bottom-right, top-right,
                # top-left, which is what the rest of the pipeline expects.
                corners = observation.corners
                orderedCorners = (corners[1], corners[0], corners[3], corners[2])

                # NAPA computes both lazily from the corners; read the
                # homography once and take the centre from it.
                homography = observation.homography
                center = homography[:2, 2]

                detections.append(
                    AprilTagDetection(
                        tagID=int(observation.tag_id),
                        homography=cast(
                            Homography,
                            tuple(float(value) for value in homography.reshape(-1)),
                        ),
                        hamming=int(observation.hamming or 0),
                        corners=makeCorners(
                            float(orderedCorners[0][0]),
                            float(orderedCorners[0][1]),
                            float(orderedCorners[1][0]),
                            float(orderedCorners[1][1]),
                            float(orderedCorners[2][0]),
                            float(orderedCorners[2][1]),
                            float(orderedCorners[3][0]),
                            float(orderedCorners[3][1]),
                        ),
                        center=(
                            int(round(float(center[0]))),
                            int(round(float(center[1]))),
                        ),
                    )
                )

            return detections

    def setFamily(self, fam: str) -> None:
        with self.lock:
            if fam == self._family:
                return

            self._replaceDetector(fam, self._config)

    def setConfig(self, config: AprilTagDetector.Config) -> None:
        with self.lock:
            newConfig = replace(config)

            if self._napaConfigKey(newConfig) == self._napaConfigKey(self._config):
                self._config = newConfig
                return

            self._replaceDetector(self._family, newConfig)

    def getConfig(self) -> AprilTagDetector.Config:
        with self.lock:
            return replace(self._config)

    def close(self) -> None:
        with self.lock:
            self._detector.close()
