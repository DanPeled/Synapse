#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Measure Synapse throughput and latency against real cameras.

The project passed with ``--project`` supplies the camera set through its
``config/settings.yml``; this script never assumes specific device paths or a
particular host. A typical comparison is:

1. Capture a single-camera baseline with ``--no-hotplug``.
2. Capture the multi-camera result with the same flag and the same warmup and
   duration.
3. Optionally pass ``--baseline-json`` to evaluate the per-camera and aggregate
   throughput ratios against that baseline.

``--no-hotplug`` keeps the measured set equal to the configured set, which
otherwise grows silently as USB cameras are discovered. ``--no-pipelines``
still applies each configured video mode before unbinding pipelines, so a
capture/stream-only stage measures the real sensor format rather than a
fallback mode. Every report records the effective resolution, FPS, pixel
format, hotplug mode, pipeline mode, stream mode, USB topology, and host sample
so a result can be reproduced or compared with a later run.

Measurement notes for future capture experiments:

* CSCore's ``grabFrameDirect`` family only returns a timestamp from Python and
  leaves the supplied NumPy array untouched. Its pixel data is owned by the
  sink and invalidated by the next grab, so it cannot back the camera handle's
  lease without a full copy. Do not replace ``grabFrame`` with it on the basis
  of API name alone.
* ``--opencv-threads`` exists to A/B OpenCV's global worker count without
  editing code. Two-camera measurements on the development computer did not
  show a throughput or CPU gain from reducing the default count, so the default
  remains unchanged.
* ``--gil-switch-interval`` is a diagnostic control for CPython thread handoffs.
  Simulated 1/2/4/8-camera runs showed no effect at a normal source rate, and
  an extreme 8-camera stream load showed no gain over the default. Use
  ``scripts/benchmark_simulated_cameras.py`` for hardware-free thread scaling
  checks; simulated results must not be reported as real-camera throughput.
* Uncompressed YUYV modes avoid JPEG decode but trade away frame rate or use
  more CPU for format conversion. Any switch must be a user-visible video-mode
  choice, never a silent fallback.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import psutil
from synapse.core.config import Config
from synapse.core.global_settings import GlobalSettings
from synapse.core.performance import summarizeCameras
from synapse.core.runtime_handler import RuntimeManager
from synapse.hardware.deploy_dir import DeployDirectory
from synapse_net.nt_client import NtClient

DEFAULT_THRESHOLD = 0.83
SAMPLE_INTERVAL_SECONDS = 0.25


def collectUsbTopology() -> Dict[str, Any]:
    """Collect bus topology with the first available platform tool."""
    candidates: List[Tuple[str, List[str]]] = []
    if shutil.which("lsusb"):
        candidates.append(("lsusb -t", ["lsusb", "-t"]))
    if shutil.which("system_profiler"):
        candidates.append(
            ("system_profiler SPUSBDataType", ["system_profiler", "SPUSBDataType"])
        )
    if shutil.which("wmic"):
        candidates.append(
            (
                "wmic path win32_usbcontrollerdevice get dependent",
                ["wmic", "path", "win32_usbcontrollerdevice", "get", "dependent"],
            )
        )

    for label, command in candidates:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0 and completed.stdout.strip():
            return {
                "available": True,
                "command": label,
                "output": completed.stdout.strip(),
            }

    return {
        "available": False,
        "command": None,
        "output": "No supported USB topology tool was available.",
    }


def readBaselineFps(path: Path) -> float:
    """Read a baseline FPS from a previous report produced by this script."""
    with path.open(encoding="utf-8") as file:
        report = json.load(file)

    if report.get("baseline_fps") is not None:
        return float(report["baseline_fps"])

    cameras = report.get("cameras") or []
    if not cameras:
        raise ValueError(f"{path} does not contain a baseline FPS")
    return float(cameras[0]["processed_fps"])


