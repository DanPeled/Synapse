# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import PipelineResult
from synapse.core.settings_api import NumberConstraint, settingField
from synapse.stypes import Frame


# ---------------- Settings ---------------- #
class BullseyeTrackerSettings(PipelineSettings):
    darkThreshold = settingField(NumberConstraint(0, 255, 1), default=128)
    minContourArea = settingField(NumberConstraint(0, None, 1), default=100)
    maxContourArea = settingField(NumberConstraint(0, None, 1), default=50000)
    centerWeighting = settingField(NumberConstraint(0, 1, 0.01), default=1.0)
    minCircularity = settingField(NumberConstraint(0, 1, 0.01), default=0.7)
    concentricThreshold = settingField(NumberConstraint(0, 1, 0.01), default=0.3)
    minCircles = settingField(NumberConstraint(1, 20, 1), default=2)
    maxCircles = settingField(NumberConstraint(1, 20, 1), default=4)


# ---------------- Data Classes ---------------- #
@dataclass
class CircleData:
    cx: float
    cy: float
    radius: float
    centroidX: float
    centroidY: float
    circularity: float
    axisRatio: float
    area: float
    contour: np.ndarray


@dataclass
class BullseyeResult(PipelineResult):
    hasResult: bool
    area: float
    position: List[float]
    axisRatios: List[float]
    circularities: List[float]


# ---------------- Pipeline ---------------- #
class BullseyeTrackerPipeline(Pipeline[BullseyeTrackerSettings, BullseyeResult]):
    def __init__(self, settings: BullseyeTrackerSettings):
        super().__init__(settings)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def processFrame(self, img, timestamp: float) -> Frame:
        results = self.getBullseyeCenter(img, showDebug=True)
        self.setResults(results)
        return img

    def getCentroid(self, contour: np.ndarray) -> Tuple[float, float]:
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return 0.0, 0.0
        return M["m10"] / M["m00"], M["m01"] / M["m00"]

    def getBullseyeCenter(
        self, frame: Frame, showDebug: bool = False
    ) -> BullseyeResult:
        """Detect black/white bullseye and compute its screen offset."""
        h, w = frame.shape[:2]
        screenCx, screenCy = w / 2, h / 2

        # Load settings
        darkThreshold = self.getSetting(self.settings.darkThreshold)
        minContourArea = self.getSetting(self.settings.minContourArea)
        maxContourArea = self.getSetting(self.settings.maxContourArea)
        centerWeighting = self.getSetting(self.settings.centerWeighting)
        minCircularity = self.getSetting(self.settings.minCircularity)
        concentricThreshold = self.getSetting(self.settings.concentricThreshold)
        minC = self.getSetting(self.settings.minCircles)
        maxC = self.getSetting(self.settings.maxCircles)

        # Grayscale and threshold
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, darkThreshold, 255, cv2.THRESH_BINARY)

        # Morphology to remove noise
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self._kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self._kernel)

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        circles: List[CircleData] = []
        circularities: List[float] = []
        axisRatios: List[float] = []

        # Analyze each contour
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < minContourArea or area > maxContourArea or len(contour) < 5:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue

            circularity = 4 * np.pi * area / (perimeter**2)
            if circularity < minCircularity:
                continue

            x, y, wRect, hRect = cv2.boundingRect(contour)
            axisRatio = min(wRect, hRect) / max(wRect, hRect)

            (cx, cy), radius = cv2.minEnclosingCircle(contour)
            centroidX = (x + x + wRect) / 2
            centroidY = (y + y + hRect) / 2

            circle = CircleData(
                cx=cx,
                cy=cy,
                radius=radius,
                centroidX=centroidX,
                centroidY=centroidY,
                circularity=circularity,
                axisRatio=axisRatio,
                area=area,
                contour=contour,
            )

            circles.append(circle)
            circularities.append(circularity)
            axisRatios.append(axisRatio)

        # sort large → small
        circles.sort(key=lambda c: c.radius, reverse=True)

        bestBullseye: Optional[CircleData] = None
        bestScore = 0

        # --- Find groups of concentric circles with radius ordering ---
        for i in range(len(circles)):
            outer = circles[i]
            group = [outer]

            for j in range(i + 1, len(circles)):
                cand = circles[j]

                centerDistance = math.hypot(outer.cx - cand.cx, outer.cy - cand.cy)
                radiusRatio = cand.radius / outer.radius

                if (
                    centerDistance < outer.radius * concentricThreshold
                    and radiusRatio < 1.0  # must be smaller
                ):
                    group.append(cand)

                if len(group) == maxC:  # reached allowed maximum
                    break

            # Not enough circles
            if not (minC <= len(group) <= maxC):
                continue

            # Compute group metrics
            avgCx = sum(c.cx for c in group) / len(group)
            avgCy = sum(c.cy for c in group) / len(group)
            avgCirc = sum(c.circularity for c in group) / len(group)
            avgAxis = sum(c.axisRatio for c in group) / len(group)

            largest = group[0]  # sorted by radius → biggest is first
            distToCenter = math.hypot(avgCx - screenCx, avgCy - screenCy)

            score = avgCirc * avgAxis * (1 / (1 + distToCenter / 100 * centerWeighting))

            if score > bestScore:
                bestScore = score
                bestBullseye = CircleData(
                    cx=avgCx,
                    cy=avgCy,
                    radius=largest.radius,
                    centroidX=avgCx,
                    centroidY=avgCy,
                    circularity=avgCirc,
                    axisRatio=avgAxis,
                    area=sum(c.area for c in group),
                    contour=largest.contour,
                )

        # Debug visualization
        if showDebug and bestBullseye:
            cv2.circle(
                frame,
                (int(bestBullseye.cx), int(bestBullseye.cy)),
                int(bestBullseye.radius),
                (0, 255, 0),
                2,
            )
            cv2.circle(
                frame, (int(bestBullseye.cx), int(bestBullseye.cy)), 5, (0, 0, 255), -1
            )
            cv2.putText(
                frame,
                "BULLSEYE",
                (
                    int(bestBullseye.cx - 40),
                    int(bestBullseye.cy - bestBullseye.radius - 10),
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

        # Output center offset
        if bestBullseye:
            dx = bestBullseye.cx - screenCx
            dy = bestBullseye.cy - screenCy
            return BullseyeResult(
                True, bestBullseye.area, [dx, dy], axisRatios, circularities
            )

        return BullseyeResult(False, 0, [], axisRatios, circularities)
