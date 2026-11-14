# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generated from schema/synapse_lib.json. Do not edit by hand.
# Run `python tools/generate_synapse_lib.py` to regenerate.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


def _hashable(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((_hashable(k), _hashable(v)) for k, v in value.items()))
    return value


@dataclass(frozen=True)
class ColorDetection:
    """Represents a detected color region."""

    bbox: List[float]
    """The bounding box as [x, y, width, height]."""

    center: List[float]
    """The center of the region as [x, y]."""

    area: float
    """The area of the region in pixels squared."""

    def __hash__(self) -> int:
        return hash((_hashable(self.bbox), _hashable(self.center), self.area))


@dataclass(frozen=True)
class ColorResult:
    """Represents the result of a color detection pipeline run."""

    timestamp: float
    """The timestamp in seconds when the frame was processed."""

    detections: List[ColorDetection]
    """All detected color regions."""

    main_detection: Optional[ColorDetection]
    """The primary detection, or null when no regions were detected."""

    def __hash__(self) -> int:
        return hash((self.timestamp, _hashable(self.detections), self.main_detection))
