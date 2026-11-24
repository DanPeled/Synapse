#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Measure Synapse thread scaling with deterministic in-memory cameras.

This benchmark uses a ``SynapseCamera`` implementation that fills a NumPy buffer
on a paced thread. It never opens a USB device, so it can exercise the runtime's
per-camera ``FrameGrabber``, ``processCamera``, and ``StreamPublisher`` threads
when only one or no physical camera is available. Results are *not* a proxy for
real capture throughput: JPEG decode, USB transport, and camera driver behavior
are intentionally absent.

The generated project is temporary and contains only the configured camera
count. ``--gil-switch-interval`` changes CPython's global scheduling interval so
the report records whether Python-level handoffs are sensitive to it. A typical
comparison holds every other flag constant and changes only camera count or
switch interval.

Measured notes from the development computer:

* At a normal 640x480@120 synthetic rate, 1, 2, 4, and 8 cameras produced
  about 118 FPS per camera with 6, 9, 15, and 27 active Python threads. Changing
  the switch interval from 0.0005 to 0.02 seconds did not change FPS.
* An intentionally unrealistic 1000 FPS synthetic rate with 8 cameras and
  streams enabled ran about 913-925 FPS per camera. The default 0.005 second
  interval was at least as fast as 0.001 or 0.01 and used less CPU. That is not
  evidence for changing a global interpreter setting in production code.
* Each camera occupies three Python threads. Moving cameras into separate
  processes to obtain separate GILs would require sharing full-resolution
  frames across process boundaries and duplicating settings, stream, and metric
  state, so it should only be considered after profiling shows a Python-only
  bottleneck.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import psutil
from cscore import VideoMode
from synapse.core.camera.synapse_camera import SynapseCamera
from synapse.core.config import Config
from synapse.core.global_settings import GlobalSettings
from synapse.core.performance import summarizeCameras
from synapse.core.runtime_handler import RuntimeManager
from synapse.hardware.deploy_dir import DeployDirectory
from synapse.stypes import CameraID, PropertyMetaDict, Size
from synapse_net.nt_client import NtClient
from wpiutil import PixelFormat

SAMPLE_INTERVAL_SECONDS = 0.25


class SyntheticCamera(SynapseCamera):
    """A deterministic, paced camera backed by an in-memory color pattern."""

    WIDTH = 640
    HEIGHT = 480
    FPS = 120

    def __init__(self, index: CameraID) -> None:
        self.mode = VideoMode(
            PixelFormat.MJPEG, type(self).WIDTH, type(self).HEIGHT, type(self).FPS
        )
        self.pattern = np.random.default_rng(index).integers(
            0, 256, (self.mode.height, self.mode.width, 3), dtype=np.uint8
        )
        self.nextFrame = time.monotonic()
        self.closed = False

    @classmethod
    def create(
        cls,
        *_,
        path: Union[str, int],
        index: CameraID,
    ) -> "SyntheticCamera":
        """Create one synthetic camera for a configured camera index."""
        return cls(index)

    def grabFrame(self, buffer: np.ndarray) -> Tuple[float, Optional[np.ndarray]]:
        """Copy the pattern into ``buffer`` at the configured cadence."""
        if self.closed:
            return 0, None

        now = time.monotonic()
        if now < self.nextFrame:
            time.sleep(min(self.nextFrame - now, 0.01))
            now = time.monotonic()
        self.nextFrame = now + 1.0 / self.mode.fps

        if buffer.shape != self.pattern.shape:
            self.pattern = np.random.default_rng(0).integers(
                0, 256, buffer.shape, dtype=np.uint8
            )
        np.copyto(buffer, self.pattern)
        return int(now * 1_000_000), buffer

    def close(self) -> None:
        """Mark the synthetic device closed."""
        self.closed = True

    def isConnected(self) -> bool:
        """Return whether the synthetic device is still open."""
        return not self.closed

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        """Ignore property writes because the synthetic device has no controls."""

    def getProperty(self, prop: str) -> Union[int, float, None]:
        """Return no property value because the synthetic device has no controls."""
        return None

    def setVideoMode(self, videoMode: VideoMode) -> None:
        """Replace the synthetic mode and regenerate the matching pattern."""
        self.mode = VideoMode(
            PixelFormat.MJPEG, videoMode.width, videoMode.height, videoMode.fps
        )
        self.pattern = np.random.default_rng(0).integers(
            0, 256, (self.mode.height, self.mode.width, 3), dtype=np.uint8
        )

    def getResolution(self) -> Size:
        """Return the active synthetic resolution."""
        return self.mode.width, self.mode.height

    def getSupportedResolutions(self) -> List[Size]:
        """Return only the active synthetic resolution."""
        return [(self.mode.width, self.mode.height)]

    def getPropertyMeta(self) -> PropertyMetaDict:
        """Return empty metadata because the synthetic device has no controls."""
        return {}

    def getMaxFPS(self) -> float:
        """Return the active synthetic frame-rate cap."""
        return float(self.mode.fps)

    def enumerateVideoModes(self) -> List[VideoMode]:
        """Return the single supported synthetic video mode."""
        return [self.mode]

    def getVideoMode(self) -> VideoMode:
        """Return the active synthetic video mode."""
        return self.mode


