# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread-safe per-camera performance counters used by the runtime and benchmark."""

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence


def percentile(sortedValues: Sequence[float], fraction: float) -> Optional[float]:
    """Return a linearly interpolated percentile from an already sorted sequence."""
    if not sortedValues:
        return None
    if len(sortedValues) == 1:
        return float(sortedValues[0])

    position = (len(sortedValues) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sortedValues) - 1)
    weight = position - lower
    return float(sortedValues[lower] * (1.0 - weight) + sortedValues[upper] * weight)


def latencyPercentiles(values: Iterable[float]) -> Dict[str, Optional[float]]:
    """Convert latency samples in seconds to P50/P95/P99 values in milliseconds."""
    ordered = sorted(values)
    return {
        "p50": None if (value := percentile(ordered, 0.50)) is None else value * 1000.0,
        "p95": None if (value := percentile(ordered, 0.95)) is None else value * 1000.0,
        "p99": None if (value := percentile(ordered, 0.99)) is None else value * 1000.0,
    }


class CameraPerformanceTracker:
    """Track processed FPS and latency for one camera without blocking the frame loop."""

    def __init__(self, historySize: int = 4096, windowSeconds: float = 10.0) -> None:
        self._historySize = historySize
        self._windowSeconds = windowSeconds
        self._lock = threading.Lock()
        self._createdAt = time.perf_counter()
        self._timestamps: Deque[float] = deque(maxlen=historySize)
        self._captureLatencies: Deque[float] = deque(maxlen=historySize)
        self._processLatencies: Deque[float] = deque(maxlen=historySize)
        self._endToEndLatencies: Deque[float] = deque(maxlen=historySize)
        self._processedFrames = 0
        self._lastFrameBytes = 0
        self._lastResultAt: Optional[float] = None

    def reset(self) -> None:
        with self._lock:
            self._createdAt = time.perf_counter()
            self._timestamps.clear()
            self._captureLatencies.clear()
            self._processLatencies.clear()
            self._endToEndLatencies.clear()
            self._processedFrames = 0
            self._lastFrameBytes = 0
            self._lastResultAt = None

    def record(
        self,
        captureLatency: float,
        processingLatency: float,
        totalLatency: float,
        frameBytes: int = 0,
    ) -> None:
        now = time.perf_counter()
        with self._lock:
            self._timestamps.append(now)
            self._captureLatencies.append(max(0.0, float(captureLatency)))
            self._processLatencies.append(max(0.0, float(processingLatency)))
            self._endToEndLatencies.append(max(0.0, float(totalLatency)))
            self._processedFrames += 1
            self._lastFrameBytes = max(0, int(frameBytes))
            self._lastResultAt = now

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.perf_counter() if now is None else now
        with self._lock:
            while self._timestamps and now - self._timestamps[0] > self._windowSeconds:
                self._timestamps.popleft()

            elapsed = max(now - self._createdAt, 1e-9)
            windowElapsed = min(elapsed, self._windowSeconds)
            processedFps = len(self._timestamps) / windowElapsed

            result: Dict[str, Any] = {
                "processed_frames": self._processedFrames,
                "window_frames": len(self._timestamps),
                "window_seconds": windowElapsed,
                "processed_fps": processedFps,
                "frame_bytes": self._lastFrameBytes,
                "capture_latency_ms": latencyPercentiles(self._captureLatencies),
                "process_latency_ms": latencyPercentiles(self._processLatencies),
                "capture_to_result_latency_ms": latencyPercentiles(
                    self._endToEndLatencies
                ),
                "last_result_age_seconds": (
                    None
                    if self._lastResultAt is None
                    else max(0.0, now - self._lastResultAt)
                ),
            }
            return result


def summarizeCameras(
    statsByCamera: Dict[int, Dict[str, Any]],
    baselineFps: Optional[float] = None,
    threshold: float = 0.83,
) -> Dict[str, Any]:
    """Aggregate per-camera stats and evaluate the multi-camera pass condition."""
    cameras: List[Dict[str, Any]] = []
    fpsValues: List[float] = []

    for cameraIndex in sorted(statsByCamera):
        stats = dict(statsByCamera[cameraIndex])
        fps = float(stats.get("processed_fps") or 0.0)
        fpsValues.append(fps)
        stats["camera_index"] = cameraIndex
        stats["processed_fps"] = fps
        stats["baseline_fps"] = baselineFps
        stats["baseline_ratio"] = (
            fps / baselineFps if baselineFps is not None and baselineFps > 0 else None
        )
        cameras.append(stats)

    minFps = min(fpsValues, default=0.0)
    targetFps = None if baselineFps is None else baselineFps * threshold
    if baselineFps is None:
        meetsTarget: Optional[bool] = None
    else:
        meetsTarget = minFps >= (targetFps or 0.0)

    return {
        "camera_count": len(cameras),
        "cameras": cameras,
        "aggregate_fps": sum(fpsValues),
        "min_camera_fps": minFps,
        "baseline_fps": baselineFps,
        "target_fps_per_camera": targetFps,
        "threshold": threshold,
        "meets_target": meetsTarget,
    }
