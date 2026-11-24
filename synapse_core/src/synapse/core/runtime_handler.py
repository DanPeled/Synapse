# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import faulthandler
import math
import os
import tempfile
import threading
import time
import traceback
from asyncio import Queue
from pathlib import Path
from typing import Any, Dict, Final, Iterable, List, Optional, Tuple, TypeAlias, cast

import cv2
import numpy as np
import synapse.__version__ as versionFile
import synapse.log as log
from ntcore import (
    DoublePublisher,
    Event,
    EventFlags,
    NetworkTable,
    NetworkTableEntry,
    NetworkTableInstance,
    NetworkTableType,
    StringPublisher,
    ValueEventData,
)
from synapse_net.generated.messages.v1 import (
    CameraPerformanceProto,
    HardwareMetricsProto,
    MessageTypeProto,
)
from synapse_net.nt_client import NtClient, RemoteConnectionIP
from synapse_net.socketServer import WebSocketServer, createMessage
from wpimath.units import seconds, secondsToMilliseconds

from ..bcolors import MarkupColors
from ..callback import Callback
from ..stypes import CameraID, CameraName, DataValue, Frame, PipelineID
from ..util import Publisher, getIP, getPublisher
from .camera.camera_handle import CameraHandle
from .camera_factory import CameraSettingsKeys, getCameraSettingEntry, getCameraTable
from .camera_handler import CameraHandler
from .config import Config, NetworkConfig, yaml
from .lifecycle import joinThread
from .nt_keys import NTKeys
from .performance import CameraPerformanceTracker, FrameRateMeter
from .pipeline import (
    FrameResult,
    Pipeline,
    PipelineProcessFrameResult,
    PipelineSettings,
    getPipelineTypename,
)
from .pipeline_handler import PipelineHandler
from .settings_api import CameraSettings


def sendWebUIIP():
    if NtClient.INSTANCE is not None:
        NtClient.INSTANCE.nt_inst.getTable(NtClient.INSTANCE.NT_TABLE).getEntry(
            "web_ui"
        ).setString(f"{getIP()}:3000")


SettingChangedCallback: TypeAlias = Callback[[str, Any, CameraID]]
DEFAULT_PIPELINE_FOR_NEW_CAMERA: Final[PipelineID] = 0
METRICS_INTERVAL_SECONDS: Final[float] = 1.0
# FPS is reported at most once per second by sendLatency; use the same span
# for the measurement window so the published value describes that interval.
FRAME_FPS_WINDOW_SECONDS: Final[float] = 1.0
_ROTATIONS: Final[dict[int, int]] = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

# UI changes often arrive in bursts. Wait for a short quiet period before
# writing, but bound the wait so a continuous stream still produces saves.
SAVE_DEBOUNCE_SECONDS: Final[float] = 0.25
MAX_SAVE_DELAY_SECONDS: Final[float] = 1.0
SAVE_WORKER_TIMEOUT_SECONDS: Final[float] = 5.0


def _atomicWriteText(path: Path, content: str) -> None:
    """Write a YAML/text file atomically using a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    existingMode: Optional[int] = None
    try:
        existingMode = path.stat().st_mode & 0o777
    except OSError:
        pass

    descriptor, tempName = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if existingMode is not None:
            os.chmod(tempName, existingMode)
        os.replace(tempName, path)
    except Exception:
        try:
            os.unlink(tempName)
        except OSError:
            pass
        raise


def _metricsMonotonic() -> float:
    """Cycle clock for the metrics loop, kept separate for tests."""
    return time.monotonic()


def _cameraFpsLimit(handle: CameraHandle) -> Optional[float]:
    """Best known physical frame-rate bound for a camera, if available.

    Prefer the active video mode: a 120 FPS sensor configured for 30 FPS must
    not be allowed to report 120. ``getMaxFPS()`` is the fallback for backends
    that do not expose a usable mode.
    """
    candidates: List[float] = []
    for getter in (lambda: handle.camera.getVideoMode().fps, handle.camera.getMaxFPS):
        try:
            fps = float(getter())
        except Exception:
            continue
        if math.isfinite(fps) and fps > 0:
            candidates.append(fps)
    return min(candidates) if candidates else None


def _cameraModeGeneration(handle: CameraHandle) -> int:
    """Return a camera's mode generation, or 0 for backends without one."""
    try:
        generation = handle.videoModeGeneration
    except Exception:
        return 0
    if isinstance(generation, bool) or not isinstance(generation, int):
        return 0
    return generation


