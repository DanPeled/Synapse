# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import faulthandler
import threading
import time
import traceback
from asyncio import Queue
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple, TypeAlias

import cv2
import numpy as np
import synapse.log as log
from ntcore import (Event, EventFlags, NetworkTable, NetworkTableEntry,
                    NetworkTableInstance, NetworkTableType, ValueEventData)
from synapse_net.nt_client import NtClient, RemoteConnectionIP
from synapse_net.proto.v1 import (CameraPerformanceProto, HardwareMetricsProto,
                                  MessageTypeProto)
from synapse_net.socketServer import WebSocketServer, createMessage
from wpimath.units import seconds, secondsToMilliseconds

from ..bcolors import MarkupColors
from ..callback import Callback
from ..stypes import CameraID, CameraName, DataValue, Frame, PipelineID
from ..util import Publisher, getIP, getPublisher
from .camera_factory import CameraSettingsKeys, SynapseCamera, getCameraTable
from .camera_handler import CameraHandler
from .config import Config, NetworkConfig, yaml
from .nt_keys import NTKeys
from .pipeline import (FrameResult, Pipeline, PipelineProcessFrameResult,
                       PipelineSettings, getPipelineTypename)
from .pipeline_handler import PipelineHandler
from .settings_api import CameraSettings


@dataclass
class FPSView:
    font = cv2.FONT_HERSHEY_PLAIN
    fontScale = 3
    thickness = 2
    color = (0, 256, 0)
    position = (10, 30)


def sendWebUIIP():
    if NtClient.INSTANCE is not None:
        NtClient.INSTANCE.nt_inst.getTable(NtClient.INSTANCE.NT_TABLE).getEntry(
            "web_ui"
        ).setString(f"https://{getIP()}:3000")


