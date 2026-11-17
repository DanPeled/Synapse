# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from synapse.core.pipeline import PipelineResult

# Approximate dimensions (in meters) for the objects the bundled model knows
# about. Classes that are not listed here are still reported, but they do not
# get a 3D position estimate.
OBJECT_DIMENSIONS: Dict[str, Dict[str, float]] = {
    "dog": {"width": 0.50, "height": 0.60, "depth": 0.80},
    "cat": {"width": 0.30, "height": 0.25, "depth": 0.40},
    "cone": {"width": 0.24, "height": 0.33, "depth": 0.24},
    "cube": {"width": 0.24, "height": 0.24, "depth": 0.24},
    "sports ball": {"width": 0.22, "height": 0.22, "depth": 0.22},
    "person": {"width": 0.45, "height": 1.70, "depth": 0.30},
    "algae": {"width": 0.30, "height": 0.30, "depth": 0.30},
    "coral": {"width": 0.30, "height": 0.30, "depth": 0.30},
    "default": {"width": 0.30, "height": 0.30, "depth": 0.30},
}


@dataclass(frozen=True)
class CameraFrame:
    """Position of a detection in the camera's optical frame."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class PositionEstimate:
    """Estimated field-space position of a detection."""

    fieldX: float
    fieldY: float
    fieldZ: float
    distance: float
    qualityScore: float
    reprojectionError: float
    bboxArea: float
    cameraFrame: CameraFrame


@dataclass
class NeuralDetection:
    """A single object detected by the neural network."""

    className: str
    x: float
    y: float
    confidence: float
    bbox: Tuple[float, float, float, float]
    position3D: Optional[PositionEstimate] = None


@dataclass
class NeuralResult(PipelineResult):
    """Result published by the YOLO pipeline."""

    detections: List[NeuralDetection]
    model: str = ""
    error: str = ""
