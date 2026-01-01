# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
from synapse.core.pipeline import Pipeline, PipelineResult
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, PipelineSettings,
                                       settingField)
from synapse.stypes import Frame


class ColorDetectSettings(PipelineSettings):
    """
    Settings for the Color Detection Pipeline.

    Attributes:
        h_lower, s_lower, v_lower: Lower bounds for HSV thresholding.
        h_upper, s_upper, v_upper: Upper bounds for HSV thresholding.
        morph_kernel: Kernel size for morphological operations.
        min_area: Minimum contour area to consider a detection.
        result_strategy: Strategy to select the primary detection.
        publish_all_detections: Whether to send all detections or only the main one.
    """

    h_lower = settingField(
        NumberConstraint(minValue=0, maxValue=179),
        default=0,
        description="Lower bound for hue (0-179)",
    )
    s_lower = settingField(
        NumberConstraint(minValue=0, maxValue=255),
        default=100,
        description="Lower bound for saturation (0-255)",
    )
    v_lower = settingField(
        NumberConstraint(minValue=0, maxValue=255),
        default=100,
        description="Lower bound for value (0-255)",
    )

    h_upper = settingField(
        NumberConstraint(minValue=0, maxValue=179),
        default=10,
        description="Upper bound for hue (0-179)",
    )
    s_upper = settingField(
        NumberConstraint(minValue=0, maxValue=255),
        default=255,
        description="Upper bound for saturation (0-255)",
    )
    v_upper = settingField(
        NumberConstraint(minValue=0, maxValue=255),
        default=255,
        description="Upper bound for value (0-255)",
    )

    morph_kernel = settingField(
        NumberConstraint(minValue=1, maxValue=20, step=1),
        default=5,
        description="Kernel size for morphological opening and closing",
    )
    min_area = settingField(
        NumberConstraint(minValue=0, maxValue=None),
        default=500,
        description="Minimum contour area to be considered a valid detection",
    )

    result_strategy = settingField(
        EnumeratedConstraint(
            options=["largest_area", "closest_to_center", "first_detected"]
        ),
        default="largest_area",
        description="Strategy to select the primary detection from all detections",
    )

    publish_all_detections = settingField(
        BooleanConstraint(),
        default=True,
        description="If True, all detections will be sent; otherwise, only the main detection is sent.",
    )


@dataclass
class ColorDetection:
    """
    Represents a single color detection result.

    Attributes:
        bbox: Bounding box [x, y, w, h]
        center: Center of the detection [x, y]
        area: Area of the detected contour
    """

    bbox: List[float]
    center: List[float]
    area: float


@dataclass
class ColorResult(PipelineResult):
    """
    Holds all color detections for a single frame.

    Attributes:
        detections: List of ColorDetection objects
        main_detection: The selected primary detection (optional)
    """

    timestamp: float
    detections: List[ColorDetection]
    main_detection: Optional[ColorDetection] = None


class ColorPipeline(Pipeline[ColorDetectSettings, ColorResult]):
    """
    Pipeline for detecting objects of a specific color using HSV thresholds.
    """

    def __init__(self, settings: ColorDetectSettings):
        super().__init__(settings)

    def _createMask(self, hsv: np.ndarray) -> np.ndarray:
        """Apply HSV thresholding and morphological operations to generate a mask."""
        lower = np.array(
            [
                self.getSetting(self.settings.h_lower),
                self.getSetting(self.settings.s_lower),
                self.getSetting(self.settings.v_lower),
            ],
            dtype=np.uint8,
        )

        upper = np.array(
            [
                self.getSetting(self.settings.h_upper),
                self.getSetting(self.settings.s_upper),
                self.getSetting(self.settings.v_upper),
            ],
            dtype=np.uint8,
        )

        mask = cv2.inRange(hsv, lower, upper)
        k = int(self.getSetting(self.settings.morph_kernel))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask

    def _findDetections(self, mask: np.ndarray) -> List[ColorDetection]:
        """Find contours in the mask and convert them into ColorDetection objects."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = self.getSetting(self.settings.min_area)
        detections = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            center = [x + w / 2, y + h / 2]
            detections.append(
                ColorDetection(bbox=[x, y, w, h], center=center, area=area)
            )

        return detections

    def _selectMainDetection(
        self, detections: List[ColorDetection], frame_shape
    ) -> Optional[ColorDetection]:
        """Select the main detection based on the chosen strategy."""
        if not detections:
            return None

        strategy = self.getSetting(self.settings.result_strategy)
        if strategy == "largest_area":
            return max(detections, key=lambda d: d.area)
        elif strategy == "closest_to_center":
            frame_center = (frame_shape[1] / 2, frame_shape[0] / 2)
            return min(
                detections,
                key=lambda d: (d.center[0] - frame_center[0]) ** 2
                + (d.center[1] - frame_center[1]) ** 2,
            )
        elif strategy == "first_detected":
            return detections[0]

        return None

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        """
        Processes a frame to detect objects and returns an annotated frame.

        Args:
            img: Input frame (BGR format)
            timestamp: Frame timestamp

        Returns:
            Annotated frame with bounding boxes.
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = self._createMask(hsv)
        detections = self._findDetections(mask)
        main_detection = self._selectMainDetection(detections, img.shape)

        # Draw detections
        output = img.copy()
        publish_all = self.getSetting(self.settings.publish_all_detections)
        for det in detections:
            if det == main_detection:
                color = (0, 0, 255)  # Red for main
            else:
                color = (0, 255, 0)  # Green for others
            if publish_all or det == main_detection:
                x, y, w, h = det.bbox
                cv2.rectangle(
                    output, (int(x), int(y)), (int(x + w), int(y + h)), color, 2
                )

        # Publish results
        result = ColorResult(
            timestamp=timestamp,
            detections=detections
            if publish_all
            else ([main_detection] if main_detection else []),
            main_detection=main_detection,
        )
        self.setResults(result)

        return output