SettingChangedCallback: TypeAlias = Callback[[str, Any, CameraID]]
DEFAULT_PIPELINE_FOR_NEW_CAMERA: Final[PipelineID] = 0


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
        self.propPubs: Dict[Tuple[CameraID, str], Publisher] = {}
        self._lastFrameTime: dict[CameraID, float] = {}
        self.frameQueues: Dict[CameraID, Queue] = {}
        self.cameraManagementThreads: List[threading.Thread] = []

        self.running = threading.Event()
        self.running.set()

        self.isSetup: bool = False
        self.lastLatencyReportTime: float = time.time()

        self.DEFAULT_STEP = "step_0"

        self.metricsThread: Optional[threading.Thread]

        self.networkSettings: NetworkConfig = NetworkConfig(
            name="Synapse",
            teamNumber=0000,
            hostname="synapse",
            ip=None,
            networkInterface=None,
        )

        self.onSettingChanged: SettingChangedCallback = Callback()
        self.onSettingChangedFromNT: SettingChangedCallback = Callback()
        self.onPipelineChangedFromNT: Callback[PipelineID, CameraID] = Callback()
        self.onPipelineChanged: Callback[PipelineID, CameraID] = Callback()

        def onAddCamera(cameraID: CameraID, name: str, camera: SynapseCamera):
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
            thread.start()
            self.cameraManagementThreads.append(thread)

        self.cameraHandler.onAddCamera.add(onAddCamera)
        self.cameraHandler.onAddCamera.add(self.pipelineHandler.onAddCamera)

    def setup(self, directory: Path):
        """
        Initializes all components:
        - Loads pipelines from the directory.
        - Initializes camera configurations.
        - Assigns default pipelines to each camera.
        - Starts metrics collection and monitoring.
        - Registers cleanup routine on exit.

        Args:
            directory (Path): Path to directory containing pipelines and configurations.
        """

        self.setupCallbacks()

        log.log(
            MarkupColors.header(
                "\n" + "=" * 20 + " Loading Pipeline Types & Instances... " + "=" * 20
            )
        )

        self.pipelineHandler.setup(directory)

        log.log(
            MarkupColors.header(
                "\n" + "=" * 20 + " Loading Camera Bindings & Settings... " + "=" * 20
            )
        )

        self.cameraHandler.setup()

        self.assignDefaultPipelines()

        self.setupNetworkTables()

        self.startMetricsThread()
        sendWebUIIP()

        self.isSetup = True

    def assignDefaultPipelines(self) -> None:
        """
        Assigns the default pipeline to each connected camera based on predefined configuration.
        """

        for cameraIndex in self.cameraHandler.cameras:
            pipeline = self.pipelineHandler.getDefaultPipeline(cameraIndex)
            self.setPipelineByIndex(
                cameraIndex=cameraIndex,
                pipelineIndex=pipeline,
            )
            log.log(f"Setup default pipeline (#{pipeline}) for camera ({cameraIndex})")

    def startMetricsThread(self):
        """
        Starts a multiprocessing process and thread to:
        - Collect system metrics from a background process.
        - Publish metrics as a double array to NetworkTables from the main process.
        """

        def metricsWorker() -> None:
            from synapse.hardware.metrics import MetricsManager

            metricsManager: Final[MetricsManager] = MetricsManager()

            # entry = NetworkTableInstance.getDefault().getEntry(
            #     f"{NtClient.NT_TABLE}/{NTKeys.kMetrics.value}"
            # )

            while self.running.is_set():
                cpuTemp = metricsManager.getCpuTemp()
                cpuUsage = metricsManager.getCpuUtilization()
                memory = metricsManager.getMemory()
                uptime = metricsManager.getUptime()
                # gpuMemorySplit = metricsManager.getGPUMemorySplit()
                usedRam = metricsManager.getUsedRam()
                usedDiskPct = metricsManager.getUsedDiskPct()
                # npuUsage = metricsManager.getNpuUsage()

                # metrics = [
                #     cpuTemp,
                #     cpuUsage,
                #     memory,
                #     uptime,
                #     gpuMemorySplit,
                #     usedRam,
                #     usedDiskPct,
                #     npuUsage,
                # ]

                if WebSocketServer.kInstance is not None:
                    metricsMessage = HardwareMetricsProto()
                    metricsMessage.cpu_temp = cpuTemp
                    metricsMessage.cpu_usage = cpuUsage
                    metricsMessage.uptime = uptime
                    metricsMessage.memory = memory
                    metricsMessage.ram_usage = usedRam
                    metricsMessage.disk_usage = usedDiskPct

                    WebSocketServer.kInstance.sendToAllSync(
                        createMessage(
                            MessageTypeProto.SEND_METRICS,
                            metricsMessage,
                        )
                    )

                # entry.setDoubleArray(metrics)

                try:
                    time.sleep(1.4)
                except Exception:
                    continue

        self.metricsThread = threading.Thread(target=metricsWorker, daemon=True)
        log.log("Startig metrics thread")
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

        camera: Optional[SynapseCamera] = self.cameraHandler.getCamera(cameraIndex)

        assert camera is not None

        currPipeline.bind(cameraIndex, camera)

        cameraSettings = currPipeline.getCurrentCameraSettingCollection()

        assert cameraSettings is not None

        cameraTable: NetworkTable = getCameraTable(camera)

        self.cameraHandler.setCameraProps(
            {
                key: cameraSettings.getSetting(key)
                for key in cameraSettings.getMap().keys()
            },
            camera,
        )

        currPipeline.ntTable = cameraTable
        settingsSubtable = cameraTable.getSubTable(NTKeys.kSettings.value)
        pipeline_config.sendSettings(settingsSubtable)

        cameraSettings.sendSettings(settingsSubtable)

        def updateSettingListener(event: Event, cameraIndex=cameraIndex):
            assert isinstance(event.data, ValueEventData)

            prop: str = event.data.topic.getName().split("/")[-1]
            value: Any = self.getEventDataValue(event)
            self.updateSetting(prop, cameraIndex, value)

            self.onSettingChangedFromNT.call(prop, value, cameraIndex)

        def addlistener(key: str) -> None:
            nt_table = getCameraTable(camera)
            if nt_table is not None:
                entry = nt_table.getSubTable(NTKeys.kSettings.value).getEntry(key)

                if NtClient.INSTANCE is not None:
                    NetworkTableInstance.getDefault().addListener(
                        entry, EventFlags.kValueRemote, updateSettingListener
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

        settings = self.pipelineHandler.getPipelineSettings(
            self.pipelineBindings[cameraIndex], cameraIndex
        )
        setting = settings.getAPI().getSetting(prop)
        camera = self.cameraHandler.getCamera(cameraIndex)

        if prop in CameraSettings().getAPI().settings.keys():
            assert camera is not None
            camera.setProperty(prop=prop, value=value)
            pipeline.setCameraSetting(prop, value)
        elif setting is not None:
            settings.setSetting(prop, value)
            pipeline.onSettingChanged(setting, settings.getSetting(prop))
        else:
            log.warn(
                f"Attempted to set setting {prop} on pipeline #{pipeline.pipelineIndex} but it was not found!"
            )
            return

        self.onSettingChanged.call(prop, value, cameraIndex)

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

        self.propPubs[key].set(value)

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

        if topic_type == NetworkTableType.kBoolean:
            return value.getBoolean()
        elif topic_type == NetworkTableType.kFloat:
            return value.getFloat()
        elif topic_type == NetworkTableType.kDouble:
            return value.getDouble()
        elif topic_type == NetworkTableType.kInteger:
            return value.getInteger()
        elif topic_type == NetworkTableType.kString:
            return value.getString()
        elif topic_type == NetworkTableType.kBooleanArray:
            return value.getBooleanArray()
        elif topic_type == NetworkTableType.kFloatArray:
            return value.getFloatArray()
        elif topic_type == NetworkTableType.kDoubleArray:
            return value.getDoubleArray()
        elif topic_type == NetworkTableType.kIntegerArray:
            return value.getIntegerArray()
        elif topic_type == NetworkTableType.kStringArray:
            return value.getStringArray()
        else:
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
        if cameraIndex not in self.cameraHandler.cameras:
            log.err(
                f"Invalid cameraIndex {cameraIndex}. Must be in {list(self.cameraHandler.cameras.keys())})."
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
        self.onPipelineChanged.call(pipelineIndex, cameraIndex)
        log.log(f"Set pipeline #{pipelineIndex} for camera ({cameraIndex})")

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

        if cameraIndex not in self.__pipelineEntryCache:
            table = getCameraTable(self.cameraHandler.getCamera(cameraIndex))
            pipeline_entryPath = f"{CameraSettingsKeys.kPipeline.value}"
            self.__pipelineEntryCache[cameraIndex] = table.getEntry(pipeline_entryPath)

        self.__pipelineEntryCache[cameraIndex].setInteger(pipelineIndex)
        getCameraTable(self.cameraHandler.getCamera(cameraIndex)).getEntry(
            "pipeline_type"
        ).setString(
            self.pipelineHandler.pipelineTypeNames[cameraIndex].get(
                pipelineIndex, "unknown"
            )
        )

    def processCamera(self, cameraIndex: CameraID):
        camera: SynapseCamera = self.cameraHandler.cameras[cameraIndex]

        maxFps = float(camera.getMaxFPS())
        minInterval = 1.0 / maxFps if maxFps > 0 else 0.0

        log.log(f"Started {camera.name} loop (maxFPS={maxFps})")

        while self.running.is_set():
            loopStart = time.perf_counter()

            ret, frame = camera.grabFrame()
            if not ret or frame is None:
                continue

            frame = self.fixtureFrame(cameraIndex, frame)

            self._processAndPublishFrame(cameraIndex, frame)

            # Maintain camera FPS cap
            elapsed = time.perf_counter() - loopStart
            remaining = minInterval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _processAndPublishFrame(self, cameraIndex: CameraID, frame: Frame):
        camera: SynapseCamera = self.cameraHandler.cameras[cameraIndex]

        now = time.perf_counter()

        # ---- Camera FPS (frame-to-frame) ----
        lastTime = self._lastFrameTime.get(cameraIndex)
        if lastTime is not None:
            cameraFps = 1.0 / (now - lastTime)
        else:
            cameraFps = 0.0
        self._lastFrameTime[cameraIndex] = now

        # ---- Processing latency ----
        processStart = time.perf_counter()

        pipeline = self.pipelineHandler.getPipeline(
            self.pipelineBindings.get(cameraIndex, -1), cameraIndex
        )

        processedFrame = frame
        if pipeline is not None:
            try:
                result = pipeline.processFrame(frame, processStart)
                out = self.handleResults(result, cameraIndex)
                if out is not None:
                    processedFrame = out
            except Exception as e:
                log.err(
                    f"Pipeline error for camera {camera.name}: {e}\n{traceback.format_exc()}"
                )

        processLatency = time.perf_counter() - processStart

        cv2.putText(
            processedFrame,
            f"FPS: {int(cameraFps)}",
            FPSView.position,
            FPSView.font,
            FPSView.fontScale,
            FPSView.color,
            FPSView.thickness,
            lineType=cv2.LINE_8,
        )

        self.sendLatency(
            cameraIndex,
            0,
            processLatency,
            cameraFps,
        )

        self.cameraHandler.publishFrame(processedFrame, camera)

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """

        log.log(
            MarkupColors.header(
                "\n" + "=" * 20 + " Synapse Runtime Starting... " + "=" * 20
            )
        )

        while self.running.is_set():
            time.sleep(0.05)

    def handleResults(
        self, result: PipelineProcessFrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        return self.handleFramePublishing(result, cameraIndex)

    def handleFramePublishing(
        self, result: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        if cameraIndex not in self.cameraFrameEntries:
            entry = getCameraTable(self.cameraHandler.getCamera(cameraIndex)).getEntry(
                CameraSettingsKeys.kViewID.value
            )
            if not entry.exists():
                entry.setString(self.DEFAULT_STEP)
            self.cameraFrameEntries[cameraIndex] = entry
        entry = self.cameraFrameEntries[cameraIndex]

        if result is None:
            return

        entry_exists = entry.exists()
        entry_value = (
            entry.getString(defaultValue=self.DEFAULT_STEP)
            if entry_exists
            else self.DEFAULT_STEP
        )

        if isinstance(result, Frame):
            if entry_value == self.DEFAULT_STEP:
                return result

    def sendLatency(
        self,
        cameraIndex: CameraID,
        captureLatency: seconds,
        processingLatency: seconds,
        fps: float,
    ) -> None:
        current_time = time.time()
        if current_time - self.lastLatencyReportTime < 1.0:
            return  # Skip sending

        self.lastLatencyReportTime = current_time

        cameraTable = getCameraTable(self.cameraHandler.getCamera(cameraIndex))
        cameraTable.getEntry(NTKeys.kCaptureLatency.value).setDouble(captureLatency)
        cameraTable.getEntry(NTKeys.kProcessLatency.value).setDouble(processingLatency)

        if WebSocketServer.kInstance is not None:
            WebSocketServer.kInstance.sendToAllSync(
                createMessage(
                    MessageTypeProto.REPORT_CAMERA_PERFORMANCE,
                    CameraPerformanceProto(
                        latency_capture=secondsToMilliseconds(captureLatency),
                        latency_process=secondsToMilliseconds(processingLatency),
                        fps=int(fps),
                        camera_index=cameraIndex,
                    ),
                )
            )

    def setupNetworkTables(self) -> None:
        for cameraIndex, camera in self.cameraHandler.cameras.items():
            entry = camera.getSettingEntry(CameraSettingsKeys.kPipeline.value)

            if entry is None:
                entry = getCameraTable(camera).getEntry(
                    CameraSettingsKeys.kPipeline.value
                )

            def updateNTPipelineListener(event: Event):
                assert isinstance(event.data, ValueEventData)

                pipelineIndex = event.data.value.getInteger()

                self.onPipelineChangedFromNT.call(pipelineIndex, cameraIndex)

                self.setPipelineByIndex(
                    pipelineIndex=pipelineIndex, cameraIndex=cameraIndex
                )

            NetworkTableInstance.getDefault().addListener(
                entry, EventFlags.kValueRemote, updateNTPipelineListener
            )

            entry.setInteger(self.pipelineHandler.defaultPipelineIndexes[cameraIndex])
        for cameraIndex, status in self.cameraHandler.recordingStatus.items():
            camera = self.cameraHandler.getCamera(cameraIndex)
            assert camera is not None

            entry = camera.getSettingEntry("record")

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

        if blackLevelOffset == 0 or blackLevelOffset is None:
            return frame  # No adjustment needed

        blackLevelOffset = -blackLevelOffset / 100

        # Convert to float32 for better precision
        image = frame.astype(np.float32) / 255.0  # Normalize to range [0,1]

        # Apply black level offset: lift only the darkest values
        image = np.power(image + blackLevelOffset, 1.0)  # Apply a soft offset

        # Clip to valid range and convert back to uint8
        return np.clip(image * 255, 0, 255).astype(np.uint8)

    def fixtureFrame(self, cameraIndex: CameraID, frame: Frame) -> Frame:
        if (
            cameraIndex in self.pipelineBindings
            and self.pipelineBindings[cameraIndex]
            in self.pipelineHandler.pipelineInstanceBindings
        ):
            pipeline = self.pipelineHandler.getPipeline(
                self.pipelineBindings[cameraIndex], cameraIndex
            )
            if pipeline is None:
                return frame
            settings: Optional[CameraSettings] = (
                pipeline.getCurrentCameraSettingCollection()
            )
            if settings is not None:
                frame = self.rotateCameraBySettings(settings, frame)

        return frame

    def toDict(self) -> Dict:
        return {
            "network": self.networkSettings.toJson(),
            "global": {
                "cameras": [
                    index for index in self.cameraHandler.cameraConfigBindings.keys()
                ]
            },
        }

    def savePipelines(self) -> None:
        cameraSettingsDict: Dict[CameraID, Dict[PipelineID, Dict]] = {}  # TODO
        for (
            cameraid,
            pipelinesSet,
        ) in self.pipelineHandler.pipelineInstanceBindings.items():
            cameraSettingsDict[cameraid] = {}
            for pipelineid, pipeline in pipelinesSet.items():
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
            savefile.parent.mkdir(parents=True, exist_ok=True)
            with open(savefile, "w") as f:
                f.write(y)

    def save(self) -> None:
        y = yaml.safe_dump(
            self.toDict(),
            default_flow_style=None,  # use block style by default
            sort_keys=False,  # preserve key order
            indent=2,  # control indentation
            width=80,  # wrap width for long lists
        )
        savefile = Config.getInstance().path
        with open(savefile, "w") as f:
            f.write(y)

        self.savePipelines()
        self.saveCameras()

        log.log(
            MarkupColors.bold(f"Saved into {savefile.absolute().__str__()}"),
            shouldAlert=True,
        )

    def saveCameras(self):
        for cameraid, config in self.cameraHandler.cameraConfigBindings.items():
            savefile = (
                Config.getInstance().path.parent
                / f"camera_{cameraid}"
                / "camera_configs.yml"
            )
            with open(savefile, "w") as f:
                y = yaml.safe_dump(
                    {"camera_configs": config.toDict()},
                    default_flow_style=None,  # use block style by default
                    sort_keys=False,  # preserve key order
                    indent=2,  # control indentation
                    width=80,  # wrap width for long lists
                )
                f.write(y)

    def cleanup(self) -> None:
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        self.cameraHandler.cleanup()
        self.running.clear()
        for thread in self.cameraManagementThreads:
            thread.join()
        if self.metricsThread:
            self.metricsThread.join()
        log.log("Cleaned up all resources.")

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
            cameraIndex: CameraID, name: CameraName, camera: SynapseCamera
        ) -> None:
            def listener(event, cameraIndex: CameraID = cameraIndex) -> None:
                value = self.getEventDataValue(event)
                assert isinstance(value, bool)

                self.cameraHandler.setRecordingStatus(cameraIndex, value)

            recordEntry = camera.getSettingEntry(CameraSettingsKeys.kRecord.value)
            assert recordEntry is not None

            NetworkTableInstance.getDefault().addListener(
                recordEntry, EventFlags.kValueRemote, listener
            )

        self.cameraHandler.onAddCamera.add(onAddCamera)
        self.pipelineHandler.onRemovePipeline.add(onRemovePipeline)  # pyright: ignore
        self.pipelineHandler.onDefaultPipelineSet.add(onSetDefaultPipeline)

        NtClient.onConnect.add(onConnect)
