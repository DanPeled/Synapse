# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from synapse.core.performance import (
    CameraPerformanceTracker,
    latencyPercentiles,
    percentile,
    summarizeCameras,
)


def test_percentile_interpolates_between_samples() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([], 0.5) is None


def test_latency_percentiles_are_reported_in_milliseconds() -> None:
    stats = latencyPercentiles([0.01, 0.02, 0.03, 0.04])

    assert stats["p50"] == pytest.approx(25.0)
    assert stats["p95"] == pytest.approx(38.5)
    assert stats["p99"] == pytest.approx(39.7)


def test_tracker_records_fps_and_end_to_end_latency() -> None:
    tracker = CameraPerformanceTracker(historySize=8, windowSeconds=1.0)
    for index in range(8):
        tracker.record(
            captureLatency=0.01,
            processingLatency=0.02 + index * 0.001,
            totalLatency=0.03 + index * 0.001,
            frameBytes=1024,
        )

    stats = tracker.snapshot()

    assert stats["processed_frames"] == 8
    assert stats["window_frames"] == 8
    assert stats["processed_fps"] > 0
    assert stats["frame_bytes"] == 1024
    assert stats["capture_latency_ms"]["p50"] == pytest.approx(10.0)
    assert stats["capture_to_result_latency_ms"]["p99"] > 30.0

    tracker.reset()
    assert tracker.snapshot()["processed_frames"] == 0
    assert tracker.snapshot()["capture_to_result_latency_ms"]["p50"] is None


def test_tracker_flushes_pending_samples_on_snapshot() -> None:
    tracker = CameraPerformanceTracker(historySize=8, batchSize=100, flushInterval=60.0)
    tracker.record(0.01, 0.02, 0.03, frameBytes=128)

    assert len(tracker._pendingTimestamps) == 1
    assert len(tracker._timestamps) == 0

    stats = tracker.snapshot()

    assert stats["processed_frames"] == 1
    assert stats["capture_latency_ms"]["p50"] == pytest.approx(10.0)
    assert len(tracker._pendingTimestamps) == 0
    assert len(tracker._timestamps) == 1


def test_summarize_cameras_uses_worst_camera_for_pass_condition() -> None:
    stats = {
        0: {"processed_fps": 120.0},
        1: {"processed_fps": 100.0},
        2: {"processed_fps": 110.0},
        3: {"processed_fps": 105.0},
    }

    report = summarizeCameras(stats, baselineFps=120.0, threshold=0.83)

    assert report["aggregate_fps"] == pytest.approx(435.0)
    assert report["mean_camera_fps"] == pytest.approx(108.75)
    assert report["min_camera_fps"] == 100.0
    assert report["max_camera_fps"] == 120.0
    assert report["fps_spread"] == 20.0
    assert report["slowest_camera_index"] == 1
    assert report["fastest_camera_index"] == 0
    assert report["target_fps_per_camera"] == pytest.approx(99.6)
    assert report["target_fps_aggregate"] == pytest.approx(398.4)
    assert report["mean_baseline_ratio"] == pytest.approx(108.75 / 120.0)
    assert report["aggregate_efficiency"] == pytest.approx(108.75 / 120.0)
    assert report["meets_target"] is True

    failing = summarizeCameras(stats, baselineFps=130.0, threshold=0.83)
    assert failing["meets_target"] is False
    assert failing["cameras"][1]["baseline_ratio"] == pytest.approx(100 / 130)
