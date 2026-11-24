# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import patch

import pytest
from synapse.core.performance import (
    CameraPerformanceTracker,
    FrameRateMeter,
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
    clock = {"now": 100.0}
    with patch("synapse.core.performance.time.perf_counter", lambda: clock["now"]):
        tracker = CameraPerformanceTracker(historySize=16, windowSeconds=0.25)
        for index in range(8):
            clock["now"] += 1.0 / 30.0
            tracker.record(
                captureLatency=0.01,
                processingLatency=0.02 + index * 0.001,
                totalLatency=0.03 + index * 0.001,
                frameBytes=1024,
            )

        stats = tracker.snapshot()

        assert stats["processed_frames"] == 8
        assert stats["window_frames"] == 8
        assert stats["processed_fps"] == pytest.approx(30.0, abs=1.0)
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


def test_frame_rate_meter_rejects_short_bursts_and_respects_camera_limit() -> None:
    """A pair of frames arriving 5 ms apart is not a 200 FPS camera."""
    clock = {"now": 1000.0}
    meter = FrameRateMeter(clock=lambda: clock["now"])

    assert meter.record(limit=30.0) == 0.0
    clock["now"] += 0.005
    assert meter.record(limit=30.0) == 0.0

    # A steady 30 FPS stream produces a meaningful rate once the window fills.
    for _ in range(30):
        clock["now"] += 1.0 / 30.0
        fps = meter.record(limit=30.0)
    assert fps == pytest.approx(30.0, abs=1.0)

    # A long idle followed by a short burst must not spike above the limit.
    clock["now"] += 2.0
    meter.record(limit=30.0)
    clock["now"] += 0.005
    assert meter.record(limit=30.0) <= 30.0

    # Once the window contains no frames the rate falls back to zero instead
    # of holding the last value from a disconnected camera.
    clock["now"] += 2.0
    assert meter.rate(limit=30.0) == 0.0

    # Without a known limit the window still prevents an impossible spike.
    meter.reset()
    assert meter.record() == 0.0
    clock["now"] += 0.005
    assert meter.record() == 0.0


def test_tracker_does_not_report_burst_after_long_idle_as_high_fps() -> None:
    """The benchmark tracker must not divide two burst frames by ~0 seconds."""
    clock = {"now": 500.0}
    with patch("synapse.core.performance.time.perf_counter", lambda: clock["now"]):
        tracker = CameraPerformanceTracker(windowSeconds=1.0, batchSize=1)
        tracker.record(0.01, 0.01, 0.02)
        clock["now"] += 0.005
        tracker.record(0.01, 0.01, 0.02)

        assert tracker.snapshot()["processed_fps"] == 0.0

        for _ in range(60):
            clock["now"] += 1.0 / 60.0
            tracker.record(0.01, 0.01, 0.02)
        assert tracker.snapshot()["processed_fps"] == pytest.approx(60.0, abs=2.0)

        # reset() must not retain a sample window from before the reset.
        tracker.reset()
        tracker.record(0.01, 0.01, 0.02)
        clock["now"] += 0.005
        tracker.record(0.01, 0.01, 0.02)
        assert tracker.snapshot()["processed_fps"] == 0.0
