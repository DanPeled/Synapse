# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Frame-path performance tests for the color detection pipeline."""

import cv2
import numpy as np
from synapse.pipelines.color_pipeline import (
    ColorDetection,
    ColorDetectSettings,
    ColorPipeline,
)


def _pipeline() -> ColorPipeline:
    return ColorPipeline(ColorDetectSettings())


def test_process_frame_returns_input_when_nothing_detected(monkeypatch):
    pipeline = _pipeline()
    # Red has full saturation, so it is outside the default S range and
    # produces an empty mask.
    img = np.zeros((48, 64, 3), dtype=np.uint8)
    img[..., 2] = 255
    pipeline._ensureScratch(img)
    assert pipeline._output is not None
    pipeline._output.fill(0)

    result = pipeline.processFrame(img, 0.0)

    assert result is img
    # The reusable output buffer must stay untouched when no annotation is
    # needed; copying a full frame is the expensive part we are avoiding.
    assert not np.any(pipeline._output)


def test_process_frame_reuses_output_buffer_for_detections(monkeypatch):
    pipeline = _pipeline()
    img = np.zeros((48, 64, 3), dtype=np.uint8)
    pipeline._ensureScratch(img)
    detections = [
        ColorDetection(bbox=[2.0, 3.0, 10.0, 8.0], center=[7.0, 7.0], area=80.0)
    ]

    monkeypatch.setattr(
        "synapse.pipelines.color_pipeline.cv2.cvtColor",
        lambda source, code, dst=None: dst,
    )
    monkeypatch.setattr(pipeline, "_createMask", lambda hsv: hsv)
    monkeypatch.setattr(pipeline, "_findDetections", lambda mask: detections)
    monkeypatch.setattr(
        pipeline, "_selectMainDetection", lambda found, shape: found[0]
    )
    rectangles = []
    monkeypatch.setattr(
        "synapse.pipelines.color_pipeline.cv2.rectangle",
        lambda *args, **kwargs: rectangles.append(args),
    )

    first = pipeline.processFrame(img, 0.0)
    second = pipeline.processFrame(img, 0.0)

    assert first is pipeline._output
    assert second is first
    assert first is not img
    assert len(rectangles) == 2


def test_process_frame_draws_only_main_detection_when_not_publishing_all(
    monkeypatch,
):
    pipeline = _pipeline()
    pipeline.setSetting(pipeline.settings.publish_all_detections, False)
    img = np.zeros((48, 64, 3), dtype=np.uint8)
    pipeline._ensureScratch(img)
    detections = [
        ColorDetection(bbox=[0.0, 0.0, 4.0, 4.0], center=[2.0, 2.0], area=16.0),
        ColorDetection(bbox=[20.0, 20.0, 6.0, 6.0], center=[23.0, 23.0], area=36.0),
    ]

    monkeypatch.setattr(
        "synapse.pipelines.color_pipeline.cv2.cvtColor",
        lambda source, code, dst=None: dst,
    )
    monkeypatch.setattr(pipeline, "_createMask", lambda hsv: hsv)
    monkeypatch.setattr(pipeline, "_findDetections", lambda mask: detections)
    monkeypatch.setattr(
        pipeline, "_selectMainDetection", lambda found, shape: found[1]
    )
    rectangles = []
    monkeypatch.setattr(
        "synapse.pipelines.color_pipeline.cv2.rectangle",
        lambda *args, **kwargs: rectangles.append(args),
    )

    pipeline.processFrame(img, 0.0)

    assert len(rectangles) == 1
    assert rectangles[0][1] == (20, 20)


def test_threshold_arrays_are_reused_until_settings_change():
    pipeline = _pipeline()
    img = np.zeros((16, 16, 3), dtype=np.uint8)

    pipeline.processFrame(img, 0.0)
    firstLower = pipeline._lower
    firstUpper = pipeline._upper

    pipeline.processFrame(img, 0.0)
    assert pipeline._lower is firstLower
    assert pipeline._upper is firstUpper

    pipeline.setSetting(pipeline.settings.s, [0, 255])
    pipeline.processFrame(img, 0.0)
    assert pipeline._lower is not firstLower
    assert pipeline._upper is not firstUpper


def test_kernel_is_reused_for_the_same_size():
    pipeline = _pipeline()
    pipeline._ensureScratch(np.zeros((16, 16, 3), dtype=np.uint8))
    hsv = pipeline._hsv
    assert hsv is not None

    first = pipeline._createMask(hsv)
    kernel = pipeline._kernels[5]
    second = pipeline._createMask(hsv)

    assert first is pipeline._mask
    assert second is pipeline._mask
    assert pipeline._kernels[5] is kernel
    assert cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)).shape == kernel.shape
