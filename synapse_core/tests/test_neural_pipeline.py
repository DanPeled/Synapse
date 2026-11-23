# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from synapse.core.settings_api import FileConstraint
from synapse.pipelines.neural.constants import (
    DEFAULT_OBJECT_HEIGHT,
    DEFAULT_OBJECT_WIDTH,
    NeuralDetection,
)
from synapse.pipelines.neural.position_estimator import (
    PositionEstimator,
    PositionEstimatorConfig,
    parseObjectDimensions,
)
from synapse.pipelines.neural.yolo_pipeline import (
    DEFAULT_MODEL_PATH,
    YOLOPipeline,
    YOLOSettings,
)


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
        "objectDimensions": {},
        "defaultObjectWidth": DEFAULT_OBJECT_WIDTH,
        "defaultObjectHeight": DEFAULT_OBJECT_HEIGHT,
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


def test_estimate_uses_default_size_for_unknown_class():
    estimator = PositionEstimator(_config())

    result = estimator.estimate3DPosition(_detection("not-a-real-class"), _pose())

    assert result is not None
    assert result.objectWidth == pytest.approx(DEFAULT_OBJECT_WIDTH)
    assert result.objectHeight == pytest.approx(DEFAULT_OBJECT_HEIGHT)


def test_estimate_uses_class_specific_dimensions():
    estimator = PositionEstimator(_config(objectDimensions={"person": (0.45, 1.70)}))

    result = estimator.estimate3DPosition(_detection("person"), _pose())

    assert result is not None
    assert result.objectWidth == pytest.approx(0.45)
    assert result.objectHeight == pytest.approx(1.70)


def test_estimate_uses_configured_default_dimensions():
    estimator = PositionEstimator(
        _config(defaultObjectWidth=0.5, defaultObjectHeight=0.25)
    )

    result = estimator.estimate3DPosition(_detection("unknown"), _pose())

    assert result is not None
    assert result.objectWidth == pytest.approx(0.5)
    assert result.objectHeight == pytest.approx(0.25)


def test_estimate_rejects_small_bbox():
    estimator = PositionEstimator(_config(minBboxArea=20_000.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_estimate_rejects_out_of_range_distance():
    estimator = PositionEstimator(_config(maxDistance=1.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_estimate_rejects_high_reprojection_error():
    estimator = PositionEstimator(_config(maxReprojectionError=-1.0))

    assert estimator.estimate3DPosition(_detection(), _pose()) is None


def test_parse_object_dimensions_accepts_dict_and_list_entries():
    parsed = parseObjectDimensions(
        {
            "person": {"width": 0.45, "height": 1.70},
            "sports ball": [0.22, 0.22],
        }
    )

    assert parsed == {"person": (0.45, 1.70), "sports ball": (0.22, 0.22)}


def test_parse_object_dimensions_skips_invalid_entries():
    parsed = parseObjectDimensions(
        {
            "ok": [0.3, 0.3],
            "missing": {"width": 0.3},
            "negative": [-1.0, 0.3],
            "text": "not a size",
            "nan": [float("nan"), 0.3],
        }
    )

    assert parsed == {"ok": (0.3, 0.3)}


def test_parse_object_dimensions_rejects_non_object():
    with pytest.raises(ValueError):
        parseObjectDimensions([1, 2, 3])


def test_yolo_settings_expose_model_file_setting():
    settings = YOLOSettings()
    setting = settings.getAPI().getSetting("model_file")

    assert setting is not None
    assert isinstance(setting.constraint, FileConstraint)
    assert setting.defaultValue == DEFAULT_MODEL_PATH
    assert setting.constraint.fileTypes == {".pt", ".onnx", ".engine"}


def test_yolo_settings_expose_generic_object_size_settings():
    settings = YOLOSettings()
    api = settings.getAPI()

    dimensions = api.getSetting("object_dimensions_file")
    width = api.getSetting("default_object_width")
    height = api.getSetting("default_object_height")

    assert dimensions is not None
    assert isinstance(dimensions.constraint, FileConstraint)
    assert dimensions.defaultValue == ""
    assert dimensions.constraint.fileTypes == {".json"}
    assert width is not None
    assert width.defaultValue == DEFAULT_OBJECT_WIDTH
    assert height is not None
    assert height.defaultValue == DEFAULT_OBJECT_HEIGHT


def test_pipeline_loads_object_dimensions_file(tmp_path, monkeypatch):
    (tmp_path / "dimensions.json").write_text(
        json.dumps({"person": {"width": 0.45, "height": 1.70}})
    )
    monkeypatch.setattr("synapse.core.settings_api._getSettingsRoot", lambda: tmp_path)
    monkeypatch.setattr(
        "synapse.pipelines.neural.yolo_pipeline._projectRoot", lambda: tmp_path
    )

    settings = YOLOSettings()
    result = settings.getAPI().setValue("object_dimensions_file", "dimensions.json")
    assert result.isValid

    pipeline = YOLOPipeline(settings)

    assert pipeline._objectDimensions == {"person": (0.45, 1.70)}


def test_create_model_prefers_yolo_loader():
    class FakeYOLO:
        def __init__(self, path: str):
            self.path = path

    class FakeRTDETR:
        def __init__(self, path: str):
            raise AssertionError("RTDETR should not be used")

    module = SimpleNamespace(YOLO=FakeYOLO, RTDETR=FakeRTDETR)

    model = YOLOPipeline._createModel(module, Path("model.pt"))

    assert isinstance(model, FakeYOLO)
    assert model.path == "model.pt"


def test_create_model_falls_back_to_rtdetr_loader():
    class FakeYOLO:
        def __init__(self, path: str):
            raise RuntimeError("unsupported model")

    class FakeRTDETR:
        def __init__(self, path: str):
            self.path = path

    module = SimpleNamespace(YOLO=FakeYOLO, RTDETR=FakeRTDETR)

    model = YOLOPipeline._createModel(module, Path("model.pt"))

    assert isinstance(model, FakeRTDETR)
    assert model.path == "model.pt"


def test_camera_pose_is_cached_until_a_pose_setting_changes():
    pipeline = YOLOPipeline(YOLOSettings())

    first = pipeline._cameraPose()
    assert pipeline._cameraPose() is first

    pipeline.setSetting(pipeline.settings.camera_x, 2.0)
    second = pipeline._cameraPose()

    assert second is not first
    assert second["x"] == 2.0


def test_draw_detections_reuses_the_display_buffer():
    pipeline = YOLOPipeline(YOLOSettings())
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    detections = [_detection(bbox=(10.0, 10.0, 50.0, 50.0))]

    first = pipeline.draw_detections(frame, detections)
    assert first is pipeline._displayBuffer
    assert first is not frame

    second = pipeline.draw_detections(frame, detections)
    assert second is first

    resized = pipeline.draw_detections(
        np.zeros((60, 80, 3), dtype=np.uint8), detections
    )
    assert resized is pipeline._displayBuffer
    assert resized is not first