def writeProject(root: Path, cameraCount: int, resolution: Tuple[int, int]) -> None:
    """Write a minimal camera project used only for this measurement."""
    configRoot = root / "config"
    configRoot.mkdir(parents=True, exist_ok=True)
    (configRoot / "settings.yml").write_text(
        "network: {team_number: 9738, name: SynapseSimBench, ip: null, interface: null}\n"
        f"global:\n  cameras: {list(range(cameraCount))}\n".replace("'", ""),
        encoding="utf-8",
    )

    width, height = resolution
    for cameraIndex in range(cameraCount):
        cameraRoot = configRoot / f"camera_{cameraIndex}"
        cameraRoot.mkdir(exist_ok=True)
        (cameraRoot / "camera_configs.yml").write_text(
            "camera_configs:\n"
            f"  name: Sim Camera {cameraIndex}\n"
            f"  id: sim-{cameraIndex}\n"
            "  default_pipeline: 0\n"
            "  stream_res: [320, 240]\n",
            encoding="utf-8",
        )
        (cameraRoot / "pipeline_settings.yml").write_text(
            "pipeline_configs:\n"
            "  0:\n"
            "    name: BenchmarkDriver\n"
            "    type: DriverViewPipeline\n"
            "    settings:\n"
            "      crosshair_x: 0.0\n"
            "      crosshair_y: 0.0\n"
            f"      resolution: {width}x{height}\n",
            encoding="utf-8",
        )


def createRuntime(
    project: Path,
    publishStreams: bool,
    usePipelines: bool,
    gilSwitchInterval: Optional[float],
    opencvThreads: Optional[int],
) -> RuntimeManager:
    """Start a headless runtime backed entirely by synthetic cameras."""
    if opencvThreads is not None:
        cv2.setNumThreads(opencvThreads)
    if gilSwitchInterval is not None:
        sys.setswitchinterval(gilSwitchInterval)

    config = Config()
    config.load(project / "config" / "settings.yml")
    DeployDirectory.setup(project)
    settings = config.getConfigMap()
    GlobalSettings.setup(settings.get("global", {}))
    NtClient.NT_TABLE = config.network.name or NtClient.NT_TABLE

    runtime = RuntimeManager(project)
    runtime.cameraHandler.setCameraType(SyntheticCamera)
    if not usePipelines:
        setattr(runtime, "assignDefaultPipelines", lambda: None)
    runtime.setup(project, sendSettingsInNT=False)
    if not usePipelines:
        for cameraIndex in runtime.cameraHandler.cameraHandles:
            pipelineIndex = runtime.pipelineHandler.getDefaultPipeline(cameraIndex)
            runtime.setPipelineByIndex(cameraIndex, pipelineIndex)
            runtime.pipelineBindings[cameraIndex] = -1
    runtime.cameraHandler.setPublishingEnabled(publishStreams)
    return runtime


def describeCameras(runtime: RuntimeManager) -> Dict[int, Dict[str, Any]]:
    """Describe effective synthetic modes so reports are self-contained."""
    descriptions: Dict[int, Dict[str, Any]] = {}
    for cameraIndex, handle in runtime.cameraHandler.cameraHandles.items():
        mode = handle.camera.getVideoMode()
        descriptions[cameraIndex] = {
            "name": getattr(handle, "name", str(cameraIndex)),
            "resolution": f"{mode.width}x{mode.height}",
            "target_fps": int(mode.fps),
            "pixel_format": getattr(getattr(mode, "pixelFormat", None), "name", "unknown"),
        }
    return descriptions


