# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import List, Optional, Tuple

from synapse.core.pipeline import PipelineResult

#: Object width/height pair in meters.
ObjectSize = Tuple[float, float]

#: Assumed size for classes without an explicit entry. This keeps position
#: estimation usable for any model while allowing per-class sizes to be
#: supplied through the pipeline settings.
DEFAULT_OBJECT_WIDTH = 0.3
DEFAULT_OBJECT_HEIGHT = 0.3


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
    objectWidth: float
    objectHeight: float


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
    """Result published by the neural pipeline."""

    detections: List[NeuralDetection]
    model: str = ""
    error: str = ""
