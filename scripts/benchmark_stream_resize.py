#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Benchmark the interpolation options used for live stream frames.

This exercises :meth:`CameraHandler._resizeFrame` with the same destination
buffer reuse as the publication lane, so the numbers describe the real resizing
work done for each streamed frame. A deterministic synthetic frame is also
compared against INTER_AREA to quantify the quality tradeoff. Run it with::

    python scripts/benchmark_stream_resize.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from synapse.core.camera_handler import CameraHandler


class _ResizeHarness:
    """Call the real resize helper without constructing a camera handler."""

    _resizeFrame = CameraHandler._resizeFrame


def _measure(
    frame: np.ndarray,
    size: Tuple[int, int],
    interpolation: int,
    batches: int,
    perBatch: int,
) -> Dict[str, Any]:
    harness = _ResizeHarness()
    buffers: Dict[int, np.ndarray] = {}

    def operation() -> None:
        harness._resizeFrame(  # type: ignore[attr-defined]
            frame, size, buffers, 0, interpolation=interpolation
        )

    operation()
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
    }


def _sampleFrame(width: int, height: int) -> np.ndarray:
    """Build a deterministic, edge-heavy frame for the quality comparison."""
    rng = np.random.default_rng(7)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    for _ in range(80):
        x = int(rng.integers(0, width))
        y = int(rng.integers(0, height))
        w = int(rng.integers(width // 40, max(width // 40 + 1, width // 8)))
        h = int(rng.integers(height // 40, max(height // 40 + 1, height // 8)))
        color = tuple(int(value) for value in rng.integers(0, 256, 3))
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)
    return frame


def _quality(frame: np.ndarray, size: Tuple[int, int]) -> Tuple[float, float]:
    """Compare INTER_LINEAR against INTER_AREA, which is used as reference."""
    reference = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    linear = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
    difference = np.abs(reference.astype(np.int16) - linear.astype(np.int16))
    return round(cv2.PSNR(reference, linear), 2), round(float(difference.mean()), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=5)
    parser.add_argument("--per-batch", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    cases = (
        ((1920, 1080), (320, 240)),
        ((1280, 720), (320, 240)),
        ((640, 480), (320, 240)),
    )
    results: Dict[str, Any] = {}
    for source, target in cases:
        frame = _sampleFrame(*source)
        label = f"{source[0]}x{source[1]}->{target[0]}x{target[1]}"
        psnr, meanDifference = _quality(frame, target)
        results[label] = {
            "area": _measure(
                frame, target, cv2.INTER_AREA, args.batches, args.per_batch
            ),
            "linear": _measure(
                frame, target, cv2.INTER_LINEAR, args.batches, args.per_batch
            ),
            "psnr_db": psnr,
            "mean_abs_difference": meanDifference,
        }
        results[label]["speedup"] = round(
            results[label]["area"]["min_us"] / results[label]["linear"]["min_us"], 1
        )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(
        f"{'resize':<20}{'AREA (us)':>12}{'LINEAR (us)':>14}"
        f"{'speedup':>10}{'PSNR (dB)':>12}{'mean diff':>11}"
    )
    for label, result in results.items():
        print(
            f"{label:<20}{result['area']['min_us']:>12.2f}"
            f"{result['linear']['min_us']:>14.2f}{result['speedup']:>9.1f}x"
            f"{result['psnr_db']:>12.2f}{result['mean_abs_difference']:>11.2f}"
        )


if __name__ == "__main__":
    main()