def sampleHost(process: psutil.Process, durationSeconds: float) -> Dict[str, Any]:
    """Sample process CPU and RSS during the measurement window."""
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
        "cpu_percent_mean": sum(cpuSamples) / len(cpuSamples) if cpuSamples else 0.0,
        "cpu_percent_max": max(cpuSamples, default=0.0),
        "peak_rss_bytes": peakRss,
    }


def buildReport(
    runtime: RuntimeManager,
    cameraCount: int,
    width: int,
    height: int,
    sourceFps: int,
    warmupSeconds: float,
    durationSeconds: float,
    publishStreams: bool,
    usePipelines: bool,
    hostSample: Dict[str, Any],
    startedAt: datetime,
) -> Dict[str, Any]:
    """Combine runtime counters with the controls needed to reproduce a run."""
    summary = summarizeCameras(runtime.getPerformanceStats())
    descriptions = describeCameras(runtime)
    cameras: List[Dict[str, Any]] = []
    for camera in summary["cameras"]:
        merged = dict(descriptions.get(camera["camera_index"], {}))
        merged.update(camera)
        cameras.append(merged)
    summary["cameras"] = cameras

    return {
        "started_at": startedAt.isoformat(),
        "measurement": {
            "backend": "synthetic",
            "camera_count": cameraCount,
            "source_resolution": f"{width}x{height}",
            "source_fps": sourceFps,
            "warmup_seconds": warmupSeconds,
            "duration_seconds": durationSeconds,
            "stream_publication": "enabled" if publishStreams else "disabled",
            "pipelines": "enabled" if usePipelines else "disabled",
            "python_switch_interval_seconds": sys.getswitchinterval(),
            "opencv_threads": cv2.getNumThreads(),
        },
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
        },
        "threads": {
            "count": threading.active_count(),
            "names": [thread.name for thread in threading.enumerate()],
        },
        "process": hostSample,
        "cameras": summary["cameras"],
        "aggregate_fps": summary["aggregate_fps"],
    }


def parseArgs(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse benchmark controls."""
    parser = argparse.ArgumentParser(
        description="Measure Synapse thread scaling with synthetic cameras"
    )
    parser.add_argument("--cameras", type=int, default=4, help="Number of synthetic cameras")
    parser.add_argument("--width", type=int, default=640, help="Synthetic frame width")
    parser.add_argument("--height", type=int, default=480, help="Synthetic frame height")
    parser.add_argument("--fps", type=int, default=120, help="Synthetic source frame rate")
    parser.add_argument("--warmup", type=float, default=3.0, help="Warmup seconds")
    parser.add_argument("--duration", type=float, default=8.0, help="Measurement seconds")
    parser.add_argument(
        "--streams", action="store_true", help="Keep stream publication enabled"
    )
    parser.add_argument(
        "--no-pipelines", action="store_true", help="Measure capture and publication only"
    )
    parser.add_argument(
        "--gil-switch-interval",
        type=float,
        default=None,
        help="Set CPython's GIL switch interval in seconds",
    )
    parser.add_argument(
        "--opencv-threads",
        type=int,
        default=None,
        help="Set OpenCV's global worker count for the measurement",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Also write the JSON report here"
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Run one synthetic multi-camera measurement and print its JSON report."""
    args = parseArgs(argv)
    if args.cameras < 1 or args.width < 1 or args.height < 1 or args.fps < 1:
        raise ValueError("cameras, width, height, and fps must all be positive")
    if args.warmup < 0 or args.duration <= 0:
        raise ValueError("warmup must be >= 0 and duration must be > 0")

    SyntheticCamera.WIDTH = args.width
    SyntheticCamera.HEIGHT = args.height
    SyntheticCamera.FPS = args.fps

    with tempfile.TemporaryDirectory(prefix="synapse-sim-bench-") as temporary:
        project = Path(temporary)
        writeProject(project, args.cameras, (args.width, args.height))
        runtime = createRuntime(
            project,
            publishStreams=args.streams,
            usePipelines=not args.no_pipelines,
            gilSwitchInterval=args.gil_switch_interval,
            opencvThreads=args.opencv_threads,
        )
        try:
            if args.warmup:
                time.sleep(args.warmup)
            runtime.resetPerformanceStats()
            startedAt = datetime.now(timezone.utc)
            hostSample = sampleHost(psutil.Process(), args.duration)
            report = buildReport(
                runtime=runtime,
                cameraCount=args.cameras,
                width=args.width,
                height=args.height,
                sourceFps=args.fps,
                warmupSeconds=args.warmup,
                durationSeconds=args.duration,
                publishStreams=args.streams,
                usePipelines=not args.no_pipelines,
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
