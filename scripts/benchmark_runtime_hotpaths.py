#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Micro-benchmarks for the runtime camera and pipeline hot paths.

The script exercises the same code paths on every revision, so it can be run
against a baseline checkout and against the optimized checkout and compared::

    python scripts/benchmark_runtime_hotpaths.py --json > after.json

Results publishing and camera I/O are excluded; these are CPU-only measurements
of the work done for each processed frame.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any, Callable, Dict, List

import numpy as np
from synapse.core.camera_handler import _PublishLane
from synapse.core.pipeline import Pipeline, PipelineResult, PipelineSettings
from synapse.core.settings_api import CameraSettings
from synapse.pipelines.apriltag.apriltag_detector import AprilTagDetection, makeCorners
from synapse.pipelines.apriltag.apriltag_pipeline import filterTagsByIds
from synapse.pipelines.color_pipeline import ColorDetectSettings, ColorPipeline
from synapse.pipelines.neural.constants import NeuralDetection
from synapse.pipelines.neural.yolo_pipeline import YOLOPipeline, YOLOSettings


class _ResolutionPipeline(Pipeline[PipelineSettings, PipelineResult]):
    def __init__(self) -> None:
        super().__init__(PipelineSettings())
        self.cameraIndex = 0
        self.pipelineIndex = 0

    def processFrame(self, img, timestamp: float):
        return None


def _measure(
    operation: Callable[[], Any], batches: int, perBatch: int
) -> Dict[str, Any]:
    operation()  # warm up imports, lazy caches, and allocator state
    samples: List[float] = []
    for _ in range(batches):
        start = time.perf_counter()
        for _ in range(perBatch):
            operation()
        elapsed = time.perf_counter() - start
        samples.append(elapsed / perBatch * 1_000_000.0)
    return {
        "median_us": round(statistics.median(samples), 2),
        "min_us": round(min(samples), 2),
        "samples_us": [round(sample, 2) for sample in samples],
    }


def _settingsLookup(settings: ColorDetectSettings) -> None:
    # Seven reads: the same set a color pipeline performs on a typical frame.
    settings.getSetting(settings.h)
    settings.getSetting(settings.s)
    settings.getSetting(settings.v)
    settings.getSetting(settings.morph_kernel)
    settings.getSetting(settings.min_area)
    settings.getSetting(settings.result_strategy)
    settings.getSetting(settings.publish_all_detections)


def _makeDetection(tagID: int) -> AprilTagDetection:
    return AprilTagDetection(
        tagID=tagID,
        homography=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        hamming=0,
        corners=makeCorners(0, 0, 1, 0, 1, 1, 0, 1),
        center=(0, 0),
    )


def _benchmarks() -> Dict[str, Callable[[], Any]]:
    colorSettings = ColorDetectSettings()
    color = ColorPipeline(colorSettings)
    # Publishing goes through NetworkTables/WebSocket singletons; exclude it so
    # the numbers describe frame processing only.
    color.setDataValue = lambda *args, **kwargs: None  # type: ignore[method-assign]
    colorFrame = np.zeros((480, 640, 3), dtype=np.uint8)
    colorFrame[100:300, 100:300] = (100, 150, 100)
    # A frame with no detectable target still costs a full-frame copy in the
    # baseline; the optimized path returns the capture buffer unchanged.
    emptyFrame = np.zeros_like(colorFrame)
    color._ensureScratch(colorFrame)
    hsv = color._hsv
    assert hsv is not None

    yolo = YOLOPipeline(YOLOSettings())
    yoloFrame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = [
        NeuralDetection(
            className="object",
            x=100.0,
            y=100.0,
            confidence=0.9,
            bbox=(100.0, 100.0, 200.0, 200.0),
        )
        for _ in range(4)
    ]

    tags = [_makeDetection(index % 16) for index in range(64)]
    tagIds = frozenset(range(16))

    resolution = _ResolutionPipeline()
    resolution.setCameraSetting(CameraSettings.resolution, "640x480")

    lane = _PublishLane(0, lambda *args, **kwargs: None)
    laneFrame = np.zeros((480, 640, 3), dtype=np.uint8)
    lane.enqueue(laneFrame, 30)

    return {
        "settings_lookup": lambda: _settingsLookup(colorSettings),
        "color_create_mask": lambda: color._createMask(hsv),
        "color_process_frame": lambda: color.processFrame(colorFrame, 0.0),
        "color_no_detections": lambda: color.processFrame(emptyFrame, 0.0),
        "yolo_draw_detections": lambda: yolo.draw_detections(yoloFrame, detections),
        "apriltag_filter": lambda: filterTagsByIds(tags, tagIds),
        "pipeline_get_resolution": lambda: resolution.getResolution(),
        "publish_lane_enqueue": lambda: lane.enqueue(laneFrame, 30),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=7)
    parser.add_argument("--per-batch", type=int, default=200)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    results = {
        name: _measure(operation, args.batches, args.per_batch)
        for name, operation in _benchmarks().items()
    }

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"{'case':<28}{'median (us)':>14}{'min (us)':>12}")
    for name, result in results.items():
        print(f"{name:<28}{result['median_us']:>14}{result['min_us']:>12}")


if __name__ == "__main__":
    main()
