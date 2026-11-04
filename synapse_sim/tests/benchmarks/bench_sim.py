# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end throughput benchmark for the simulated camera.

This measures the path the actual simulator uses: ``SimCamera.grabFrame``
publishes a pose, the headless Chrome renderer draws the field, reads the
pixels back, sends them over a WebSocket, and Python decodes them into a BGR
frame.

Run one size per process because ``getViewer()`` is a process-wide singleton
and reusing it across resolutions leaks frames from the previous size. The
default invocation spawns one child process per resolution.

Examples
--------
From the repository root, with the development paths on ``PYTHONPATH``::

    PYTHONPATH=synapse_sim/src:synapse_core/src:synapse_net/src \\
        python synapse_sim/tests/benchmarks/bench_sim.py

    # One resolution, machine-readable output
    python synapse_sim/tests/benchmarks/bench_sim.py \\
        --size 1280x720 --seconds 10 --json

    # Fail if 640x480 drops below 60 FPS
    python synapse_sim/tests/benchmarks/bench_sim.py \\
        --size 640x480 --min-fps 60

Run it from an installed environment with ``python -m
synapse_sim.tests.benchmarks.bench_sim`` only if the tests directory is on
``PYTHONPATH``; the file path form works everywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_SIZES = ("640x480", "1280x720", "1920x1080")
DEFAULT_SECONDS = 5.0
DEFAULT_WARMUP = 1.0


def parseSize(text: str) -> Tuple[int, int]:
    """Parses a ``WIDTHxHEIGHT`` resolution."""
    try:
        widthText, heightText = text.lower().split("x", 1)
        width, height = int(widthText), int(heightText)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid resolution {text!r}; expected WIDTHxHEIGHT"
        ) from error
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(
            f"invalid resolution {text!r}; dimensions must be positive"
        )
    return width, height


def percentile(sortedValues: Sequence[float], fraction: float) -> float:
    """Returns a percentile from an already-sorted sequence."""
    if not sortedValues:
        return 0.0
    index = min(
        len(sortedValues) - 1, max(0, round(fraction * (len(sortedValues) - 1)))
    )
    return sortedValues[index]


def measure(
    width: int,
    height: int,
    seconds: float,
    warmup: float,
    targetFps: float,
    collectStats: bool,
) -> Dict[str, Any]:
    """Runs the simulated camera as fast as it can for ``seconds``."""
    import numpy as np
    from cscore import VideoMode
    from synapse_sim.camera import SimCamera
    from synapse_sim.viewer import STARTUP_TIMEOUT
    from wpimath.geometry import Pose3d, Rotation3d, Translation3d

    if collectStats:
        # The renderer only sends its per-second diagnostics when this is set.
        os.environ["SYNAPSE_SIM_DEBUG"] = "1"

    camera = SimCamera.create(path=0, index=0)
    camera.setVideoMode(
        VideoMode(VideoMode.PixelFormat.kMJPEG, width, height, int(targetFps))
    )
    viewer = camera._viewer

    # A fixed pose keeps the workload stable across runs. It matches the
    # default robot position looking across the field.
    pose = Pose3d(Translation3d(8.0, 4.0, 0.5), Rotation3d(0.0, 0.3, 0.0))
    camera.poses = lambda: (pose, pose)  # type: ignore[method-assign]

    buffer = np.zeros((height, width, 3), dtype=np.uint8)

    try:
        viewer.ensureStarted(STARTUP_TIMEOUT)

        deadline = time.perf_counter() + max(0.0, warmup)
        while time.perf_counter() < deadline:
            camera.grabFrame(buffer)

        receivedBefore, bytesBefore = viewer.transferStats()
        frames = 0
        latencies: List[float] = []
        started = time.perf_counter()
        while time.perf_counter() - started < seconds:
            frameStarted = time.perf_counter()
            timestamp, _ = camera.grabFrame(buffer)
            elapsedMs = (time.perf_counter() - frameStarted) * 1000.0
            if timestamp:
                frames += 1
                latencies.append(elapsedMs)
        elapsed = time.perf_counter() - started

        receivedAfter, bytesAfter = viewer.transferStats()
        stats = viewer.stats()
        receivedFrames = receivedAfter - receivedBefore
        receivedBytes = bytesAfter - bytesBefore
    finally:
        camera.close()

    latencies.sort()
    fps = frames / elapsed if elapsed > 0 else 0.0
    receivedFps = receivedFrames / elapsed if elapsed > 0 else 0.0
    meanMs = statistics.fmean(latencies) if latencies else 0.0
    return {
        "size": f"{width}x{height}",
        "width": width,
        "height": height,
        "seconds": elapsed,
        "frames": frames,
        "fps": fps,
        "received_fps": receivedFps,
        "throughput_mbps": (receivedBytes / elapsed / (1024 * 1024))
        if elapsed
        else 0.0,
        "mean_ms": meanMs,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "max_ms": latencies[-1] if latencies else 0.0,
        "renderer": stats,
    }


