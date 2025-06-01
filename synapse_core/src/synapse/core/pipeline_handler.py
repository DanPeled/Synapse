import importlib.util
import threading
import time
import traceback
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple, Type

import cscore as cs
import cv2
import numpy as np
import synapse.log as log
from ntcore import (Event, EventFlags, NetworkTable, NetworkTableInstance,
                    NetworkTableType)
from synapse.bcolors import bcolors
from synapse.stypes import DataValue, Frame
from synapse_net.nt_client import NtClient
from wpilib import Timer
from wpimath.units import seconds

from .camera_factory import (CSCORE_TO_CV_PROPS, CameraFactory,
                             CameraSettingsKeys, SynapseCamera, getCameraTable,
                             getCameraTableName)
from .config import Config
from .pipeline import (CameraConfig, FrameResult, GlobalSettings, Pipeline,
                       PipelineSettings)
from .settings_api import PipelineSettingsMap

CameraID = int
PipelineID = int
PipelineName = str


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
    color = (0, 0, 0)
    position = (10, 30)


def resolveGenericArgument(cls):
    orig_bases = getattr(cls, "__orig_bases__", ())
    for base in orig_bases:
        if typing.get_origin(base) is Pipeline:
            args = typing.get_args(base)
            if args:
                return args[0]
    return None


class PipelineLoader:
    def __init__(self, pipelineDirectory: Path):
        self.pipelineTypeNames: Dict[PipelineID, PipelineName] = {}
        self.pipelineSettings: Dict[PipelineID, PipelineSettings] = {}
        self.pipelineTypes: Dict[str, Type[Pipeline]] = {}
        self.defaultPipelineIndexes: Dict[CameraID, PipelineID] = {}
        self.pipelineInstanceBindings: Dict[PipelineID, Pipeline] = {}
        self.pipelineDirectory: Path = pipelineDirectory

    def setup(self, directory: Path):
        self.pipelineTypes = self.loadPipelines(directory)
        self.loadPipelineSettings()

    def loadPipelines(self, directory: Path) -> Dict[PipelineName, Type[Pipeline]]:
        """
        Loads all classes that extend Pipeline from Python files in the directory.
        :return: A dictionary of Pipeline subclasses
        """

        ignoredFiles: Final[list] = ["setup.py"]

        def loadPipelineClasses(directory: Path):
            pipelineClasses = {}
            for file_path in directory.rglob("*_pipeline.py"):
                if file_path.name not in ignoredFiles:
                    module_name = file_path.stem  # Get filename without extension

                    try:
                        # Load module directly from file path
                        spec = importlib.util.spec_from_file_location(
                            module_name, str(file_path)
                        )
                        if spec is None or spec.loader is None:
                            continue

                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Look for Pipeline subclasses in the loaded module
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
                        log.err(f"while loading {file_path}: {e}")
                        traceback.print_exc()
            return pipelineClasses

        pipelines = loadPipelineClasses(directory)
        pipelines.update(loadPipelineClasses(Path(__file__).parent.parent))

        log.log("Loaded pipeline classes successfully")
        return pipelines

    def loadPipelineSettings(self) -> None:
        settings: dict = Config.getInstance().getConfigMap()
        camera_configs = GlobalSettings.getCameraConfigMap()

        for cameraIndex in camera_configs:
            self.defaultPipelineIndexes[cameraIndex] = camera_configs[
                cameraIndex
            ].defaultPipeline

        pipelines: dict = settings["pipelines"]

        for pipeIndex, _ in enumerate(pipelines):
            pipeline = pipelines[pipeIndex]

            log.log(f"Loaded pipeline #{pipeIndex} with type {pipeline['type']}")

            self.pipelineTypeNames[pipeIndex] = pipeline["type"]

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
        settings: PipelineSettingsMap,
    ) -> None:
        settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
        self.pipelineSettings[pipelineIndex] = settingsType(settings)

    def getDefaultPipeline(self, cameraIndex: CameraID) -> PipelineID:
        return self.defaultPipelineIndexes.get(cameraIndex, 0)

    def getPipelineSettings(self, pipelineIndex: PipelineID) -> PipelineSettings:
        return self.pipelineSettings[pipelineIndex]

    def getPipeline(self, pipelineIndex: PipelineID) -> Pipeline:
        return self.pipelineInstanceBindings[pipelineIndex]

    def setPipelineInstance(
        self, pipelineIndex: PipelineID, pipeline: Pipeline
    ) -> None:
        self.pipelineInstanceBindings[pipelineIndex] = pipeline

    def getPipelineTypeByName(self, name: PipelineName) -> Type[Pipeline]:
        return self.pipelineTypes[name]

    def getPipelineTypeByIndex(self, index: PipelineID) -> Type[Pipeline]:
        return self.getPipelineTypeByName(self.pipelineTypeNames[index])


