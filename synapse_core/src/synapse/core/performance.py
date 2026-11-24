# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread-safe per-camera performance counters used by the runtime and benchmark."""

import math
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Final, Iterable, List, Optional, Sequence


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


class FrameRateMeter:
    """Estimate a frame rate from timestamps taken on one monotonic clock.

    An instantaneous ``1 / (t_n - t_{n-1})`` reading is unbounded: two frames
    delivered back-to-back after a stall, reconnect or mode switch can report
    several times the camera's real rate. Count the *intervals* inside a
    sliding window instead, and withhold a value until the window has actually
    covered enough time. Using ``samples - 1`` intervals also avoids the
    phantom extra frame that ``samples / window`` produces whenever a window
    boundary falls between two samples.
    """

    WINDOW_SECONDS: Final[float] = 1.0
    MIN_SAMPLES: Final[int] = 2
    MIN_ELAPSED_RATIO: Final[float] = 0.5

    def __init__(
        self,
        windowSeconds: float = WINDOW_SECONDS,
        minSamples: int = MIN_SAMPLES,
        minElapsedRatio: float = MIN_ELAPSED_RATIO,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._windowSeconds = max(0.01, float(windowSeconds))
        self._minSamples = max(2, int(minSamples))
        self._minElapsed = self._windowSeconds * min(
            1.0, max(0.0, float(minElapsedRatio))
        )
        self._clock = clock
        self._timestamps: Deque[float] = deque()
        self._lastRate = 0.0

    def record(
        self, now: Optional[float] = None, limit: Optional[float] = None
    ) -> float:
        """Add one frame sample and return the current rate estimate."""
        sampleTime = self._clock() if now is None else float(now)
        self._timestamps.append(sampleTime)
        return self.rate(now=sampleTime, limit=limit)

    def rate(self, now: Optional[float] = None, limit: Optional[float] = None) -> float:
        """Return the rate over the trailing window without adding a sample.

        ``limit`` is an optional physical upper bound (the camera's active
        video mode). A camera cannot produce more frames than its mode allows,
        so clipping an impossible reading is correcting the math, not hiding
        a slow pipeline: genuine slowdowns still lower the reported rate.
        """
        sampleTime = self._clock() if now is None else float(now)
        cutoff = sampleTime - self._windowSeconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

        if len(self._timestamps) < self._minSamples:
            # An empty window means the camera stopped producing frames; do
            # not keep reporting the last rate from a previous connection.
            if not self._timestamps:
                self._lastRate = 0.0
            return self._lastRate
        span = self._timestamps[-1] - self._timestamps[0]
        if span < self._minElapsed:
            return self._lastRate

        fps = (len(self._timestamps) - 1) / span
        if limit is not None and math.isfinite(limit) and limit > 0:
            fps = min(fps, float(limit))
        self._lastRate = max(0.0, fps)
        return self._lastRate

    def reset(self) -> None:
        """Discard the measurement window (e.g. before a benchmark run)."""
        self._timestamps.clear()
        self._lastRate = 0.0


class CameraPerformanceTracker:
    """Track processed FPS and latency for one camera without blocking the frame loop."""

    def __init__(
        self,
        historySize: int = 4096,
        windowSeconds: float = 10.0,
        batchSize: int = 64,
        flushInterval: float = 0.1,
    ) -> None:
        self._historySize = historySize
        self._windowSeconds = windowSeconds
        self._batchSize = max(1, int(batchSize))
        self._flushInterval = max(0.0, float(flushInterval))

        # Committed state is read by snapshots. Pending state is written by the
        # single camera worker and flushed in batches, so percentile sorting no
        # longer competes with per-frame recording for the committed lock.
        self._lock = threading.Lock()
        self._pendingLock = threading.Lock()
        self._createdAt = time.perf_counter()
        self._lastFlush = self._createdAt
        self._timestamps: Deque[float] = deque(maxlen=historySize)
        self._captureLatencies: Deque[float] = deque(maxlen=historySize)
        self._processLatencies: Deque[float] = deque(maxlen=historySize)
        self._endToEndLatencies: Deque[float] = deque(maxlen=historySize)
        self._processedFrames = 0
        self._lastFrameBytes = 0
        self._lastResultAt: Optional[float] = None

        self._pendingTimestamps: List[float] = []
        self._pendingCaptureLatencies: List[float] = []
        self._pendingProcessLatencies: List[float] = []
        self._pendingEndToEndLatencies: List[float] = []
        self._pendingFrames = 0
        self._pendingFrameBytes = 0
        self._pendingLastResultAt: Optional[float] = None

        # FPS comes from a monotonic window with a minimum elapsed interval so
        # a burst of frames right after reset() cannot report an impossible rate.
        self._rateMeter = FrameRateMeter(
            windowSeconds=windowSeconds,
            # Benchmarks use a 10 s window but can be much shorter; one tenth
            # of the window is enough to reject a burst without delaying a
            # short run by half the window.
            minElapsedRatio=0.1,
            clock=time.perf_counter,
        )

    def _commitPendingLocked(self, now: float) -> None:
        """Move pending samples into committed state; ``_pendingLock`` is held."""
        if not self._pendingTimestamps:
            return

        with self._lock:
            self._timestamps.extend(self._pendingTimestamps)
            self._captureLatencies.extend(self._pendingCaptureLatencies)
            self._processLatencies.extend(self._pendingProcessLatencies)
            self._endToEndLatencies.extend(self._pendingEndToEndLatencies)
            self._processedFrames += self._pendingFrames
            self._lastFrameBytes = self._pendingFrameBytes
            if self._pendingLastResultAt is not None:
                self._lastResultAt = self._pendingLastResultAt

        self._pendingTimestamps.clear()
        self._pendingCaptureLatencies.clear()
        self._pendingProcessLatencies.clear()
        self._pendingEndToEndLatencies.clear()
        self._pendingFrames = 0
        self._pendingFrameBytes = 0
        self._pendingLastResultAt = None
        self._lastFlush = now

    def flush(self) -> None:
        """Publish pending samples immediately, e.g. before reading a benchmark."""
        with self._pendingLock:
            self._commitPendingLocked(time.perf_counter())

    def reset(self) -> None:
        now = time.perf_counter()
        with self._pendingLock:
            with self._lock:
                self._createdAt = now
                self._lastFlush = now
                self._timestamps.clear()
                self._captureLatencies.clear()
                self._processLatencies.clear()
                self._endToEndLatencies.clear()
                self._processedFrames = 0
                self._lastFrameBytes = 0
                self._lastResultAt = None

                self._pendingTimestamps.clear()
                self._pendingCaptureLatencies.clear()
                self._pendingProcessLatencies.clear()
                self._pendingEndToEndLatencies.clear()
                self._pendingFrames = 0
                self._pendingFrameBytes = 0
                self._pendingLastResultAt = None
            self._rateMeter.reset()

    def record(
        self,
        captureLatency: float,
        processingLatency: float,
        totalLatency: float,
        frameBytes: int = 0,
    ) -> None:
        now = time.perf_counter()
        with self._pendingLock:
            self._pendingTimestamps.append(now)
            self._pendingCaptureLatencies.append(max(0.0, float(captureLatency)))
            self._pendingProcessLatencies.append(max(0.0, float(processingLatency)))
            self._pendingEndToEndLatencies.append(max(0.0, float(totalLatency)))
            self._pendingFrames += 1
            self._pendingFrameBytes = max(0, int(frameBytes))
            self._pendingLastResultAt = now

            if (
                len(self._pendingTimestamps) >= self._batchSize
                or now - self._lastFlush >= self._flushInterval
            ):
                self._commitPendingLocked(now)

            self._rateMeter.record(now)

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.perf_counter() if now is None else now
        with self._pendingLock:
            self._commitPendingLocked(now)
            with self._lock:
                while (
                    self._timestamps and now - self._timestamps[0] > self._windowSeconds
                ):
                    self._timestamps.popleft()

                elapsed = max(now - self._createdAt, 0.0)
                windowElapsed = min(elapsed, self._windowSeconds)
                processedFps = self._rateMeter.rate(now)

                processedFrames = self._processedFrames
                windowFrames = len(self._timestamps)
                frameBytes = self._lastFrameBytes
                lastResultAt = self._lastResultAt
                captureSamples = tuple(self._captureLatencies)
                processSamples = tuple(self._processLatencies)
                endToEndSamples = tuple(self._endToEndLatencies)

        # Percentile sorting happens outside both locks so a snapshot cannot
        # stall a camera worker that is recording the next frame.
        return {
            "processed_frames": processedFrames,
            "window_frames": windowFrames,
            "window_seconds": windowElapsed,
            "processed_fps": processedFps,
            "frame_bytes": frameBytes,
            "capture_latency_ms": latencyPercentiles(captureSamples),
            "process_latency_ms": latencyPercentiles(processSamples),
            "capture_to_result_latency_ms": latencyPercentiles(endToEndSamples),
            "last_result_age_seconds": (
                None if lastResultAt is None else max(0.0, now - lastResultAt)
            ),
        }


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
    maxFps = max(fpsValues, default=0.0)
    aggregateFps = sum(fpsValues)
    meanFps = aggregateFps / len(fpsValues) if fpsValues else 0.0
    targetFps = None if baselineFps is None else baselineFps * threshold
    ratios = [
        float(stats["baseline_ratio"])
        for stats in cameras
        if stats["baseline_ratio"] is not None
    ]
    meanRatio = sum(ratios) / len(ratios) if ratios else None
    if baselineFps is None:
        meetsTarget: Optional[bool] = None
    else:
        meetsTarget = minFps >= (targetFps or 0.0)

    slowestIndex = None
    fastestIndex = None
    if cameras:
        slowest = min(cameras, key=lambda camera: camera["processed_fps"])
        fastest = max(cameras, key=lambda camera: camera["processed_fps"])
        slowestIndex = slowest["camera_index"]
        fastestIndex = fastest["camera_index"]

    return {
        "camera_count": len(cameras),
        "cameras": cameras,
        "aggregate_fps": aggregateFps,
        "mean_camera_fps": meanFps,
        "min_camera_fps": minFps,
        "max_camera_fps": maxFps,
        "fps_spread": maxFps - minFps,
        "slowest_camera_index": slowestIndex,
        "fastest_camera_index": fastestIndex,
        "baseline_fps": baselineFps,
        "target_fps_per_camera": targetFps,
        "target_fps_aggregate": (
            None if targetFps is None else targetFps * len(cameras)
        ),
        "threshold": threshold,
        "mean_baseline_ratio": meanRatio,
        "aggregate_efficiency": meanRatio,
        "meets_target": meetsTarget,
    }
