# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ColorDetection:
    """
    Represents a detected color region.

    Attributes:
        bbox: Bounding box as (x, y, width, height).
        center: Center of the region as (x, y).
        area: Area of the detected region in pixels squared.
    """

    bbox: List[float]
    center: List[float]
    area: float


@dataclass(frozen=True)
class ColorResult:
    """
    Represents the result of a color detection pipeline run.

    Attributes:
        timestamp: Timestamp (in seconds) when the frame was processed.
        detections: All detected color regions in the frame.
        main_detection: The primary or best detection, if one exists.
    """

    timestamp: float
    detections: List[ColorDetection]
    main_detection: Optional[ColorDetection]
