# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from typing import Any

import numpy as np
import pytest
from synapse.core.settings_api import FileConstraint
from synapse.pipelines.neural.constants import NeuralDetection
from synapse.pipelines.neural.position_estimator import (
    PositionEstimator,
    PositionEstimatorConfig,
)
from synapse.pipelines.neural.yolo_pipeline import DEFAULT_MODEL_PATH, YOLOSettings


def _config(**overrides: Any) -> PositionEstimatorConfig:
    values: dict[str, Any] = {
        "cameraMatrix": np.array(
            [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
        ),
        "distCoeffs": np.zeros(5),
        "calibResolution": (640, 480),
        "minDistance": 0.1,
        "maxDistance": 50.0,
        "minBboxArea": 10.0,
        "maxReprojectionError": 50.0,
    }
    values.update(overrides)
    return PositionEstimatorConfig(**values)


def _detection(
    className: str = "coral",
    bbox: tuple[float, float, float, float] = (270.0, 190.0, 370.0, 290.0),
    confidence: float = 0.9,
) -> NeuralDetection:
    return NeuralDetection(
        className=className,
        x=(bbox[0] + bbox[2]) / 2.0,
        y=(bbox[1] + bbox[3]) / 2.0,
        confidence=confidence,
        bbox=bbox,
    )


def _pose(**overrides) -> dict[str, float]:
    values = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
    }
    values.update(overrides)
    return values


def test_estimate_returns_distance_and_field_position():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(_detection(), _pose())

    assert result is not None
    assert result.distance == pytest.approx(1.5, rel=0.1)
    assert result.fieldX == pytest.approx(result.distance, rel=0.1)
    assert result.fieldY == pytest.approx(0.0, abs=0.05)
    assert result.fieldZ == pytest.approx(0.0, abs=0.05)
    assert result.qualityScore > 0.0


def test_estimate_applies_camera_position():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(_detection(), _pose(x=1.0, y=2.0, z=3.0))

    assert result is not None
    assert result.fieldX == pytest.approx(1.0 + result.distance, rel=0.1)
    assert result.fieldY == pytest.approx(2.0, abs=0.05)
    assert result.fieldZ == pytest.approx(3.0, abs=0.05)


def test_estimate_applies_camera_yaw():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(_detection(), _pose(yaw=math.radians(90.0)))

    assert result is not None
    assert result.fieldX == pytest.approx(0.0, abs=0.05)
    assert result.fieldY == pytest.approx(result.distance, rel=0.1)


def test_estimate_applies_camera_pitch():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(_detection(), _pose(pitch=math.radians(90.0)))

    assert result is not None
    # Positive pitch tilts the camera down, matching the WPILib convention.
    assert result.fieldX == pytest.approx(0.0, abs=0.05)
    assert result.fieldZ == pytest.approx(-result.distance, rel=0.1)


def test_estimate_scales_calibration_to_frame_resolution():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(
        _detection(), _pose(), frameShape=(960, 1280, 3)
    )

    assert result is not None
    assert result.distance == pytest.approx(3.0, rel=0.1)


def test_estimate_rejects_unknown_class():
    estimator = PositionEstimator(_config())

    assert estimator.estimate3DPosition(_detection("not-a-real-class"), _pose()) is None


def test_estimate_rejects_small_bbox():
    estimator = PositionEstimator(_config(minBboxArea=20_000.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_estimate_rejects_out_of_range_distance():
    estimator = PositionEstimator(_config(maxDistance=1.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_estimate_rejects_high_reprojection_error():
    estimator = PositionEstimator(_config(maxReprojectionError=-1.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_yolo_settings_expose_model_file_setting():
    settings = YOLOSettings()
    setting = settings.getAPI().getSetting("model_file")

    assert setting is not None
    assert isinstance(setting.constraint, FileConstraint)
    assert setting.defaultValue == DEFAULT_MODEL_PATH
    assert setting.constraint.fileTypes == {".pt", ".onnx", ".engine"}