class RuntimeManager:
    """
    Handles the loading, configuration, and runtime execution of vision pipelines
    across multiple camera devices. It interfaces with NetworkTables for dynamic
    pipeline control and provides metrics reporting for system diagnostics.
    """

    def __init__(self, directory: Path):
        """
        Initializes the RuntimeManager by preparing the loader and camera handler.

        Args:
            directory (Path): Root directory containing pipeline definitions.
        """
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param pipelineDirectory: Root directory to search for pipeline files
        """

        faulthandler.enable()

        self.pipelineHandler: PipelineHandler = PipelineHandler(directory)
        self.cameraHandler: CameraHandler = CameraHandler()
        self.pipelineBindings: Dict[CameraID, PipelineID] = {}
        self.cameraFrameEntries: Dict[CameraID, NetworkTableEntry] = {}
        # Last known "view id" per camera, kept up to date by an NT listener so
        # the per-frame path does not have to read NetworkTables.
        self.cameraViewIDs: Dict[CameraID, str] = {}
        self.propPubs: Dict[Tuple[CameraID, str], Publisher] = {}
        self._latencyPubs: Dict[Tuple[CameraID, str], DoublePublisher] = {}
        self._frameRateMeters: Dict[CameraID, FrameRateMeter] = {}
        self._cameraFpsLimits: Dict[CameraID, float] = {}
        self._cameraFpsLimitGenerations: Dict[CameraID, int] = {}
        self._lastLatencyReportTime: dict[CameraID, float] = {}
        self._performanceLock = threading.Lock()
        self._performanceTrackers: Dict[CameraID, CameraPerformanceTracker] = {}
        self._frameFixtureCache: Dict[
            CameraID, Tuple[Any, int, Tuple[int, int], int, np.ndarray]
        ] = {}
        # Persistent pipeline failures must not format/log a full traceback on
        # every camera frame. This reports the first failure per camera, then
        # periodic counts.
        self._pipelineErrorThrottle = log.ExceptionThrottle()
        self._metricsErrorThrottle = log.ExceptionThrottle()
        self.frameQueues: Dict[CameraID, Queue] = {}
        self.cameraManagementThreads: Dict[CameraID, threading.Thread] = {}
        self._ntListeners: List[int] = []
        self._ntListenerKeys: Dict[Tuple[CameraID, str, str], int] = {}
        self._ntListenerLock = threading.Lock()

        # ``running`` is set while the runtime should keep going. ``stopped`` is
        # the inverse, so worker loops can block until shutdown is requested.
        self.running = threading.Event()
        self.running.set()
        self.stopped = threading.Event()

        self._cleanupLock = threading.Lock()
        self._cleanedUp = False

        self.isSetup: bool = False
        self.setupEvent = threading.Event()
        self.lastLatencyReportTime: float = time.time()
        self.versionPublisher: Optional[StringPublisher] = None

        self.DEFAULT_STEP = "step_0"

        self.metricsThread: Optional[threading.Thread] = None

        self.networkSettings: NetworkConfig = NetworkConfig(
            name="Synapse",
            teamNumber=0000,
            hostname="synapse",
            ip=None,
            networkInterface=None,
            prefixLength=24,
        )

        self.onSettingChanged: SettingChangedCallback = Callback()
        self.onSettingChangedFromNT: SettingChangedCallback = Callback()
        self.onPipelineChangedFromNT: Callback[PipelineID, CameraID] = Callback()
        self.onPipelineChanged: Callback[PipelineID, CameraID] = Callback()
        self.onSaveError: Callback[[Exception]] = Callback()

        # One worker owns all config writes. Requests are coalesced so bursts
        # of UI/NT callbacks result in a single (or bounded) number of saves.
        self._saveLock = threading.Lock()
        self._saveRequested = threading.Event()
        self._saveStopped = threading.Event()
        self._savePending = False
        self._saveCancelled = False
        self._saveThread: Optional[threading.Thread] = None
        self._saveDebounceSeconds = SAVE_DEBOUNCE_SECONDS

        def onAddCamera(cameraID: CameraID, name: str, handle: CameraHandle):
            with self._cleanupLock:
                if self._cleanedUp:
                    return
            # Trackers are long-lived, so create them before the process thread
            # starts. The hot path can then record without a global lock.
            with self._performanceLock:
                self._performanceTrackers.setdefault(
                    cameraID, CameraPerformanceTracker()
                )
                self._frameRateMeters.setdefault(
                    cameraID,
                    FrameRateMeter(windowSeconds=FRAME_FPS_WINDOW_SECONDS),
                )
            if cameraID not in self.pipelineBindings:
                self.pipelineBindings[cameraID] = DEFAULT_PIPELINE_FOR_NEW_CAMERA
            if (
                self.pipelineHandler.getPipeline(
                    self.pipelineBindings[cameraID], cameraid=cameraID
                )
                is None
            ):
                self.pipelineHandler.addPipeline(
                    self.pipelineBindings[cameraID],
                    "New Pipeline",
                    "ApriltagPipeline",  # TODO: maybe generate different pipeline?
                    cameraID,
                    {},
                )
                self.setPipelineByIndex(cameraID, self.pipelineBindings[cameraID])

            thread = threading.Thread(target=self.processCamera, args=(cameraID,))
            thread.daemon = True
            with self._cleanupLock:
                if self._cleanedUp:
                    return
                thread.start()
                self.cameraManagementThreads[cameraID] = thread

        self.cameraHandler.onAddCamera.add(onAddCamera)
        self.cameraHandler.onAddCamera.add(self.pipelineHandler.onAddCamera)

    def setup(self, directory: Path, sendSettingsInNT: bool):
        """
        Initializes all components:
        - Loads pipelines from the directory.
        - Initializes camera configurations.
        - Assigns default pipelines to each camera.
        - Starts metrics collection and monitoring.
        - Starts the main runtime loop.

        Args:
            directory (Path): Path to directory containing pipelines and configurations.
        """

        self.setupCallbacks()
        self.__sendSettingsInNT = sendSettingsInNT

        log.info(
            MarkupColors.header(
                "\n" + "=" * 20 + " Loading Pipeline Types & Instances... " + "=" * 20
            )
        )

        self.pipelineHandler.setup(directory)

        log.info(
            MarkupColors.header(
                "\n" + "=" * 20 + " Loading Camera Bindings & Settings... " + "=" * 20
            )
        )

        self.cameraHandler.setup()

        self.assignDefaultPipelines()

        self.setupNetworkTables()

        self.versionPublisher = (
            NetworkTableInstance.getDefault()
            .getStringTopic(f"{NtClient.NT_TABLE}/version")
            .publish()
        )

        self.versionPublisher.set(versionFile.SYNAPSE_VERSION)

        self.startMetricsThread()
        sendWebUIIP()

        self.isSetup = True
        self.setupEvent.set()

    def assignDefaultPipelines(self) -> None:
        """
        Assigns the default pipeline to each connected camera based on predefined configuration.
        """

        for cameraIndex in self.cameraHandler.cameraHandles:
            pipeline = self.pipelineHandler.getDefaultPipeline(cameraIndex)
            self.setPipelineByIndex(
                cameraIndex=cameraIndex,
                pipelineIndex=pipeline,
            )
            log.info(f"Setup default pipeline (#{pipeline}) for camera ({cameraIndex})")

    def startMetricsThread(self):
        """
        Starts a multiprocessing process and thread to:
        - Collect system metrics from a background process.
        - Publish metrics as a double array to NetworkTables from the main process.
        """

        def metricsWorker() -> None:
            from synapse.hardware.metrics import MetricsManager

            metricsManager: Final[MetricsManager] = MetricsManager()

            entry = (
                NetworkTableInstance.getDefault()
                .getDoubleArrayTopic(f"{NtClient.NT_TABLE}/{NTKeys.kMetrics.value}")
                .publish()
            )

            lastMetrics = [0.0] * 8

            while self.running.is_set():
                cycleStart = _metricsMonotonic()

                try:
                    cpuTemp = metricsManager.getCpuTemp()
                    # Pass the cycle start so the CPU sample uses an explicit
                    # timestamp instead of relying on psutil's blocking interval.
                    cpuUsage = metricsManager.sampleCpuUtilization(now=cycleStart)
                    memory = metricsManager.getMemory()
                    uptime = metricsManager.getUptime()
                    gpuMemorySplit = metricsManager.getGPUMemorySplit()
                    usedRam = metricsManager.getUsedRam()
                    usedDiskPct = metricsManager.getUsedDiskPct()
                    npuUsage = metricsManager.getNpuUsage()

                    lastMetrics = [
                        cpuTemp,
                        cpuUsage,
                        memory,
                        uptime,
                        gpuMemorySplit,
                        usedRam,
                        usedDiskPct,
                        npuUsage,
                    ]
                except Exception as error:
                    # A single unavailable sensor must not kill metrics
                    # reporting for the rest of the runtime's lifetime.
                    detail = self._metricsErrorThrottle.exceptionDetail(
                        "metrics",
                        error,
                        lambda error=error: "".join(
                            traceback.format_exception(
                                type(error), error, error.__traceback__
                            )
                        ),
                    )
                    if detail is not None:
                        log.warn(f"Metrics collection failed: {detail}")

                metrics = lastMetrics

                ws = WebSocketServer.kInstance
                if ws is not None and ws.hasClients:
                    try:

                        def buildMetricsMessage() -> bytes:
                            metricsMessage = HardwareMetricsProto(
                                cpu_temp=cpuTemp,
                                cpu_usage=cpuUsage,
                                uptime=uptime,
                                memory=memory,
                                ram_usage=usedRam,
                                disk_usage=usedDiskPct,
                            )
                            return createMessage(
                                MessageTypeProto.SEND_METRICS,
                                metricsMessage,
                            )

                        ws.sendToAllSync(buildMetricsMessage, coalesce_key=("metrics",))
                    except Exception:
                        pass

                try:
                    numericMetrics: List[Any] = [float(value) for value in metrics]
                    entry.set(cast(List[Any], numericMetrics))
                except Exception:
                    pass

                # Schedule the next wake relative to the start of this cycle so
                # collection time does not accumulate into a slower cadence.
                remaining = METRICS_INTERVAL_SECONDS - (
                    _metricsMonotonic() - cycleStart
                )
                self.stopped.wait(max(0.0, remaining))

        self.metricsThread = threading.Thread(target=metricsWorker, daemon=True)
        log.info("Starting metrics thread")
        self.metricsThread.start()

    def __setupPipelineForCamera(
        self,
        cameraIndex: CameraID,
        pipeline_config: PipelineSettings,
    ):
        """
        Internal method that configures a specific pipeline instance for a camera.
        - Initializes the pipeline.
        - Applies settings from configuration.
        - Sets up NetworkTables listeners to allow dynamic pipeline reconfiguration.

        Args:
            cameraIndex (CameraID): The camera index to configure.
            pipelineType (Type[Pipeline]): The class type of the pipeline to instantiate.
            pipeline_config (PipelineSettings): The configuration for the pipeline.
        """

        # Create instances for each pipeline only when setting them
        currPipeline = self.pipelineHandler.getPipeline(
            self.pipelineBindings[cameraIndex], cameraIndex
        )

        if currPipeline is None:
            log.err(f"No pipeline with index: {self.pipelineBindings[cameraIndex]}")
            return

        handle: Optional[CameraHandle] = self.cameraHandler.getCameraHandle(cameraIndex)

        assert handle is not None

        currPipeline.bind(cameraIndex, handle.camera)

        cameraSettings = currPipeline.getCameraSettings()

        assert cameraSettings is not None

        cameraTable: NetworkTable = getCameraTable(handle)

        self.cameraHandler.setCameraProps(
            {
                key: cameraSettings.getSetting(key)
                for key in cameraSettings.getMap().keys()
            },
            handle,
        )

        currPipeline.ntTable = cameraTable

        if not self.__sendSettingsInNT:
            return
        settingsSubtable = cameraTable.getSubTable(NTKeys.kSettings.value)
        pipeline_config.sendSettings(settingsSubtable)
        cameraSettings.sendSettings(settingsSubtable)

        def updateSettingListener(event: Event, cameraIndex=cameraIndex):
            assert isinstance(event.data, ValueEventData)

            prop: str = event.data.topic.getName().split("/")[-1]
            value: Any = self.getEventDataValue(event)
            self.updateSetting(prop, cameraIndex, value)

            self.onSettingChangedFromNT.call(prop, value, cameraIndex)

        def addlistener(settingKey: str) -> None:
            nt_table = getCameraTable(handle)
            if nt_table is not None:
                entry = nt_table.getSubTable(NTKeys.kSettings.value).getEntry(
                    settingKey
                )

                if NtClient.INSTANCE is not None:
                    self._addNtListener(
                        entry,
                        EventFlags.VALUE_REMOTE,
                        updateSettingListener,
                        # Register each setting once per camera. Switching
                        # pipelines previously stacked duplicate callbacks,
                        # multiplying setting writes and UI traffic.
                        key=(cameraIndex, NTKeys.kSettings.value, settingKey),
                    )

        for key in pipeline_config.getMap().keys():
            addlistener(key)
        for key in CameraSettings().getAPI().settings.keys():
            addlistener(key)

    def updateSetting(self, prop: str, cameraIndex: CameraID, value: Any) -> None:
        pipeline = self.pipelineHandler.getPipeline(
            self.pipelineBindings[cameraIndex], cameraIndex
        )
        assert pipeline is not None

        camera = self.cameraHandler.getCameraHandle(cameraIndex)
        camSettings = pipeline.getCameraSettings().getAPI().settings.keys()

        settings = self.pipelineHandler.getPipelineSettings(
            self.pipelineBindings[cameraIndex], cameraIndex
        )
        setting = settings.getAPI().getSetting(prop)

        if prop in camSettings:
            assert camera is not None
            camera.setProperty(prop=prop, value=value)
            pipeline.setCameraSetting(prop, value)
        elif setting is not None:
            pipeline.setSetting(prop, value)
            pipeline.onSettingChanged(setting, settings.getSetting(prop))
        else:
            log.warn(
                f"Attempted to set setting {prop} on pipeline #{pipeline.pipelineIndex} but it was not found!"
            )
            return

        self.onSettingChanged.call(prop, value, cameraIndex)

        if not self.__sendSettingsInNT:
            return

        assert camera is not None
        nt_table = getCameraTable(camera)
        key = (cameraIndex, prop)

        if key not in self.propPubs:
            settings = nt_table.getSubTable(NTKeys.kSettings.value)
            try:
                self.propPubs[key] = getPublisher(settings, prop, value)
            except Exception as e:
                log.err(
                    f"Failed to create publisher for prop '{prop}' "
                    f"(camera={cameraIndex}, value_type={type(value)}): {e}"
                )
                return

        try:
            self.propPubs[key].set(value)
        except Exception:
            pass

    @staticmethod
    def getEventDataValue(
        event: Event,
    ) -> DataValue:
        """
        Extracts the correctly typed value from a NetworkTables event based on topic type.

        Args:
            event (Event): Event containing NetworkTables data.

        Returns:
            DataValue: The parsed value from the event.
        """
        assert isinstance(event.data, ValueEventData)
        topic = event.data.topic
        topic_type = topic.getType()
        value = event.data.value

        if topic_type == NetworkTableType.BOOLEAN:
            return value.getBoolean()
        if topic_type == NetworkTableType.FLOAT:
            return value.getFloat()
        if topic_type == NetworkTableType.DOUBLE:
            return value.getDouble()
        if topic_type == NetworkTableType.INTEGER:
            return value.getInteger()
        if topic_type == NetworkTableType.STRING:
            return value.getString()
        if topic_type == NetworkTableType.BOOLEAN_ARRAY:
            return value.getBooleanArray()
        if topic_type == NetworkTableType.FLOAT_ARRAY:
            return value.getFloatArray()
        if topic_type == NetworkTableType.DOUBLE_ARRAY:
            return value.getDoubleArray()
        if topic_type == NetworkTableType.INTEGER_ARRAY:
            return value.getIntegerArray()
        if topic_type == NetworkTableType.STRING_ARRAY:
            return value.getStringArray()
        raise ValueError(f"Unsupported topic type: {topic_type}")

    def setPipelineByIndex(
        self, cameraIndex: CameraID, pipelineIndex: PipelineID
    ) -> None:
        """
        Sets a vision pipeline for a specific camera by index.

        This method validates the provided camera and pipeline indices, logs errors
        if they're invalid, and safely falls back to the current bound pipeline if needed.

        If both indices are valid:
        - Updates the binding between the camera and the pipeline.
        - Notifies NetworkTables of the selected pipeline.
        - Configures the actual processing pipeline for the camera.

        Args:
            cameraIndex (int): The index of the target camera.
            pipelineIndex (int): The index of the pipeline to assign.
        """
        if cameraIndex not in self.cameraHandler.cameraHandles:
            log.err(
                f"Invalid cameraIndex {cameraIndex}. Must be in {list(self.cameraHandler.cameraHandles.keys())})."
            )
            return

        if pipelineIndex not in self.pipelineHandler.pipelineTypeNames[cameraIndex]:
            self.pipelineHandler.addPipeline(
                self.pipelineBindings[cameraIndex],
                "New Pipeline",
                "ApriltagPipeline",  # TODO: maybe generate different pipeline?
                cameraIndex,
                {},
            )
            self.setPipelineByIndex(cameraIndex, self.pipelineBindings[cameraIndex])
            # log.err(
            #     f"Invalid pipeline index {pipelineIndex}. Must be one of {list(self.pipelineHandler.pipelineTypeNames[cameraIndex].keys())}."
            # )
            # self.setNTPipelineIndex(cameraIndex, self.pipelineBindings[cameraIndex])
            # return

        # If both indices are valid, proceed with the pipeline setting
        prev = self.pipelineHandler.getPipeline(
            self.pipelineBindings[cameraIndex], cameraIndex
        )
        if prev is not None:
            prev.invalidateCachedEntries()

        self.pipelineBindings[cameraIndex] = pipelineIndex

        self.setNTPipelineIndex(cameraIndex=cameraIndex, pipelineIndex=pipelineIndex)

        settings = self.pipelineHandler.getPipelineSettings(pipelineIndex, cameraIndex)

        self.__setupPipelineForCamera(
            cameraIndex=cameraIndex,
            pipeline_config=settings,
        )
        # Pipeline setup can change the camera's video mode; refresh the
        # physical bound used to sanity-check reported FPS.
        handle = self.cameraHandler.getCameraHandle(cameraIndex)
        if handle is not None:
            self._refreshCameraFpsLimit(cameraIndex, handle)
        self.onPipelineChanged.call(pipelineIndex, cameraIndex)
        log.info(f"Set pipeline #{pipelineIndex} for camera ({cameraIndex})")

    def setNTPipelineIndex(
        self, cameraIndex: CameraID, pipelineIndex: PipelineID
    ) -> None:
        """
        Sets the pipeline index for a specific camera via NetworkTables.

        If a valid NetworkTables instance exists, this method writes the given
        `pipeline_index` to the entry corresponding to the specified `cameraIndex`.

        This method caches the entry paths per camera index to avoid redundant lookups.

        Args:
            cameraIndex (int): The index of the camera whose pipeline is being set.
            pipeline_index (int): The index of the vision pipeline to set for the camera.
        """

        if not hasattr(self, "__pipelineEntryCache"):
            self.__pipelineEntryCache = {}

        handle = self.cameraHandler.getCameraHandle(cameraIndex)
        assert handle is not None

        if cameraIndex not in self.__pipelineEntryCache:
            table = getCameraTable(handle)
            pipeline_entryPath = f"{CameraSettingsKeys.kPipeline.value}"
            self.__pipelineEntryCache[cameraIndex] = table.getEntry(pipeline_entryPath)

        self.__pipelineEntryCache[cameraIndex].setInteger(pipelineIndex)
        getCameraTable(handle).getEntry(
            CameraSettingsKeys.kPipelineType.value
        ).setString(
            self.pipelineHandler.pipelineTypeNames[cameraIndex].get(
                pipelineIndex, "unknown"
            )
        )

    def processCamera(self, cameraIndex: CameraID):
        handle: CameraHandle = self.cameraHandler.cameraHandles[cameraIndex]

        try:
            maxFps = float(handle.camera.getMaxFPS())
        except Exception:
            maxFps = 30.0

        self._refreshCameraFpsLimit(cameraIndex, handle)

        try:
            log.info(
                f"Started {getattr(handle, 'name', cameraIndex)} loop (maxFPS={maxFps})"
            )
        except Exception:
            pass

        while self.running.is_set():
            transferredLease = False
            try:
                # CameraHandle's producer owns connection checks and its own
                # bounded retry delay. Checking again here only adds a native
                # call per frame and can discard frames that are already ready.
                ret, frame, captureLatency = handle.grabFrame()
                try:
                    if not ret or frame is None:
                        continue

                    # If we just switched resolution, sometimes the first frame might be bad
                    try:
                        h, w = frame.shape[:2]
                        if h == 0 or w == 0:
                            raise ValueError("bad frame")
                    except Exception:
                        # Try again quickly without going to no-signal
                        time.sleep(0.002)
                        continue

                    transferredLease = self._processAndPublishFrame(
                        cameraIndex, frame, captureLatency
                    )
                finally:
                    if not transferredLease:
                        handle.releaseFrame()
            except Exception:
                time.sleep(0.002)

    def _processAndPublishFrame(
        self, cameraIndex: CameraID, frame: Frame, captureLatency: float = 0.0
    ) -> bool:
        camera_handles = self.cameraHandler.cameraHandles
        handle = camera_handles[cameraIndex]

        now = time.perf_counter()

        # ---- Camera FPS (windowed, bounded by the camera's mode) ----
        # A single frame-to-frame interval can be arbitrarily short after a
        # stall or mode switch, so a 30 FPS camera could report 100+ FPS.
        # Count intervals over a full monotonic window instead and clip to the
        # active mode's rate, which is a hard physical bound.
        limit = self._refreshCameraFpsLimit(cameraIndex, handle)
        meter = self._frameRateMeters.get(cameraIndex)
        if meter is None:
            meter = FrameRateMeter(windowSeconds=FRAME_FPS_WINDOW_SECONDS)
            self._frameRateMeters[cameraIndex] = meter
        cameraFps = meter.record(now, limit=limit)

        # ---- Processing latency ----
        processStart = now

        pipeline_bindings = self.pipelineBindings
        pipeline = self.pipelineHandler.getPipeline(
            pipeline_bindings.get(cameraIndex, -1), cameraIndex
        )
        try:
            frame = self._fixtureFrameForPipeline(cameraIndex, frame, pipeline)
        except Exception:
            pass

        processedFrame = frame
        if pipeline is not None:
            try:
                result = pipeline.processFrame(frame, processStart)
                out = self.handleResults(result, cameraIndex)
                if out is not None:
                    processedFrame = out
            except Exception as e:
                detail = self._pipelineErrorThrottle.exceptionDetail(
                    cameraIndex, e, lambda: "\n" + traceback.format_exc()
                )
                if detail is not None:
                    log.err(
                        f"Pipeline error for camera {getattr(handle, 'name', cameraIndex)}: {detail}"
                    )

        processEnd = time.perf_counter()
        processLatency = processEnd - processStart

        try:
            self.sendLatency(
                cameraIndex,
                captureLatency,
                processLatency,
                cameraFps,
            )
        except Exception:
            pass

        # Only a frame that is still the camera's own buffer can be borrowed.
        # Pipelines that return a derived array must be copied by the publish
        # lane while the original lease is still held by this worker.
        lease = None
        if processedFrame is frame:
            takeLease = getattr(handle, "takeLease", None)
            if takeLease is not None:
                lease = takeLease()

        transferredLease = False
        try:
            transferredLease = self.cameraHandler.publishFrame(
                processedFrame, handle, fps=int(cameraFps), lease=lease
            )
        except Exception:
            pass
        finally:
            if lease is not None and not transferredLease:
                returnLease = getattr(handle, "returnLease", None)
                if returnLease is not None:
                    returnLease(lease)

        try:
            tracker = self._performanceTrackers.get(cameraIndex)
            if tracker is None:
                tracker = self._getPerformanceTracker(cameraIndex)
            totalLatency = captureLatency + (time.perf_counter() - processStart)
            tracker.record(
                captureLatency,
                processLatency,
                totalLatency,
                getattr(processedFrame, "nbytes", 0),
            )
        except Exception:
            pass

        return transferredLease

    def _refreshCameraFpsLimit(
        self, cameraIndex: CameraID, handle: CameraHandle
    ) -> Optional[float]:
        """Return the cached mode bound, refreshing it after a mode change."""
        generation = _cameraModeGeneration(handle)
        if self._cameraFpsLimitGenerations.get(cameraIndex) == generation:
            return self._cameraFpsLimits.get(cameraIndex)

        limit = _cameraFpsLimit(handle)
        self._cameraFpsLimitGenerations[cameraIndex] = generation
        if limit is None:
            self._cameraFpsLimits.pop(cameraIndex, None)
        else:
            self._cameraFpsLimits[cameraIndex] = limit
        return limit

    def _getPerformanceTracker(self, cameraIndex: CameraID) -> CameraPerformanceTracker:
        with self._performanceLock:
            tracker = self._performanceTrackers.get(cameraIndex)
            if tracker is None:
                tracker = CameraPerformanceTracker()
                self._performanceTrackers[cameraIndex] = tracker
            return tracker

    def getPerformanceStats(
        self, cameraIndex: Optional[CameraID] = None
    ) -> Dict[Any, Any]:
        """Return latency/FPS counters for one camera or all cameras.

        Capture and stream counters are merged from their owners so a benchmark
        can report application drops alongside pipeline results.
        """
        indexes: Iterable[CameraID]
        if cameraIndex is None:
            indexes = sorted(self._performanceTrackers)
        else:
            indexes = (cameraIndex,)

        results: Dict[Any, Any] = {}
        for index in indexes:
            stats = self._getPerformanceTracker(index).snapshot()
            handle = self.cameraHandler.getCameraHandle(index)
            if handle is not None and hasattr(handle, "getCaptureStats"):
                capture = handle.getCaptureStats()
                stats["capture_frames"] = capture["captured"]
                stats["dropped_capture_frames"] = capture["dropped"]
                stats["stale_capture_frames"] = capture["stale"]
                stats["free_capture_buffers"] = capture["free"]
                stats["capture_buffer_pool"] = capture["pool"]

            publish = self.cameraHandler.getPublishStats(index)
            stats["dropped_stream_frames"] = publish["dropped"]
            stats["queued_stream_frames"] = publish["queued"]
            stats["failed_stream_frames"] = publish["failed"]
            if cameraIndex is None:
                results[index] = stats
            else:
                return stats
        return results

    def resetPerformanceStats(self, cameraIndex: Optional[CameraID] = None) -> None:
        """Clear measurement windows before a benchmark run."""
        with self._performanceLock:
            if cameraIndex is None:
                for tracker in self._performanceTrackers.values():
                    tracker.reset()
                for meter in self._frameRateMeters.values():
                    meter.reset()
            else:
                tracker = self._performanceTrackers.get(cameraIndex)
                if tracker is not None:
                    tracker.reset()
                meter = self._frameRateMeters.get(cameraIndex)
                if meter is not None:
                    meter.reset()
        if cameraIndex is None:
            for handle in self.cameraHandler.cameraHandles.values():
                if hasattr(handle, "resetCaptureStats"):
                    handle.resetCaptureStats()
            self.cameraHandler.resetPublishStats()
        else:
            handle = self.cameraHandler.getCameraHandle(cameraIndex)
            if handle is not None and hasattr(handle, "resetCaptureStats"):
                handle.resetCaptureStats()
            self.cameraHandler.resetPublishStats(cameraIndex)

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """

        log.info(
            MarkupColors.header(
                "\n" + "=" * 20 + " Synapse Runtime Starting... " + "=" * 20
            )
        )

        # Block until shutdown is requested instead of polling every frame.
        self.stopped.wait()
        log.info("Synapse runtime stopped.")

    def handleResults(
        self, result: PipelineProcessFrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        return self.handleFramePublishing(result, cameraIndex)

    def handleFramePublishing(
        self, result: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        entry = self.cameraFrameEntries.get(cameraIndex)
        if entry is None:
            handle = self.cameraHandler.getCameraHandle(cameraIndex)
            assert handle is not None
            entry = getCameraTable(handle).getEntry(CameraSettingsKeys.kViewID.value)
            if not entry.exists():
                entry.setString(self.DEFAULT_STEP)
            self.cameraFrameEntries[cameraIndex] = entry

            # Read the view id once and keep it in sync through a listener
            # instead of hitting NetworkTables for every published frame.
            self.cameraViewIDs[cameraIndex] = entry.getString(
                defaultValue=self.DEFAULT_STEP
            )

            def onViewIDChanged(event: Event, cameraIndex=cameraIndex) -> None:
                assert isinstance(event.data, ValueEventData)
                self.cameraViewIDs[cameraIndex] = event.data.value.getString()

            self._addNtListener(
                entry,
                EventFlags.VALUE_REMOTE,
                onViewIDChanged,
                key=(cameraIndex, CameraSettingsKeys.kViewID.value, ""),
            )

        if result is None:
            return

        if isinstance(result, Frame):
            if (
                self.cameraViewIDs.get(cameraIndex, self.DEFAULT_STEP)
                == self.DEFAULT_STEP
            ):
                return result

    def sendLatency(
        self,
        cameraIndex: CameraID,
        captureLatency: seconds,
        processingLatency: seconds,
        fps: float,
    ) -> None:
        # Use the monotonic clock for cadence so NTP adjustments cannot stretch
        # or skip latency report intervals.
        current_time = time.monotonic()
        last_report_time = self._lastLatencyReportTime.get(cameraIndex, 0.0)
        if current_time - last_report_time < 1.0:
            return  # Skip sending

        self._lastLatencyReportTime[cameraIndex] = current_time

        for key, value in (
            (NTKeys.kCaptureLatency.value, captureLatency),
            (NTKeys.kProcessLatency.value, processingLatency),
        ):
            pubKey = (cameraIndex, key)
            publisher = self._latencyPubs.get(pubKey)
            if publisher is None:
                handle = self.cameraHandler.getCameraHandle(cameraIndex)
                assert handle is not None
                cameraTable = getCameraTable(handle)
                publisher = cameraTable.getDoubleTopic(key).publish()
                self._latencyPubs[pubKey] = publisher
            publisher.set(value)

        ws = WebSocketServer.kInstance
        if ws is not None and ws.hasClients:

            def buildMessage() -> bytes:
                return createMessage(
                    MessageTypeProto.REPORT_CAMERA_PERFORMANCE,
                    CameraPerformanceProto(
                        latency_capture=secondsToMilliseconds(captureLatency),
                        latency_process=secondsToMilliseconds(processingLatency),
                        fps=int(fps),
                        camera_index=cameraIndex,
                    ),
                )

            ws.sendToAllSync(
                buildMessage, coalesce_key=("camera_performance", cameraIndex)
            )

    def _setupCameraRecordListener(
        self, cameraIndex: CameraID, handle: CameraHandle
    ) -> None:
        entry = getCameraSettingEntry(handle, CameraSettingsKeys.kRecord.value)
        if entry is None:
            return

        def listener(event: Event) -> None:
            value = self.getEventDataValue(event)
            assert isinstance(value, bool)
            self.cameraHandler.setRecordingStatus(cameraIndex, value)

        self._addNtListener(
            entry,
            EventFlags.VALUE_REMOTE,
            listener,
            key=(cameraIndex, CameraSettingsKeys.kRecord.value, ""),
        )

    def _setupCameraPipelineListener(
        self, cameraIndex: CameraID, handle: CameraHandle
    ) -> None:
        entry = getCameraSettingEntry(handle, CameraSettingsKeys.kPipeline.value)

        if entry is None:
            entry = getCameraTable(handle).getEntry(CameraSettingsKeys.kPipeline.value)

        def updateNTPipelineListener(event: Event, cameraIndex: CameraID = cameraIndex):
            assert isinstance(event.data, ValueEventData)

            pipelineIndex = event.data.value.getInteger()

            self.onPipelineChangedFromNT.call(pipelineIndex, cameraIndex)

            self.setPipelineByIndex(
                pipelineIndex=pipelineIndex, cameraIndex=cameraIndex
            )

        self._addNtListener(
            entry,
            EventFlags.VALUE_REMOTE,
            updateNTPipelineListener,
            key=(cameraIndex, CameraSettingsKeys.kPipeline.value, ""),
        )

        entry.setInteger(self.pipelineHandler.defaultPipelineIndexes[cameraIndex])

    def setupNetworkTables(self) -> None:
        for cameraIndex, handle in self.cameraHandler.cameraHandles.items():
            self._setupCameraPipelineListener(cameraIndex, handle)
        for cameraIndex, status in self.cameraHandler.recordingStatus.items():
            handle = self.cameraHandler.getCameraHandle(cameraIndex)
            assert handle is not None

            entry = getCameraSettingEntry(handle, "record")

            assert entry is not None

            entry.setBoolean(status)

    def rotateCameraBySettings(self, settings: CameraSettings, frame: Frame) -> Frame:
        orientation = settings.getSetting(CameraSettings.orientation.key)

        rotations = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE,
        }

        if orientation in rotations:
            frame = cv2.rotate(frame, rotations[orientation])

        return frame

    def fixBlackLevelOffset(self, settings: PipelineSettings, frame: Frame) -> Frame:
        blackLevelOffset = settings.getSetting("black_level_offset")
        if blackLevelOffset is None or blackLevelOffset == 0:
            return frame

        # Normalize to [0,1] and convert to float32
        image = frame.astype(np.float32) / 255.0

        # Apply black level offset (scaled)
        offset = blackLevelOffset / 100.0
        image = np.clip(image + offset, 0, 1)

        # Convert back to uint8
        return (image * 255).astype(np.uint8)

    def fixtureFrame(self, cameraIndex: CameraID, frame: Frame) -> Frame:
        """Public helper for tests and callers that do not already have a pipeline."""
        pipelineIndex = self.pipelineBindings.get(cameraIndex)
        if pipelineIndex is None:
            return frame
        pipeline = self.pipelineHandler.getPipeline(pipelineIndex, cameraIndex)
        return self._fixtureFrameForPipeline(cameraIndex, frame, pipeline)

    def _fixtureFrameForPipeline(
        self, cameraIndex: CameraID, frame: Frame, pipeline: Optional[Any]
    ) -> Frame:
        """Apply cached per-camera settings to a frame without repeat lookups."""
        if pipeline is None:
            return frame
        settings = pipeline.getCameraSettings()
        if settings is None:
            return frame

        orientation = settings.getSetting(CameraSettings.orientation.key)
        rotation = _ROTATIONS.get(orientation)
        if rotation is None:
            self._frameFixtureCache.pop(cameraIndex, None)
            return frame

        height, width = frame.shape[:2]
        shape = (height, width)
        cached = self._frameFixtureCache.get(cameraIndex)
        if (
            cached is not None
            and cached[0] is pipeline
            and cached[1] == orientation
            and cached[2] == shape
        ):
            destination = cached[4]
        else:
            rotatedShape = (
                (width, height, frame.shape[2])
                if rotation != cv2.ROTATE_180
                else frame.shape
            )
            destination = np.empty(rotatedShape, dtype=frame.dtype)
            self._frameFixtureCache[cameraIndex] = (
                pipeline,
                orientation,
                shape,
                rotation,
                destination,
            )

        cv2.rotate(frame, rotation, dst=destination)
        return destination

    def toDict(self) -> Dict:
        return {
            "network": self.networkSettings.toJson(),
            "global": {
                "cameras": [
                    index for index in self.cameraHandler.cameraConfigBindings.keys()
                ]
            },
        }

    def requestSave(self) -> None:
        """Request a debounced save without blocking the caller.

        All requests are coalesced by one background worker. Once the worker is
        stopped, late requests are written synchronously so settings are not
        silently dropped during shutdown.
        """
        stopped = False
        with self._saveLock:
            if self._saveCancelled:
                return
            if self._saveStopped.is_set():
                stopped = True
            else:
                self._savePending = True
                self._saveRequested.set()
                if self._saveThread is None:
                    self._saveThread = threading.Thread(
                        target=self._saveWorker,
                        name="SynapseSave",
                        daemon=True,
                    )
                    self._saveThread.start()

        if stopped:
            self._saveAndReport()

    def save(self) -> None:
        """Schedule a save on the shared debounced save worker."""
        self.requestSave()

    def _saveWorker(self) -> None:
        while True:
            self._saveRequested.wait()
            self._saveRequested.clear()

            with self._saveLock:
                if self._saveStopped.is_set() and not self._savePending:
                    return
                if not self._savePending:
                    continue

            firstRequest = time.monotonic()
            deadline = firstRequest + self._saveDebounceSeconds
            maxDeadline = firstRequest + MAX_SAVE_DELAY_SECONDS

            while True:
                waitFor = max(0.0, min(deadline, maxDeadline) - time.monotonic())
                if waitFor <= 0:
                    break
                if self._saveStopped.wait(waitFor):
                    break
                if self._saveRequested.is_set():
                    self._saveRequested.clear()
                    deadline = min(
                        time.monotonic() + self._saveDebounceSeconds,
                        maxDeadline,
                    )

            with self._saveLock:
                if not self._savePending:
                    continue
                self._savePending = False

            self._saveAndReport()

            if self._saveStopped.is_set():
                with self._saveLock:
                    if not self._savePending:
                        return

    def stopSaveWorker(
        self,
        timeout: float = SAVE_WORKER_TIMEOUT_SECONDS,
        *,
        flush: bool = True,
    ) -> None:
        """Stop the save worker after optionally flushing pending saves.

        Idempotent. ``flush=False`` drops pending writes, which is needed before
        destructive operations such as formatting the config away.
        """
        with self._saveLock:
            thread = self._saveThread
            if thread is None:
                return
            self._saveStopped.set()
            if not flush:
                self._savePending = False
            self._saveRequested.set()

        joinThread(thread, "Save", timeout)

    def cancelPendingSaves(self) -> None:
        """Drop queued saves and prevent later saves from recreating files."""
        with self._saveLock:
            self._saveCancelled = True
        self.stopSaveWorker(flush=False)

    def _saveAndReport(self) -> None:
        try:
            self.saveNow()
        except Exception as error:
            errString = "Failed to save Synapse settings:\n" + "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            if self.onSaveError.callbacks:
                self.onSaveError(error)
            else:
                log.err(errString)

    def saveNow(self) -> None:
        """Perform the actual save. Only the save worker should call this."""
        y = yaml.safe_dump(
            self.toDict(),
            default_flow_style=None,  # use block style by default
            sort_keys=False,  # preserve key order
            indent=2,  # control indentation
            width=80,  # wrap width for long lists
        )
        savefile = Config.getInstance().path
        _atomicWriteText(savefile, y)

        self.savePipelines()
        self.saveCameras()

        log.info(
            MarkupColors.bold(f"Saved into {savefile.absolute().__str__()}"),
            shouldAlert=True,
        )

    def savePipelines(self) -> None:
        cameraSettingsDict: Dict[CameraID, Dict[PipelineID, Dict]] = {}  # TODO
        # Snapshot the outer and inner maps: pipeline switching runs on the
        # command thread while the save worker serializes this configuration.
        for cameraid, pipelinesSet in list(
            self.pipelineHandler.pipelineInstanceBindings.items()
        ):
            cameraSettingsDict[cameraid] = {}
            for pipelineid, pipeline in list(pipelinesSet.items()):
                cameraSettingsDict[cameraid][pipelineid] = pipeline.toDict(
                    (getPipelineTypename(type(pipeline))), cameraid
                )

        for cameraid, data in cameraSettingsDict.items():
            y = yaml.safe_dump(
                {"pipeline_configs": data},
                default_flow_style=None,
                sort_keys=False,
                indent=2,
                width=80,
            )
            savefile = (
                Config.getInstance().path.parent
                / f"camera_{cameraid}"
                / "pipeline_settings.yml"
            )
            _atomicWriteText(savefile, y)

    def saveCameras(self) -> None:
        for cameraid, config in self.cameraHandler.cameraConfigBindings.items():
            savefile = (
                Config.getInstance().path.parent
                / f"camera_{cameraid}"
                / "camera_configs.yml"
            )
            y = yaml.safe_dump(
                {"camera_configs": config.toDict()},
                default_flow_style=None,  # use block style by default
                sort_keys=False,  # preserve key order
                indent=2,  # control indentation
                width=80,  # wrap width for long lists
            )
            _atomicWriteText(savefile, y)

    def requestStop(self) -> None:
        """Ask all runtime worker loops to stop."""
        self.running.clear()
        self.stopped.set()

    def cleanup(self) -> None:
        """Stop worker threads and release cameras, publishers, and listeners.

        Shutdown is ordered as the inverse of startup: workers stop before the
        resources they use are closed. This method is idempotent.
        """
        with self._cleanupLock:
            if self._cleanedUp:
                return
            self._cleanedUp = True

        log.info("Releasing runtime workers and resources...")
        self.requestStop()

        # Stop hotplug scanning first: it creates camera workers and handles,
        # so it must be quiescent before those collections are joined and
        # cleared below.
        self.cameraHandler.stopCameraScanning()

        with self._cleanupLock:
            cameraThreads = list(self.cameraManagementThreads.items())
            self.cameraManagementThreads.clear()
        cameraThreadCount = len(cameraThreads)
        if cameraThreadCount:
            log.info(f"Stopping {cameraThreadCount} camera worker thread(s)...")
        for cameraIndex, thread in cameraThreads:
            joinThread(thread, f"Camera-{cameraIndex}", timeout=2.0)
        if cameraThreadCount:
            log.info("Camera workers stopped.")

        if self.metricsThread is not None:
            log.info("Stopping metrics thread...")
            if joinThread(self.metricsThread, "Metrics", timeout=2.0):
                log.info("Metrics thread stopped.")
        self.metricsThread = None

        listenerCount = len(self._ntListeners)
        if listenerCount:
            log.info(f"Removing {listenerCount} NetworkTables listener(s)...")
        self._removeNtListeners()

        publisherCount = (
            len(self.propPubs)
            + len(self._latencyPubs)
            + (1 if self.versionPublisher is not None else 0)
        )
        if publisherCount:
            log.info(f"Closing {publisherCount} NetworkTables publisher(s)...")
        for key, publisher in self.propPubs.items():
            try:
                publisher.close()
            except Exception as error:
                log.err(f"Failed to close publisher {key}: {error}")
        self.propPubs.clear()
        for key, publisher in self._latencyPubs.items():
            try:
                publisher.close()
            except Exception as error:
                log.err(f"Failed to close latency publisher {key}: {error}")
        self._latencyPubs.clear()
        if self.versionPublisher is not None:
            try:
                self.versionPublisher.close()
            except Exception as error:
                log.err(f"Failed to close version publisher: {error}")
            self.versionPublisher = None

        self.pipelineHandler.cleanup()

        log.info("Releasing camera resources...")
        self.cameraHandler.cleanup()
        self.isSetup = False
        self.setupEvent.clear()

        # Flush any debounced writes after the state they describe is stable.
        self.stopSaveWorker()
        log.info("Runtime resources released.")

    def _addNtListener(
        self,
        entry: NetworkTableEntry,
        flags: int,
        callback: Any,
        *,
        key: Optional[Tuple[CameraID, str, str]] = None,
    ) -> None:
        """Track a NetworkTables listener so it can be removed on shutdown.

        ``key`` makes registration idempotent, which matters because switching
        pipelines re-runs the settings setup for the same camera and topics.
        """
        with self._ntListenerLock:
            if key is not None and key in self._ntListenerKeys:
                return
            listener = NetworkTableInstance.getDefault().addListener(
                entry, flags, callback
            )
            self._ntListeners.append(listener)
            if key is not None:
                self._ntListenerKeys[key] = listener

    def _removeNtListeners(self, cameraID: Optional[CameraID] = None) -> None:
        """Remove runtime NetworkTables listeners, optionally for one camera."""
        instance = NetworkTableInstance.getDefault()
        with self._ntListenerLock:
            if cameraID is None:
                for listener in self._ntListeners:
                    try:
                        instance.removeListener(listener)
                    except Exception as error:
                        log.err(
                            f"Failed to remove NetworkTables listener {listener}: {error}"
                        )
                self._ntListeners.clear()
                self._ntListenerKeys.clear()
                return

            removed = []
            for key, listener in list(self._ntListenerKeys.items()):
                if key[0] != cameraID:
                    continue
                try:
                    instance.removeListener(listener)
                except Exception as error:
                    log.err(
                        f"Failed to remove NetworkTables listener {listener}: {error}"
                    )
                removed.append(listener)
                del self._ntListenerKeys[key]
            self._ntListeners = [
                item for item in self._ntListeners if item not in removed
            ]

    def _closeCameraPublishers(self, cameraID: CameraID) -> None:
        """Release cached publishers/entries bound to a camera's old NT path."""
        for publishers in (self.propPubs, self._latencyPubs):
            for key, publisher in list(publishers.items()):
                if key[0] != cameraID:
                    continue
                try:
                    publisher.close()
                except Exception as error:
                    log.err(f"Failed to close publisher {key}: {error}")
                del publishers[key]

        self.cameraFrameEntries.pop(cameraID, None)
        self.cameraViewIDs.pop(cameraID, None)
        if hasattr(self, "_RuntimeManager__pipelineEntryCache"):
            self.__pipelineEntryCache.pop(cameraID, None)

    def _rebindCameraNt(self, cameraID: CameraID) -> None:
        """Re-register a camera's NT state after it has been renamed."""
        if not self.isSetup:
            return

        handle = self.cameraHandler.getCameraHandle(cameraID)
        if handle is None:
            return

        self._removeNtListeners(cameraID)
        self._closeCameraPublishers(cameraID)
        self._setupCameraRecordListener(cameraID, handle)
        self._setupCameraPipelineListener(cameraID, handle)

        pipelineIndex = self.pipelineBindings.get(
            cameraID, DEFAULT_PIPELINE_FOR_NEW_CAMERA
        )
        self.setPipelineByIndex(cameraID, pipelineIndex)

    def setupCallbacks(self):
        def onRemovePipeline(
            index: PipelineID, pipeline: Pipeline, cameraid: CameraID
        ) -> None:
            """
            Once A pipeline is removed, any camera using it will become
            invalidated and will need to switch to a different pipeline.
            By default, it will switch to it's default pipeline.
            If the removed pipeline *is* the default pipeline,
            it will become invalidated and not process any pipeline
            which may result in undefined behaviour
            """
            matches = [
                cameraid
                for cameraid in self.pipelineBindings.keys()
                if self.pipelineBindings[cameraid] == index
            ]

            for cameraid in matches:
                defaultIndex = self.pipelineHandler.defaultPipelineIndexes[cameraid]
                if defaultIndex != index:
                    self.setPipelineByIndex(cameraid, defaultIndex)
                else:
                    self.setPipelineByIndex(
                        cameraid, self.pipelineHandler.kInvalidPipelineIndex
                    )  # Will result in the camera not processing any pipeline

        def onConnect(_: RemoteConnectionIP) -> None:
            sendWebUIIP()

        def onSetDefaultPipeline(pipelineindex: PipelineID, cameraid: CameraID):
            self.cameraHandler.cameraConfigBindings[
                cameraid
            ].defaultPipeline = pipelineindex

        def onAddCamera(
            cameraIndex: CameraID, name: CameraName, handle: CameraHandle
        ) -> None:
            self._setupCameraRecordListener(cameraIndex, handle)

        def onCameraRenamed(cameraID: CameraID, newName: CameraName) -> None:
            self._rebindCameraNt(cameraID)

        self.cameraHandler.onAddCamera.add(onAddCamera)
        self.cameraHandler.onRenameCamera.add(onCameraRenamed)
        self.pipelineHandler.onRemovePipeline.add(onRemovePipeline)  # pyright: ignore
        self.pipelineHandler.onDefaultPipelineSet.add(onSetDefaultPipeline)

        NtClient.onConnect.add(onConnect)
