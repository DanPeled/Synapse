import importlib.util
import os
import threading
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple, Type, TypeAlias

import cscore as cs
import cv2
import numpy as np
import synapse.log as log
from ntcore import (
    Event,
    EventFlags,
    NetworkTable,
    NetworkTableInstance,
    NetworkTableType,
)
from synapse_net.nt_client import NtClient
from synapse_net.proto.v1 import HardwareMetricsProto, MessageTypeProto
from synapse_net.socketServer import WebSocketServer, createMessage
from wpilib import Timer
from wpimath.geometry import Transform3d
from wpimath.units import seconds

from ..bcolors import MarkupColors
from ..callback import Callback
from ..stypes import (
    CameraID,
    DataValue,
    Frame,
    PipelineID,
    PipelineName,
    PipelineTypeName,
)
from ..util import resolveGenericArgument
from .camera_factory import (
    CSCORE_TO_CV_PROPS,
    CameraConfig,
    CameraFactory,
    CameraSettingsKeys,
    SynapseCamera,
    getCameraTable,
    getCameraTableName,
)
from .config import Config, yaml
from .global_settings import GlobalSettings
from .pipeline import FrameResult, Pipeline, PipelineSettings
from .settings_api import SettingsMap


class NTKeys(Enum):
    kSettings = "settings"
    kMetrics = "metrics"
    kProcessLatency = "processLatency"
    kCaptureLatency = "captureLatency"


@dataclass
class FPSView:
    font = cv2.FONT_HERSHEY_PLAIN
    fontScale = 3
    thickness = 2
    color = (0, 256, 0)
    position = (10, 30)