def createRuntime(
    project: Path,
    publishStreams: bool = False,
    allowHotplug: bool = True,
    usePipelines: bool = True,
    opencvThreads: Optional[int] = None,
    gilSwitchInterval: Optional[float] = None,
) -> RuntimeManager:
    """Configure and start a headless runtime for a camera project.

    ``allowHotplug=False`` disables the background scanner so only configured
    cameras are measured. ``usePipelines=False`` applies configured video
    modes through the normal pipeline setup path and then unbinds the
    pipelines, isolating capture and publication without changing resolution.
    ``opencvThreads`` changes OpenCV's global worker count so multi-camera
    A/B runs can test whether per-call threading is oversubscribing the host.
    ``gilSwitchInterval`` changes how often CPython yields the GIL between
    threads, which can affect the many per-camera producer, worker, and publish
    lanes even when native capture releases the GIL.
    """
    if opencvThreads is not None:
        cv2.setNumThreads(opencvThreads)
    if gilSwitchInterval is not None:
        sys.setswitchinterval(gilSwitchInterval)
    configPath = project / "config" / "settings.yml"
    if not configPath.exists():
        raise FileNotFoundError(f"Missing project config: {configPath}")

    config = Config()
    config.load(configPath)
    DeployDirectory.setup(project)
    settings = config.getConfigMap()
    GlobalSettings.setup(settings.get("global", {}))
    NtClient.NT_TABLE = config.network.name or NtClient.NT_TABLE

    runtime = RuntimeManager(project)
    if not allowHotplug:
        # Keep the measured camera set exactly as configured. The hotplug
        # scanner would otherwise add every attached USB camera and silently
        # turn a single-camera baseline into a multi-camera measurement.
        setattr(runtime.cameraHandler, "scanCameras", lambda *args, **kwargs: None)
    if not usePipelines:
        # Capture/stream-only stage: skip default pipeline creation and bind no
        # pipeline so measurement isolates the capture and publish layers.
        setattr(runtime, "assignDefaultPipelines", lambda: None)
    runtime.setup(project, sendSettingsInNT=False)
    if not usePipelines:
        # Apply the configured camera settings (including video mode), then
        # unbind pipelines so processing is excluded from the measurement.
        for cameraIndex in runtime.cameraHandler.cameraHandles:
            pipelineIndex = runtime.pipelineHandler.getDefaultPipeline(cameraIndex)
            runtime.setPipelineByIndex(cameraIndex, pipelineIndex)
            runtime.pipelineBindings[cameraIndex] = -1
    # Headless measurements should not spend memory bandwidth encoding MJPEG
    # streams nobody is watching. Recording stays available in normal runs.
    runtime.cameraHandler.setPublishingEnabled(publishStreams)
    return runtime


def describeCameras(runtime: RuntimeManager) -> Dict[int, Dict[str, Any]]:
    """Describe configured video modes so reports are self-contained."""
    descriptions: Dict[int, Dict[str, Any]] = {}
    for cameraIndex, handle in runtime.cameraHandler.cameraHandles.items():
        try:
            mode = handle.camera.getVideoMode()
            width, height, fps = int(mode.width), int(mode.height), int(mode.fps)
            pixelFormat = getattr(getattr(mode, "pixelFormat", None), "name", None)
            if pixelFormat is None:
                pixelFormat = str(getattr(mode, "pixelFormat", "unknown"))
        except Exception:
            width, height, fps, pixelFormat = 0, 0, 0, "unknown"

        descriptions[cameraIndex] = {
            "name": getattr(handle, "name", str(cameraIndex)),
            "resolution": f"{width}x{height}" if width and height else "unknown",
            "target_fps": fps,
            "pixel_format": pixelFormat,
        }
    return descriptions


def sampleHost(process: psutil.Process, durationSeconds: float) -> Dict[str, Any]:
    """Sample process CPU and RSS while the measurement window is active."""
    process.cpu_percent(interval=None)
    cpuSamples: List[float] = []
    peakRss = process.memory_info().rss
    deadline = time.monotonic() + durationSeconds

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(SAMPLE_INTERVAL_SECONDS, remaining))
        cpuSamples.append(process.cpu_percent(interval=None))
        peakRss = max(peakRss, process.memory_info().rss)

    return {
        "cpu_percent_mean": (sum(cpuSamples) / len(cpuSamples) if cpuSamples else 0.0),
        "cpu_percent_max": max(cpuSamples, default=0.0),
        "peak_rss_bytes": peakRss,
    }