class PipelineHandler:
    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)

    def __init__(self, directory: Path):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param pipelineDirectory: Root directory to search for pipeline files
        """
        self.pipelineLoader: PipelineLoader = PipelineLoader(directory)
        self.cameras: Dict[CameraID, SynapseCamera] = {}
        self.pipelineBindings: Dict[CameraID, PipelineID] = {}
        self.streamSizes: Dict[CameraID, Tuple[int, int]] = {}
        self.outputs: Dict[CameraID, cs.CvSource] = {}
        self.recordingOutputs: Dict[CameraID, cv2.VideoWriter] = {}
        self.cameraBindings: Dict[CameraID, CameraConfig] = {}

    def setup(self, directory: Path):
        import atexit

        log.log(
            bcolors.OKGREEN
            + bcolors.BOLD
            + "\n"
            + "=" * 20
            + " Loading Pipelines & Camera Configs... "
            + "=" * 20
            + bcolors.ENDC
            + "\n"
        )

        self.pipelineLoader.setup(directory)

        self.createCameras()
        self.assignDefaultPipelines()

        self.setupNetworkTables()

        self.startMetricsThread()

        atexit.register(self.cleanup)

    def assignDefaultPipelines(self) -> None:
        for cameraIndex in self.cameras.keys():
            pipeline = self.pipelineLoader.getDefaultPipeline(cameraIndex)
            self.setPipelineByIndex(
                cameraIndex=cameraIndex,
                pipelineIndex=pipeline,
            )
            log.log(f"Setup default pipeline (#{pipeline}) for camera ({cameraIndex})")

    def createCameras(self) -> None:
        self.cameraBindings = GlobalSettings.getCameraConfigMap()

        for cameraIndex in self.cameraBindings:
            if not (self.addCamera(cameraIndex)):
                continue

    def startMetricsThread(self):
        from multiprocessing import Process, Queue

        """
        Starts a separate process that collects system metrics,
        then publishes them to NetworkTables from the main process as double array.
        """

        def metricsProcess(queue: Queue):
            from synapse.hardware import MetricsManager

            metricsManager: Final[MetricsManager] = MetricsManager()
            metricsManager.setConfig(None)  # Pass config if you have one

            while True:
                metrics_str: List[str] = [
                    metricsManager.getTemp(),
                    metricsManager.getUtilization(),
                    metricsManager.getMemory(),
                    metricsManager.getThrottleReason(),
                    metricsManager.getUptime(),
                    metricsManager.getGPUMemorySplit(),
                    metricsManager.getUsedRam(),
                    metricsManager.getMallocedMemory(),
                    metricsManager.getUsedDiskPct(),
                    metricsManager.getNpuUsage(),
                ]

                # Convert strings to floats safely
                metrics = []
                for s in metrics_str:
                    try:
                        metrics.append(float(s))
                    except (ValueError, TypeError):
                        metrics.append(0.0)

                queue.put(metrics)
                time.sleep(1)

        def publishLoop(queue: Queue):
            entry = NetworkTableInstance.getDefault().getEntry(
                f"{NtClient.NT_TABLE}/{NTKeys.kMetrics.value}"
            )
            while True:
                try:
                    metrics = queue.get(timeout=2)
                    entry.setDoubleArray(metrics)
                except Exception:
                    continue
                time.sleep(1)

        metricsQueue = Queue()

        p = Process(target=metricsProcess, args=(metricsQueue,), daemon=True)
        p.start()

        publisher_thread = threading.Thread(
            target=publishLoop, args=(metricsQueue,), daemon=True
        )
        publisher_thread.start()

    def generateRecordingOutputs(
        self, cameraIndecies: List[int]
    ) -> Dict[int, cv2.VideoWriter]:
        finalDict: Dict[int, cv2.VideoWriter] = {
            index: cv2.VideoWriter(
                log.LOG_FILE + ".avi",
                cv2.VideoWriter.fourcc("M", "J", "P", "G"),
                30,
                self.cameras[index].getResolution(),
            )
            for index in cameraIndecies
        }
        return finalDict

    def addCamera(self, cameraIndex: CameraID) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.
        :param cameraIndex: Camera index to open
        """
        camera_config = self.cameraBindings.get(cameraIndex)
        if camera_config is None:
            log.err(f"No camera defined for index {cameraIndex}")
            return False

        path = camera_config.path

        try:
            camera = CameraFactory.create(
                cameraType=CameraFactory.kCameraServer,
                cameraIndex=cameraIndex,
                devPath=path,
                name=f"{camera_config.name}(#{cameraIndex})",
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
                f"Trying to open camera #{cameraIndex} ({path}), attempt {attempt + 1}"
            )
            time.sleep(1)

        if camera.isConnected():
            self.cameras[cameraIndex] = camera
            log.log(
                f"Camera (name={camera_config.name}, path={camera_config.path}, id={cameraIndex}) added successfully."
            )
            return True

        log.err(
            f"Failed to open camera #{cameraIndex} ({path}) after {MAX_RETRIES} retries."
        )
        return False

    def __setupPipelineForCamera(
        self,
        cameraIndex: CameraID,
        pipelineType: Type[Pipeline],
        pipeline_config: PipelineSettings,
    ):
        """
        Sets the pipeline(s) to be used for a specific camera.
        :param cameraIndex: Index of the camera
        :param pipeline: A pipeline class or list of pipeline classes to assign to the camera
        """
        # Create instances for each pipeline only when setting them
        settings = self.pipelineLoader.getPipelineSettings(
            self.pipelineBindings[cameraIndex]
        )

        currPipeline = pipelineType(settings=settings, cameraIndex=cameraIndex)

        self.pipelineLoader.setPipelineInstance(
            self.pipelineBindings[cameraIndex], currPipeline
        )

        cameraTable: Optional[NetworkTable] = getCameraTable(cameraIndex)
        self.setCameraConfigs(
            {
                key: pipeline_config.getSetting(key)
                for key in pipeline_config.getMap().keys()
            },
            self.cameras[cameraIndex],
        )

        if cameraTable is not None:
            setattr(currPipeline, "nt_table", cameraTable)
            setattr(currPipeline, "builder_cache", {})
            currPipeline.setup()
            pipeline_config.sendSettings(
                cameraTable.getSubTable(NTKeys.kSettings.value)
            )

            def updateSettingListener(event: Event, cameraIndex=cameraIndex):
                prop: str = event.data.topic.getName().split("/")[-1]  # pyright: ignore
                value: Any = self.getEventDataValue(event)
                self.pipelineLoader.getPipelineSettings(
                    self.pipelineBindings[cameraIndex]
                ).setSetting(prop, value)

                if prop in CSCORE_TO_CV_PROPS.keys():
                    self.cameras[cameraIndex].setProperty(
                        prop=prop,
                        value=int(value),
                    )

            for key in pipeline_config.getMap().keys():
                nt_table = getCameraTable(cameraIndex)
                if nt_table is not None:
                    entry = nt_table.getSubTable(NTKeys.kSettings.value).getEntry(key)

                    if NtClient.INSTANCE is not None:
                        NetworkTableInstance.getDefault().addListener(
                            entry, EventFlags.kValueRemote, updateSettingListener
                        )

    @staticmethod
    def getEventDataValue(
        event: Event,
    ) -> DataValue:
        """
        Extracts the correctly typed value from a NetworkTables event based on its topic type.

        Args:
            event (Event): The NetworkTables event containing the topic and value.

        Returns:
            Any: The value interpreted according to its NetworkTableType.

        Raises:
            ValueError: If the topic type is unsupported.
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
        if cameraIndex not in self.cameras.keys():
            log.err(
                f"Invalid cameraIndex {cameraIndex}. Must be in range(0, {len(self.cameras.keys())-1})."
            )
            return

        if pipelineIndex not in self.pipelineLoader.pipelineTypeNames.keys():
            log.err(
                f"Invalid pipeline index {pipelineIndex}. Must be one of {list(self.pipelineLoader.pipelineTypeNames.keys())}."
            )
            self.setNTPipelineIndex(cameraIndex, self.pipelineBindings[cameraIndex])
            return

        # If both indices are valid, proceed with the pipeline setting
        self.pipelineBindings[cameraIndex] = pipelineIndex

        self.setNTPipelineIndex(cameraIndex=cameraIndex, pipelineIndex=pipelineIndex)

        settings = self.pipelineLoader.getPipelineSettings(pipelineIndex)

        self.__setupPipelineForCamera(
            cameraIndex=cameraIndex,
            pipelineType=self.pipelineLoader.getPipelineTypeByIndex(pipelineIndex),
            pipeline_config=settings,
        )

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
            table = NetworkTableInstance.getDefault().getTable(NtClient.NT_TABLE)
            entry_path = f"{getCameraTableName(cameraIndex)}/{CameraSettingsKeys.kPipeline.value}"
            self.__pipelineEntryCache[cameraIndex] = table.getEntry(entry_path)

        self.__pipelineEntryCache[cameraIndex].setInteger(pipelineIndex)

    def getCameraOutputs(self) -> Dict[CameraID, cs.CvSource]:
        """
        Initializes and returns video output streams for all configured cameras.

        For each camera index in `self.cameras`, retrieves its desired streaming resolution
        from the global camera configuration (if available), falls back to the default resolution
        otherwise, and creates a new video stream via `cs.CameraServer.putVideo`.

        Also updates `self.streamSizes` with the resolved stream resolution for each camera.

        Returns:
            dict[int, cs.CameraServer.VideoOutput]: A dictionary mapping camera indices
            to their corresponding video output objects.
        """

        def getStreamRes(cameraIndex: CameraID) -> Tuple[int, int]:
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

        return {
            cameraIndex: cs.CameraServer.putVideo(
                f"{NtClient.NT_TABLE}/{getCameraTableName(cameraIndex)}",
                width=getStreamRes(cameraIndex)[0],
                height=getStreamRes(cameraIndex)[1],
            )
            for cameraIndex in self.cameras.keys()
        }

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """
        self.outputs = self.getCameraOutputs()
        self.recordingOutputs = self.generateRecordingOutputs(list(self.cameras.keys()))

        def processCamera(cameraIndex: CameraID):
            output = self.outputs[cameraIndex]
            recordingOutput = self.recordingOutputs[cameraIndex]
            camera: SynapseCamera = self.cameras[cameraIndex]

            log.log(f"Started Camera #{cameraIndex} loop")

            while True:
                maxFps = camera.getMaxFPS()
                frame_time = 1.0 / float(maxFps)
                loop_start = Timer.getFPGATimestamp()

                ret, frame = camera.grabFrame()
                captureLatency = Timer.getFPGATimestamp() - loop_start
                if not ret or frame is None:
                    continue

                frame = self.fixtureFrame(cameraIndex, frame)

                process_start = Timer.getFPGATimestamp()
                pipeline = self.pipelineLoader.pipelineInstanceBindings.get(
                    self.pipelineBindings[cameraIndex], None
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
                    f"FPS: {fps:.2f}",
                    FPSView.position,
                    FPSView.font,
                    FPSView.fontScale,
                    FPSView.color,
                    FPSView.thickness,
                    lineType=cv2.LINE_8,
                )

                if processed_frame is not None:
                    resized_frame = cv2.resize(
                        processed_frame,
                        self.streamSizes[cameraIndex],
                        interpolation=cv2.INTER_AREA,
                    )
                    output.putFrame(resized_frame)
                    if camera.getSetting("record", False):
                        recordingOutput.write(processed_frame)

        def initThreads():
            for cameraIndex in self.cameras.keys():
                thread = threading.Thread(target=processCamera, args=(cameraIndex,))
                thread.daemon = True
                thread.start()

        initThreads()

        log.log(
            bcolors.OKGREEN
            + bcolors.BOLD
            + "\n"
            + "=" * 20
            + " Synapse Runtime Starting... "
            + "=" * 20
            + bcolors.ENDC
        )

        while True:
            if NtClient.INSTANCE:
                NtClient.INSTANCE.nt_inst.flush()
                if NtClient.INSTANCE.server:
                    NtClient.INSTANCE.server.flush()

    def handleResults(
        self, frames: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        if frames is not None:
            return self.handleFramePublishing(frames, cameraIndex)

    def handleFramePublishing(
        self, result: FrameResult, cameraIndex: CameraID
    ) -> Optional[Frame]:
        entry = getCameraTable(cameraIndex).getEntry("view_id")
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
        for cameraIndex, camera in self.cameras.items():
            entry = camera.getSettingEntry(CameraSettingsKeys.kPipeline.value)

            if entry is None:
                entry = getCameraTable(cameraIndex=cameraIndex).getEntry(
                    CameraSettingsKeys.kPipeline.value
                )
            NetworkTableInstance.getDefault().addListener(
                entry,
                EventFlags.kValueRemote,
                lambda event: self.setPipelineByIndex(
                    cameraIndex,
                    event.data.value.getInteger(),  # pyright: ignore
                ),
            )

            entry.setInteger(self.pipelineLoader.defaultPipelineIndexes[cameraIndex])

    def setCameraConfigs(
        self, settings: Dict[str, Any], camera: SynapseCamera
    ) -> Dict[str, Any]:
        updated_settings = {}
        for name in settings.keys():
            if name in CSCORE_TO_CV_PROPS.keys():
                setting_value = settings.get(name)
                if setting_value is not None:
                    camera.setProperty(
                        prop=name,
                        value=setting_value,
                    )

        camera.setVideoMode(
            width=int(settings["width"]), height=int(settings["height"]), fps=100
        )

        return updated_settings

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

    def cleanup(self) -> None:
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        for record in self.recordingOutputs.values():
            record.release()
        log.log("Cleaned up all resources.")