class PipelineLoader:
    """Loads, manages, and binds pipeline configurations and instances."""

    kPipelineTypeKey: Final[str] = "type"
    kPipelineNameKey: Final[str] = "name"
    kPipelinesArrayKey: Final[str] = "pipelines"
    kPipelineFilesQuery: Final[str] = "*_pipeline.py"
    kInvalidPipelineIndex: Final[int] = -1

    def __init__(self, pipelineDirectory: Path):
        """Initializes the PipelineLoader with the specified directory.

        Args:
            pipelineDirectory (Path): Path to the directory containing pipeline files.
        """
        self.pipelineTypeNames: Dict[PipelineID, PipelineTypeName] = {}
        self.pipelineSettings: Dict[PipelineID, PipelineSettings] = {}
        self.pipelineInstanceBindings: Dict[PipelineID, Pipeline] = {}
        self.pipelineNames: Dict[PipelineID, PipelineName] = {}

        self.pipelineTypes: Dict[str, Type[Pipeline]] = {}
        self.defaultPipelineIndexes: Dict[CameraID, PipelineID] = {}

        self.pipelineDirectory: Path = pipelineDirectory

        self.onAddPipeline: Callback[PipelineID, Pipeline] = Callback()
        self.onRemovePipeline: Callback[PipelineID, Pipeline] = Callback()
        self.onDefaultPipelineSet: Callback[PipelineID, CameraID] = Callback()

    def setup(self, directory: Path):
        """Initializes the pipeline system by loading pipeline classes and their settings.

        Args:
            directory (Path): The directory containing pipeline implementations.
        """
        self.pipelineDirectory = directory
        self.pipelineTypes = self.loadPipelineTypes(directory)
        self.loadPipelineSettings()
        self.loadPipelineInstances()

    def loadPipelineInstances(self):
        for pipelineIndex in self.pipelineSettings.keys():
            pipelineType = self.getPipelineTypeByIndex(pipelineIndex)
            settings = self.pipelineSettings.get(pipelineIndex)
            settingsMap: Dict = {}
            if settings:
                settingsMap = {
                    key: settings.getAPI().getValue(key)
                    for key in settings.getSchema().keys()
                }
            else:
                settingsMap = {}
            self.addPipeline(
                pipelineIndex,
                self.pipelineNames[pipelineIndex],
                pipelineType.__name__,
                settingsMap,
            )

    def setDefaultPipeline(
        self, cameraIndex: CameraID, pipelineIndex: PipelineID
    ) -> None:
        if pipelineIndex in self.pipelineSettings.keys():
            self.defaultPipelineIndexes[cameraIndex] = pipelineIndex
            log.log(
                f"Default Pipeline set (#{pipelineIndex}) for Camera #{cameraIndex}"
            )
            self.onDefaultPipelineSet.call(pipelineIndex, cameraIndex)
        else:
            log.err(
                f"Default Pipeline attempted to be set (#{pipelineIndex}) for Camera #{cameraIndex} but that pipeline does not exist"
            )

    def removePipeline(self, index: PipelineID) -> Optional[Pipeline]:
        if index in self.pipelineInstanceBindings:
            pipeline = self.pipelineInstanceBindings.pop(index)
            self.pipelineTypeNames.pop(index)
            self.pipelineNames.pop(index)
            self.pipelineSettings.pop(index)

            log.warn(f"Pipeline at index {index} was removed.")

            self.onRemovePipeline.call(index, pipeline)

            return pipeline
        else:
            log.warn(
                f"Attempted to remove pipeline at index {index}, but it was not found."
            )
            return None

    def addPipeline(
        self,
        index: PipelineID,
        name: str,
        typename: str,
        settings: Optional[SettingsMap] = None,
    ):
        pipelineType: Optional[Type[Pipeline]] = self.pipelineTypes.get(typename, None)
        if pipelineType is not None:
            settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
            settingsInst = settingsType(settings)
            currPipeline = pipelineType(settings=settingsInst)
            currPipeline.name = name

            self.pipelineInstanceBindings[index] = currPipeline
            self.pipelineNames[index] = name
            self.pipelineTypeNames[index] = typename
            self.pipelineSettings[index] = settingsInst

            log.log(f"Added Pipeline #{index} with type {typename}")
            self.onAddPipeline.call(index, currPipeline)

    def loadPipelineTypes(self, directory: Path) -> Dict[PipelineName, Type[Pipeline]]:
        """Loads all classes that extend Pipeline from Python files in the directory.

        Args:
            directory (Path): The root directory to search for pipeline implementations.

        Returns:
            Dict[PipelineName, Type[Pipeline]]: A dictionary mapping pipeline names to their types.
        """
        ignoredFiles: Final[list] = ["setup.py"]

        def loadPipelineClasses(directory: Path):
            """Helper function to load pipeline classes from files in a directory.

            Args:
                directory (Path): The directory to search.

            Returns:
                Dict[str, Type[Pipeline]]: Loaded pipeline classes found in the directory.
            """
            pipelineClasses = {}
            for file_path in directory.rglob(PipelineLoader.kPipelineFilesQuery):
                if file_path.name not in ignoredFiles:
                    module_name = file_path.stem

                    try:
                        spec = importlib.util.spec_from_file_location(
                            module_name, str(file_path)
                        )
                        if spec is None or spec.loader is None:
                            continue

                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        for attr in dir(module):
                            cls = getattr(module, attr)
                            if (
                                isinstance(cls, type)
                                and issubclass(cls, Pipeline)
                                and cls is not Pipeline
                            ):
                                if cls.__is_enabled__:
                                    log.log(f"Loaded {cls.__name__} pipeline")
                                    pipelineClasses[cls.__name__] = cls
                    except Exception as e:
                        log.err(
                            f"while loading {file_path}: {e}\n{traceback.format_exc()}"
                        )
            return pipelineClasses

        pipelines = loadPipelineClasses(directory)
        pipelines.update(loadPipelineClasses(Path(__file__).parent.parent))

        log.log("Loaded pipeline classes successfully")
        return pipelines

    def loadPipelineSettings(self) -> None:
        """Loads the pipeline settings from the global configuration.

        Populates default pipelines per camera and creates settings for each pipeline.
        """
        settings: dict = Config.getInstance().getConfigMap()
        camera_configs = GlobalSettings.getCameraConfigMap()

        for cameraIndex in camera_configs:
            self.defaultPipelineIndexes[cameraIndex] = camera_configs[
                cameraIndex
            ].defaultPipeline

        pipelines: dict = settings[self.kPipelinesArrayKey]

        for pipeIndex, _ in enumerate(pipelines):
            pipeline = pipelines[pipeIndex]

            log.log(
                f"Loaded pipeline #{pipeIndex} from disk with type {pipeline[self.kPipelineTypeKey]}"
            )

            self.pipelineTypeNames[pipeIndex] = pipeline[self.kPipelineTypeKey]
            self.pipelineNames[pipeIndex] = pipeline[self.kPipelineNameKey]

            self.createPipelineSettings(
                self.pipelineTypes[self.pipelineTypeNames[pipeIndex]],
                pipeIndex,
                pipeline[NTKeys.kSettings.value],
            )

        log.log("Loaded pipeline settings successfully")

    def createPipelineSettings(
        self,
        pipelineType: Type[Pipeline],
        pipelineIndex: PipelineID,
        settings: SettingsMap,
    ) -> None:
        """Creates and stores the settings object for a given pipeline.

        Args:
            pipelineType (Type[Pipeline]): The class type of the pipeline.
            pipelineIndex (PipelineID): The index associated with this pipeline.
            settings (PipelineSettingsMap): The settings dictionary for the pipeline.
        """
        settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
        self.pipelineSettings[pipelineIndex] = settingsType(settings)

    def getDefaultPipeline(self, cameraIndex: CameraID) -> PipelineID:
        """Returns the default pipeline index for a given camera.

        Args:
            cameraIndex (CameraID): The camera ID.

        Returns:
            PipelineID: The default pipeline index for the camera.
        """
        return self.defaultPipelineIndexes.get(cameraIndex, 0)

    def getPipelineSettings(self, pipelineIndex: PipelineID) -> PipelineSettings:
        """Returns the settings for a given pipeline.

        Args:
            pipelineIndex (PipelineID): The index of the pipeline.

        Returns:
            PipelineSettings: The settings object for the pipeline.
        """
        return self.pipelineSettings[pipelineIndex]

    def getPipeline(self, pipelineIndex: PipelineID) -> Optional[Pipeline]:
        """Returns the pipeline instance bound to a given index, if any.

        Args:
            pipelineIndex (PipelineID): The pipeline index.

        Returns:
            Optional[Pipeline]: The pipeline instance, or None if not bound.
        """
        if pipelineIndex in self.pipelineInstanceBindings:
            return self.pipelineInstanceBindings[pipelineIndex]
        return None

    def setPipelineInstance(
        self, pipelineIndex: PipelineID, pipeline: Pipeline
    ) -> None:
        """Binds a pipeline instance to a given index.

        Args:
            pipelineIndex (PipelineID): The pipeline index.
            pipeline (Pipeline): The pipeline instance to bind.
        """
        self.pipelineInstanceBindings[pipelineIndex] = pipeline

    def getPipelineTypeByName(self, name: PipelineName) -> Type[Pipeline]:
        """Returns the pipeline class type given its name.

        Args:
            name (PipelineName): The name of the pipeline.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.pipelineTypes[name]

    def getPipelineTypeByIndex(self, index: PipelineID) -> Type[Pipeline]:
        """Returns the pipeline class type given its index.

        Args:
            index (PipelineID): The pipeline index.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.getPipelineTypeByName(self.pipelineTypeNames[index])