def buildReport(
    runtime: RuntimeManager,
    warmupSeconds: float,
    durationSeconds: float,
    baselineFps: Optional[float],
    threshold: float,
    publishStreams: bool,
    allowHotplug: bool,
    usePipelines: bool,
    topology: Dict[str, Any],
    hostSample: Dict[str, Any],
    startedAt: datetime,
) -> Dict[str, Any]:
    """Merge runtime counters with environment information into one report."""
    summary = summarizeCameras(
        runtime.getPerformanceStats(), baselineFps=baselineFps, threshold=threshold
    )
    descriptions = describeCameras(runtime)
    cameras: List[Dict[str, Any]] = []
    for camera in summary["cameras"]:
        merged = dict(descriptions.get(camera["camera_index"], {}))
        merged.update(camera)
        cameras.append(merged)
    summary["cameras"] = cameras

    summary["measurement"] = {
        "started_at": startedAt.isoformat(),
        "warmup_seconds": warmupSeconds,
        "duration_seconds": durationSeconds,
        "stream_publication": "enabled" if publishStreams else "disabled",
        "hotplug_scan": "enabled" if allowHotplug else "disabled",
        "pipelines": "enabled" if usePipelines else "disabled",
        "opencv_threads": cv2.getNumThreads(),
        "python_switch_interval_seconds": sys.getswitchinterval(),
        "python_threads": threading.active_count(),
    }
    summary["host"] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": psutil.cpu_count(logical=True),
    }
    summary["process"] = hostSample
    summary["usb_topology"] = topology
    return summary


def parseArgs(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Synapse project root containing config/settings.yml (default: cwd)",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=10.0,
        help="Seconds to run before resetting counters (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Measurement window in seconds (default: 60)",
    )
    parser.add_argument(
        "--baseline-fps",
        type=float,
        default=None,
        help="Single-camera processed FPS used for the 83%% pass check",
    )
    parser.add_argument(
        "--baseline-json",
        type=Path,
        default=None,
        help="Previous benchmark report to read the baseline FPS from",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Required fraction of baseline FPS (default: 0.83)",
    )
    parser.add_argument(
        "--streams",
        action="store_true",
        help="Keep stream/record publication enabled during measurement",
    )
    parser.add_argument(
        "--no-hotplug",
        action="store_true",
        help="Use only the cameras declared in the project config",
    )
    parser.add_argument(
        "--no-pipelines",
        action="store_true",
        help="Measure capture and stream publication without vision pipelines",
    )
    parser.add_argument(
        "--opencv-threads",
        type=int,
        default=None,
        help="Set OpenCV's global worker count for the measurement",
    )
    parser.add_argument(
        "--gil-switch-interval",
        type=float,
        default=None,
        help="Set CPython's GIL switch interval in seconds for the measurement",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Also write the JSON report to this path",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parseArgs(argv)
    if args.warmup < 0 or args.duration <= 0:
        raise ValueError("warmup must be >= 0 and duration must be > 0")

    baselineFps = args.baseline_fps
    if args.baseline_json is not None:
        baselineFps = readBaselineFps(args.baseline_json)

    runtime = createRuntime(
        args.project.resolve(),
        publishStreams=args.streams,
        allowHotplug=not args.no_hotplug,
        usePipelines=not args.no_pipelines,
        opencvThreads=args.opencv_threads,
        gilSwitchInterval=args.gil_switch_interval,
    )
    try:
        if args.warmup:
            time.sleep(args.warmup)
        runtime.resetPerformanceStats()
        startedAt = datetime.now(timezone.utc)
        hostSample = sampleHost(psutil.Process(), args.duration)
        report = buildReport(
            runtime=runtime,
            warmupSeconds=args.warmup,
            durationSeconds=args.duration,
            baselineFps=baselineFps,
            threshold=args.threshold,
            publishStreams=args.streams,
            allowHotplug=not args.no_hotplug,
            usePipelines=not args.no_pipelines,
            topology=collectUsbTopology(),
            hostSample=hostSample,
            startedAt=startedAt,
        )
    finally:
        runtime.cleanup()

    output = json.dumps(report, indent=2)
    print(output)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")

    return 0 if report["meets_target"] is not False else 1


if __name__ == "__main__":
    sys.exit(main())
