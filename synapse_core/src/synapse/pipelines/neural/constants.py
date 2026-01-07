# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Optional, Tuple

from synapse.core.pipeline import PipelineResult

OBJECT_DIMENSIONS = {
    "dog": {"width": 0.50, "height": 0.60, "depth": 0.80},
    "cat": {"width": 0.30, "height": 0.25, "depth": 0.40},
    "cone": {"width": 0.24, "height": 0.33, "depth": 0.24},
    "cube": {"width": 0.24, "height": 0.24, "depth": 0.24},
    "sports ball": {"width": 0.22, "height": 0.22, "depth": 0.22},
    "person": {"width": 0.45, "height": 1.70, "depth": 0.30},
    "default": {"width": 0.30, "height": 0.30, "depth": 0.30},
    "algae": {"width": 0.30, "height": 0.30, "depth": 0.30},
    "coral": {"width": 0.30, "height": 0.30, "depth": 0.30},
}
DEFAULT_CAMERA_POSITION = {
    "x": 0.0,
    "y": 0.0,
    "z": 1.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
}


# ---------- Result Dataclass ----------
@dataclass(frozen=True)
class CameraFrame:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class PositionEstimate:
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
    className: str
    x: float
    y: float
    confidence: float
    bbox: Tuple[float, float, float, float]
    position3D: Optional[PositionEstimate]


@dataclass
class NeuralResult(PipelineResult):
    detections: List[NeuralDetection]