class CameraHandler:
    """
    Handles the lifecycle and operations of multiple cameras, including initialization,
    streaming, recording, and configuration based on global settings.
    """

    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)
    """Default resolution (width, height) used when no specific stream size is configured."""

    def __init__(self) -> None:
        """
        Initializes empty dictionaries to hold camera instances, output streams,
        stream sizes, recording outputs, and camera configuration bindings.
        """
        self.cameras: Dict[CameraID, SynapseCamera] = {}
        self.usbCameraInfos: Dict[str, cs.UsbCameraInfo] = {}
        self.streamOutputs: Dict[CameraID, cs.CvSource] = {}
        self.streamSizes: Dict[CameraID, Tuple[int, int]] = {}
        self.recordingOutputs: Dict[CameraID, cv2.VideoWriter] = {}
        self.cameraBindings: Dict[CameraID, CameraConfig] = {}
        self.onAddCamera: Callback[CameraID, str, SynapseCamera] = Callback()

    def setup(self) -> None:
        """
        Sets up the camera system by creating cameras, generating output streams,
        and initializing recording outputs.
        """
        self.createCameras()

    def createCameras(self) -> None:
        """
        Retrieves camera configuration from global settings and attempts to add
        each configured camera to the handler.
        """
        self.cameraBindings = GlobalSettings.getCameraConfigMap()
        self.usbCameraInfos = {
            f"{info.name}_{info.productId}": info
            for info in cs.UsbCamera.enumerateUsbCameras()
        }

        found: List[int] = []

        for cameraIndex, cameraConfig in self.cameraBindings.items():
            if len(cameraConfig.id):
                info: Optional[cs.UsbCameraInfo] = self.usbCameraInfos.get(
                    cameraConfig.id, None
                )
                if info is not None:
                    found.append(info.productId)
                    if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                        continue
                else:
                    log.warn(
                        f"No camera found for product id: {cameraConfig.id} (index: {cameraIndex}), camera will be skipped"
                    )
                    continue

        for info in self.usbCameraInfos.values():
            if info.productId not in found:
                log.log(
                    f"Found non-registered camera: {info.name} (i={info.dev}), adding automatically"
                )
                found.append(info.productId)
                newIndex = 0
                if len(self.cameras.keys()) > 0:
                    newIndex = max(self.cameras.keys()) + 1
                cameraIndex = newIndex
                cameraConfig = CameraConfig(
                    name=info.name,
                    id=f"{info.name}_{info.productId}",
                    transform=Transform3d(),
                    defaultPipeline=0,
                    matrix=np.eye(3).tolist(),
                    distCoeff=[0] * 5,
                    measuredRes=(1920, 1080),
                    streamRes=self.DEFAULT_STREAM_SIZE,
                )
                GlobalSettings.setCameraConfig(cameraIndex, cameraConfig)
                if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                    continue

    def getCamera(self, cameraIndex: CameraID) -> Optional[SynapseCamera]:
        """
        Retrieves a specific camera instance by its index.

        Args:
            cameraIndex (CameraID): Index of the camera to retrieve.

        Returns:
            Optional[SynapseCamera]: The camera instance if it exists, otherwise None.
        """
        return self.cameras.get(cameraIndex, None)

    def getStreamRes(self, cameraIndex: CameraID) -> Tuple[int, int]:
        """
        Retrieves the streaming resolution for the given camera index.

        If the camera configuration is available via `GlobalSettings.getCameraConfig(i)`,
        returns its configured stream resolution and updates `self.streamSizes`.
        Otherwise, returns a default resolution.

        Args:
            cameraIndex (CameraID): The index of the camera.

        Returns:
            Tuple[int, int]: The width and height of the stream resolution.
        """
        cameraConfig: Optional[CameraConfig] = GlobalSettings.getCameraConfig(
            cameraIndex
        )

        if cameraConfig is not None:
            streamRes = cameraConfig.streamRes
            self.streamSizes[cameraIndex] = streamRes
            return (streamRes[0], streamRes[1])

        return self.DEFAULT_STREAM_SIZE

    def createStreamOutput(self, cameraIndex: CameraID) -> cs.CvSource:
        """
        Initializes and returns video output streams for all configured cameras.

        For each camera index in `self.cameras`, retrieves its desired streaming resolution
        from the global camera configuration (if available), falls back to the default resolution
        otherwise, and creates a new video stream via `cs.CameraServer.putVideo`.

        Also updates `self.streamSizes` with the resolved stream resolution for each camera.

        Returns:
            dict[CameraID, cs.CameraServer.VideoOutput]: A dictionary mapping camera indices
            to their corresponding video output objects.
        """
        return cs.CameraServer.putVideo(
            f"{NtClient.NT_TABLE}/{getCameraTableName(cameraIndex)}",
            width=self.getStreamRes(cameraIndex)[0],
            height=self.getStreamRes(cameraIndex)[1],
        )

    def createRecordingOutput(self, cameraIndex: CameraID) -> cv2.VideoWriter:
        """
        Creates recording outputs for the specified camera indices if all cameras exist.

        Args:
            cameraIndecies (List[CameraID]): List of camera indices to generate outputs for.

        Returns:
            Dict[CameraID, cv2.VideoWriter]: Mapping from camera ID to the video writer object.
        """
        return cv2.VideoWriter(
            log.LOG_FILE + ".avi",
            cv2.VideoWriter.fourcc("M", "J", "P", "G"),
            30,
            self.cameras[cameraIndex].getResolution(),
        )

    @cache
    def getOutput(self, cameraIndex: CameraID) -> cs.CvSource:
        """
        Retrieves the video output stream for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cs.CvSource: The associated video output stream.
        """
        return self.streamOutputs[cameraIndex]

    @cache
    def getRecordOutput(self, cameraIndex: CameraID) -> cv2.VideoWriter:
        """
        Retrieves the recording output writer for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cv2.VideoWriter: The associated video writer.
        """
        return self.recordingOutputs[cameraIndex]

    def publishFrame(self, frame: Frame, camera: SynapseCamera) -> None:
        """
        Publishes a frame to the output stream and optionally writes it to the recording output
        if recording is enabled.

        Args:
            frame (Frame): The image frame to publish.
            camera (SynapseCamera): The camera that produced the frame.
        """
        if frame is not None:
            resized_frame = cv2.resize(
                frame,
                self.streamSizes[camera.cameraIndex],
                interpolation=cv2.INTER_AREA,
            )
            self.getOutput(camera.cameraIndex).putFrame(resized_frame)
            if camera.getSetting("record", False):
                self.getRecordOutput(camera.cameraIndex).write(frame)

    def addCamera(
        self, cameraIndex: CameraID, cameraConfig: CameraConfig, dev: int
    ) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.

        Args:
            cameraIndex (CameraID): Camera index to open.

        Returns:
            bool: True if the camera was successfully added, False otherwise.
        """

        try:
            camera = CameraFactory.create(
                cameraType=CameraFactory.kCameraServer,
                cameraIndex=cameraIndex,
                path=dev,
                name=f"{cameraConfig.name}(#{cameraIndex})",
            )
            camera.setIndex(cameraIndex)
        except Exception as e:
            log.err(f"Failed to start camera capture: {e}")
            return False

        MAX_RETRIES = 30
        for attempt in range(MAX_RETRIES):
            if camera.isConnected():
                break
            log.log(
                f"Trying to open camera #{cameraIndex} ({cameraConfig.id}), attempt {attempt + 1}"
            )
            time.sleep(1)

        if camera.isConnected():
            self.cameras[cameraIndex] = camera
            self.recordingOutputs[cameraIndex] = self.createRecordingOutput(cameraIndex)
            self.streamOutputs[cameraIndex] = self.createStreamOutput(cameraIndex)

            self.onAddCamera.call(cameraIndex, cameraConfig.name, camera)

            log.log(
                f"Camera (name={cameraConfig.name}, id={cameraConfig.id}, id={cameraIndex}) added successfully."
            )
            return True

        log.err(
            f"Failed to open camera #{cameraIndex} ({cameraConfig.id}) after {MAX_RETRIES} retries."
        )
        return False

    def setCameraProps(
        self, settings: Dict[str, Any], camera: SynapseCamera
    ) -> Dict[str, Any]:
        """
        Applies the specified settings to a camera and sets its video mode.

        Args:
            settings (Dict[str, Any]): Dictionary of property names and values to apply.
            camera (SynapseCamera): The camera to configure.

        Returns:
            Dict[str, Any]: Dictionary of updated settings (currently unused).
        """
        updated_settings = {}
        for settingName in settings.keys():
            if settingName in CSCORE_TO_CV_PROPS.keys():
                setting_value = settings.get(settingName)
                if setting_value is not None:
                    camera.setProperty(
                        prop=settingName,
                        value=setting_value,
                    )

        if {"width", "height"}.issubset(settings):
            camera.setVideoMode(
                width=int(settings["width"]),
                height=int(settings["height"]),
                fps=1000,
            )

        return updated_settings

    def cleanup(self) -> None:
        """
        Releases all video writers and closes all active camera connections.
        """
        for record in self.recordingOutputs.values():
            record.release()
        for camera in self.cameras.values():
            camera.close()


SettingChangedCallback: TypeAlias = Callback[[str, Any, CameraID]]


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

        self.pipelineLoader: PipelineLoader = PipelineLoader(directory)
        self.cameraHandler: CameraHandler = CameraHandler()
        self.pipelineBindings: Dict[CameraID, PipelineID] = {}
        self.cameraManagementThreads: List[threading.Thread] = []
        self.isRunning: bool = True
        self.onSettingChanged: SettingChangedCallback = Callback()
        self.onSettingChangedFromNT: SettingChangedCallback = Callback()
        self.onPipelineChangedFromNT: Callback[PipelineID, CameraID] = Callback()
        self.onPipelineChanged: Callback[PipelineID, CameraID] = Callback()
        self.isSetup: bool = False

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

        import atexit

        log.log(
            MarkupColors.header(
                "\n" + "=" * 20 + " Loading Pipelines & Camera Configs... " + "=" * 20
            )
        )

        self.setupCallbacks()

        self.cameraHandler.setup()
        self.pipelineLoader.setup(directory)
        self.assignDefaultPipelines()

        self.setupNetworkTables()

        self.startMetricsThread()

        self.isSetup = True

        atexit.register(self.cleanup)

    def assignDefaultPipelines(self) -> None:
        """
        Assigns the default pipeline to each connected camera based on predefined configuration.
        """

        for cameraIndex in self.cameraHandler.cameras.keys():
            pipeline = self.pipelineLoader.getDefaultPipeline(cameraIndex)
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

            entry = NetworkTableInstance.getDefault().getEntry(
                f"{NtClient.NT_TABLE}/{NTKeys.kMetrics.value}"
            )

            while self.isRunning:
                cpuTemp = metricsManager.getCpuTemp()
                cpuUsage = metricsManager.getCpuUtilization()
                memory = metricsManager.getMemory()
                uptime = metricsManager.getUptime()
                gpuMemorySplit = metricsManager.getGPUMemorySplit()
                usedRam = metricsManager.getUsedRam()
                usedDiskPct = metricsManager.getUsedDiskPct()
                npuUsage = metricsManager.getNpuUsage()

                metrics = [
                    cpuTemp,
                    cpuUsage,
                    memory,
                    uptime,
                    gpuMemorySplit,
                    usedRam,
                    usedDiskPct,
                    npuUsage,
                ]

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

                entry.setDoubleArray(metrics)

                try:
                    time.sleep(1)
                except Exception:
                    continue

        self.metricsThread = threading.Thread(target=metricsWorker, daemon=True)
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
        currPipeline = self.pipelineLoader.getPipeline(
            self.pipelineBindings[cameraIndex]
        )

        if currPipeline is None:
            log.err(f"No pipeline with index: {self.pipelineBindings[cameraIndex]}")
            return

        currPipeline.bind(cameraIndex)
        cameraTable: Optional[NetworkTable] = getCameraTable(cameraIndex)
        camera: Optional[SynapseCamera] = self.cameraHandler.getCamera(cameraIndex)
        if camera is not None:
            self.cameraHandler.setCameraProps(
                {
                    key: pipeline_config.getSetting(key)
                    for key in pipeline_config.getMap().keys()
                },
                camera,
            )

        if cameraTable is not None:
            setattr(currPipeline, "nt_table", cameraTable)
            setattr(currPipeline, "builder_cache", {})
            pipeline_config.sendSettings(
                cameraTable.getSubTable(NTKeys.kSettings.value)
            )

            def updateSettingListener(event: Event, cameraIndex=cameraIndex):
                prop: str = event.data.topic.getName().split("/")[-1]  # pyright: ignore
                value: Any = self.getEventDataValue(event)
                self.updateSetting(prop, cameraIndex, value)

                self.onSettingChangedFromNT.call(prop, value, cameraIndex)

            for key in pipeline_config.getMap().keys():
                nt_table = getCameraTable(cameraIndex)
                if nt_table is not None:
                    entry = nt_table.getSubTable(NTKeys.kSettings.value).getEntry(key)

                    if NtClient.INSTANCE is not None:
                        NetworkTableInstance.getDefault().addListener(
                            entry, EventFlags.kValueRemote, updateSettingListener
                        )

    def updateSetting(self, prop: str, cameraIndex: CameraID, value: Any) -> None:
        self.pipelineLoader.getPipelineSettings(
            self.pipelineBindings[cameraIndex]
        ).setSetting(prop, value)

        if prop in CSCORE_TO_CV_PROPS.keys():
            camera = self.cameraHandler.getCamera(cameraIndex)
            if camera is not None:
                camera.setProperty(
                    prop=prop,
                    value=int(value),
                )

        self.onSettingChanged.call(prop, value, cameraIndex)

        nt_table = getCameraTable(cameraIndex)
        entry = nt_table.getSubTable(NTKeys.kSettings.value).getEntry(prop)
        if entry is not None and entry.getValue() != value:
            entry.setValue(value)

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
        topic = event.data.topic  # pyright: ignore
        topic_type = topic.getType()
        value = event.data.value  # pyright: ignore

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
        if cameraIndex not in self.cameraHandler.cameras.keys():
            log.err(
                f"Invalid cameraIndex {cameraIndex}. Must be in {list(self.cameraHandler.cameras.keys())})."
            )
            return

        if pipelineIndex not in self.pipelineLoader.pipelineTypeNames.keys():
            log.err(
                f"Invalid pipeline index {pipelineIndex}. Must be one of {list(self.pipelineLoader.pipelineTypeNames.keys())}."
            )
            self.setNTPipelineIndex(cameraIndex, self.pipelineBindings[cameraIndex])
            return

        for cameraId, pipelineId in self.pipelineBindings.items():
            if cameraId != cameraIndex and pipelineId == pipelineIndex:
                log.err(
                    f"Another camera is using this pipeline at the moment (camera=#{cameraId})"
                )
                return

        # If both indices are valid, proceed with the pipeline setting
        self.pipelineBindings[cameraIndex] = pipelineIndex

        self.setNTPipelineIndex(cameraIndex=cameraIndex, pipelineIndex=pipelineIndex)

        settings = self.pipelineLoader.getPipelineSettings(pipelineIndex)

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
            table = getCameraTable(cameraIndex)
            pipeline_entryPath = f"{CameraSettingsKeys.kPipeline.value}"
            self.__pipelineEntryCache[cameraIndex] = table.getEntry(pipeline_entryPath)

        self.__pipelineEntryCache[cameraIndex].setInteger(pipelineIndex)

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """

        def processCamera(cameraIndex: CameraID):
            camera: SynapseCamera = self.cameraHandler.cameras[cameraIndex]

            log.log(f"Started Camera #{cameraIndex} loop")

            while self.isRunning:
                maxFps = camera.getMaxFPS()
                frame_time = 1.0 / float(maxFps)
                loop_start = Timer.getFPGATimestamp()

                ret, frame = camera.grabFrame()
                captureLatency = Timer.getFPGATimestamp() - loop_start
                if not ret or frame is None:
                    continue

                frame = self.fixtureFrame(cameraIndex, frame)

                process_start = Timer.getFPGATimestamp()
                pipeline = self.pipelineLoader.getPipeline(
                    self.pipelineBindings[cameraIndex]
                )

                processed_frame: Frame = frame

                if pipeline is not None:
                    result = pipeline.processFrame(frame, loop_start)
                    frame = self.handleResults(result, cameraIndex)
                    if frame is not None:
                        processed_frame = frame

                processLatency = Timer.getFPGATimestamp() - process_start
                total_time = Timer.getFPGATimestamp() - loop_start
                fps = 1.0 / total_time if total_time > 0 else 0
                self.sendLatency(cameraIndex, captureLatency, processLatency)

                # Sleep to enforce max FPS
                elapsed = Timer.getFPGATimestamp() - loop_start
                remaining = frame_time - elapsed
                if remaining > 0:
                    time.sleep(remaining)
                loop_end = Timer.getFPGATimestamp()
                total_loop_time = loop_end - loop_start

                fps = 1.0 / total_loop_time if total_loop_time > 0 else 0

                # Overlay FPS on the frame
                cv2.putText(
                    processed_frame,
                    f"{int(fps)}",
                    FPSView.position,
                    FPSView.font,
                    FPSView.fontScale,
                    FPSView.color,
                    FPSView.thickness,
                    lineType=cv2.LINE_8,
                )

                self.cameraHandler.publishFrame(processed_frame, camera)

        def initThreads():
            for cameraIndex in self.cameraHandler.cameras.keys():
                thread = threading.Thread(target=processCamera, args=(cameraIndex,))
                thread.daemon = True
                thread.start()
                self.cameraManagementThreads.append(thread)

        initThreads()

        log.log(
            MarkupColors.header(
                "\n" + "=" * 20 + " Synapse Runtime Starting... " + "=" * 20
            )
        )

        while self.isRunning:
            if NtClient.INSTANCE:
                NtClient.INSTANCE.nt_inst.flush()
                if NtClient.INSTANCE.server:
                    NtClient.INSTANCE.server.flush()
            try:
                time.sleep(0.05)
            except Exception:
                continue

    def handleResults(
        self, frames: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        if frames is not None:
            return self.handleFramePublishing(frames, cameraIndex)

    def handleFramePublishing(
        self, result: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        entry = getCameraTable(cameraIndex).getEntry(CameraSettingsKeys.kViewID.value)
        DEFAULT_STEP = "step_0"

        if result is None:
            return

        entry_exists = entry.exists()
        entry_value = (
            entry.getString(defaultValue=DEFAULT_STEP) if entry_exists else DEFAULT_STEP
        )

        if not entry_exists:
            entry.setString(DEFAULT_STEP)

        if isinstance(result, Frame):
            if entry_value == DEFAULT_STEP:
                return result
        else:
            for i, var in enumerate(result):
                if entry_value == f"step_{i}":
                    return var

    def sendLatency(
        self, cameraIndex: CameraID, captureLatency: seconds, processingLatency: seconds
    ) -> None:
        cameraTable = getCameraTable(cameraIndex)
        cameraTable.getEntry(NTKeys.kCaptureLatency.value).setDouble(captureLatency)
        cameraTable.getEntry(NTKeys.kProcessLatency.value).setDouble(processingLatency)

    def setupNetworkTables(self) -> None:
        for cameraIndex, camera in self.cameraHandler.cameras.items():
            entry = camera.getSettingEntry(CameraSettingsKeys.kPipeline.value)

            if entry is None:
                entry = getCameraTable(cameraIndex=cameraIndex).getEntry(
                    CameraSettingsKeys.kPipeline.value
                )

            def updateNTPipelineListener(event: Event):
                pipelineIndex = event.data.value.getInteger()  # pyright: ignore

                self.onPipelineChangedFromNT.call(pipelineIndex, cameraIndex)

                self.setPipelineByIndex(
                    pipelineIndex=pipelineIndex, cameraIndex=cameraIndex
                )

            NetworkTableInstance.getDefault().addListener(
                entry, EventFlags.kValueRemote, updateNTPipelineListener
            )

            entry.setInteger(self.pipelineLoader.defaultPipelineIndexes[cameraIndex])

    def rotateCameraBySettings(self, settings: PipelineSettings, frame: Frame) -> Frame:
        orientation = settings.getSetting(PipelineSettings.orientation.key)

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
        settings = self.pipelineLoader.pipelineSettings[
            self.pipelineBindings[cameraIndex]
        ]
        frame = self.rotateCameraBySettings(settings, frame)
        # frame = self.fixBlackLevelOffset(settings, frame)

        return frame

    def toDict(self) -> Dict:
        return {
            "global": {
                "camera_configs": {
                    index: config.toDict()
                    for index, config in GlobalSettings.getCameraConfigMap().items()
                }
            },
            "pipelines": {
                key: pipeline.toDict(self.pipelineLoader.pipelineTypeNames[key])
                for key, pipeline in (
                    self.pipelineLoader.pipelineInstanceBindings.items()
                )
            },
        }

    def save(self) -> None:
        y = yaml.safe_dump(
            self.toDict(),
            default_flow_style=None,  # use block style by default
            sort_keys=False,  # preserve key order
            indent=2,  # control indentation
            width=80,  # wrap width for long lists
        )

        with open(Path(os.getcwd()) / "config" / "settings.yml", "w") as f:
            f.write(y)

    def cleanup(self) -> None:
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        self.cameraHandler.cleanup()
        self.isRunning = False
        log.log("Cleaned up all resources.")

    def setupCallbacks(self):
        def onRemovePipeline(index: PipelineID, pipeline: Pipeline) -> None:
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
                defaultIndex = self.pipelineLoader.defaultPipelineIndexes[cameraid]
                if defaultIndex != index:
                    self.setPipelineByIndex(cameraid, defaultIndex)
                else:
                    self.setPipelineByIndex(
                        cameraid, self.pipelineLoader.kInvalidPipelineIndex
                    )  # Will result in the camera not processing any pipeline

        self.pipelineLoader.onRemovePipeline.add(onRemovePipeline)
