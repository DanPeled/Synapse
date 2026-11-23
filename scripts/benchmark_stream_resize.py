#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Benchmark the interpolation options used for live stream frames.

This exercises :meth:`CameraHandler._resizeFrame` with the same destination
buffer reuse as the publication lane, so the numbers describe the real resizing
work done for each streamed frame. Run it with::

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
        frame = np.zeros((source[1], source[0], 3), dtype=np.uint8)
        label = f"{source[0]}x{source[1]}->{target[0]}x{target[1]}"
        results[label] = {
            "area": _measure(
                frame, target, cv2.INTER_AREA, args.batches, args.per_batch
            ),
            "linear": _measure(
                frame, target, cv2.INTER_LINEAR, args.batches, args.per_batch
            ),
        }
        results[label]["speedup"] = round(
            results[label]["area"]["min_us"] / results[label]["linear"]["min_us"], 1
        )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"{'resize':<20}{'AREA (us)':>12}{'LINEAR (us)':>14}{'speedup':>10}")
    for label, result in results.items():
        print(
            f"{label:<20}{result['area']['min_us']:>12.2f}"
            f"{result['linear']['min_us']:>14.2f}{result['speedup']:>9.1f}x"
        )


if __name__ == "__main__":
    main()