def formatTable(results: Sequence[Dict[str, Any]]) -> str:
    """Formats benchmark results as a human-readable table."""
    header = (
        f"{'size':>10}  {'fps':>7}  {'recv':>7}  {'mean':>7}  {'p50':>7}  "
        f"{'p95':>7}  {'render':>7}  {'copy':>7}  {'send':>7}  {'drop':>5}"
    )
    lines = [header, "-" * len(header)]
    for result in results:
        renderer = result.get("renderer") or {}
        lines.append(
            f"{result['size']:>10}  {result['fps']:7.1f}  "
            f"{result['received_fps']:7.1f}  {result['mean_ms']:7.2f}  "
            f"{result['p50_ms']:7.2f}  {result['p95_ms']:7.2f}  "
            f"{renderer.get('renderMs', 0.0):7.2f}  "
            f"{renderer.get('copyMs', 0.0):7.2f}  "
            f"{renderer.get('sendMs', 0.0):7.2f}  "
            f"{renderer.get('dropped', 0):5d}"
        )
    return "\n".join(lines)


def runChild(args: argparse.Namespace) -> int:
    """Measures one resolution and prints its result."""
    width, height = parseSize(args.size)
    result = measure(
        width,
        height,
        args.seconds,
        args.warmup,
        args.target_fps,
        collectStats=not args.no_stats,
    )
    if args.json:
        print(json.dumps(result))
    else:
        print(formatTable([result]))
    if args.min_fps > 0 and result["fps"] < args.min_fps:
        print(
            f"{result['size']}: {result['fps']:.1f} FPS is below the "
            f"{args.min_fps:.1f} FPS minimum",
            file=sys.stderr,
        )
        return 1
    return 0


def spawnSize(args: argparse.Namespace, size: str) -> subprocess.CompletedProcess[str]:
    """Runs one resolution in a fresh process."""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--size",
        size,
        "--seconds",
        str(args.seconds),
        "--warmup",
        str(args.warmup),
        "--target-fps",
        str(args.target_fps),
        "--json",
    ]
    if args.no_stats:
        command.append("--no-stats")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=args.timeout,
    )


def parseArgs(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure end-to-end simulated camera throughput.",
    )
    parser.add_argument(
        "--size",
        help="Measure a single WIDTHxHEIGHT resolution in this process.",
    )
    parser.add_argument(
        "--sizes",
        default=",".join(DEFAULT_SIZES),
        help=f"Comma-separated resolutions (default: {','.join(DEFAULT_SIZES)}).",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help=f"Measurement window in seconds (default: {DEFAULT_SECONDS}).",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=DEFAULT_WARMUP,
        help=f"Warm-up time before measuring (default: {DEFAULT_WARMUP}).",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=120.0,
        help="Camera mode FPS; frames are throttled to this rate (default: 120).",
    )
    parser.add_argument(
        "--min-fps",
        type=float,
        default=0.0,
        help="Exit non-zero if any measured resolution is slower than this.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Per-resolution subprocess timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Disable renderer-side render/readback/send diagnostics.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parseArgs(argv)
    if args.size:
        return runChild(args)

    sizes = [size.strip() for size in args.sizes.split(",") if size.strip()]
    if not sizes:
        print("no resolutions to measure", file=sys.stderr)
        return 2

    results: List[Dict[str, Any]] = []
    failed = False
    for size in sizes:
        # Validate before spawning so a typo fails fast.
        parseSize(size)
        process = spawnSize(args, size)
        if process.returncode != 0:
            failed = True
            print(f"=== {size} failed", file=sys.stderr)
            if process.stdout:
                print(process.stdout, file=sys.stderr)
            if process.stderr:
                print(process.stderr, file=sys.stderr)
            continue
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        if not lines:
            failed = True
            print(f"=== {size} produced no output", file=sys.stderr)
            continue
        try:
            results.append(json.loads(lines[-1]))
        except json.JSONDecodeError:
            failed = True
            print(f"=== {size} produced invalid output", file=sys.stderr)
            print(process.stdout, file=sys.stderr)

    if args.json:
        print(json.dumps(results, indent=2))
    elif results:
        print(formatTable(results))

    if args.min_fps > 0:
        for result in results:
            if result["fps"] < args.min_fps:
                print(
                    f"{result['size']}: {result['fps']:.1f} FPS is below the "
                    f"{args.min_fps:.1f} FPS minimum",
                    file=sys.stderr,
                )
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
