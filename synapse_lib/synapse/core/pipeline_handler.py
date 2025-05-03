import importlib.util
import threading
import time
import traceback
from functools import cache
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple, Type

import cscore as cs
import cv2
import numpy as np
import synapse.log as log
from ntcore import (
    Event,
    EventFlags,
    NetworkTableInstance,
    NetworkTableType,
)
from synapse.bcolors import bcolors
from synapse.hardware import MetricsManager
from synapse.networking import NtClient
from wpilib import Timer
from wpimath.units import seconds

from .camera_factory import (
    CameraBinding,
    CameraSettingsKeys,
    CsCoreCamera,
    SynapseCamera,
    getCameraTable,
    getCameraTableName,
)
from .config import Config
from .pipeline import FrameResult, GlobalSettings, Pipeline, PipelineSettings
from .stypes import Frame


class PipelineHandler:
    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)

    def __init__(self, pipelineDirectory: Path):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param pipelineDirectory: Root directory to search for pipeline files
        """
        self.pipelineDirectory: Path = pipelineDirectory
        self.metricsManager: Final[MetricsManager] = MetricsManager()
        self.metricsManager.setConfig(None)
        self.cameras: Dict[int, SynapseCamera] = {}
        self.pipelineInstanceBindings: Dict[int, Pipeline] = {}
        self.pipelineSettings: Dict[int, PipelineSettings] = {}
        self.defaultPipelineIndexes: Dict[int, int] = {}
        self.pipelineBindings: Dict[int, int] = {}
        self.streamSizes: Dict[int, Tuple[int, int]] = {}
        self.pipelineTypes: Dict[int, str] = {}
        self.outputs: Dict[int, cs.CvSource] = {}
        self.recordingOutputs: Dict[int, cv2.VideoWriter] = {}

    def setup(self, settings: Dict[Any, Any]):
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

        self.pipelines = self.loadPipelines()
        self.cameraBindings = self.setupCameraBindings(
            settings["global"]["camera_configs"]
        )
        atexit.register(self.cleanup)

    def setupCameraBindings(self, cameras_yml: dict):
        bindings: Dict[int, CameraBinding] = {}

        for index in cameras_yml.keys():
            bindings[index] = CameraBinding(
                cameras_yml[index]["path"], cameras_yml[index]["name"]
            )

        return bindings

    def loadPipelines(self) -> Dict[str, Type[Pipeline]]:
        """
        Loads all classes that extend Pipeline from Python files in the directory.
        :return: A dictionary of Pipeline subclasses
        """
        log.log("Loading pipelines...")

        ignoredFiles = ["setup.py"]
        pipelines = {}
        for file_path in self.pipelineDirectory.rglob("*_pipeline.py"):
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
                                pipelines[cls.__name__] = cls
                except Exception as e:
                    log.err(f"while loading {file_path}: {e}")
                    traceback.print_exc()

        log.log("Loaded pipelines successfully")
        return pipelines

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

    def addCamera(self, cameraIndex: int) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.
        :param cameraIndex: Camera index to open
        """
        if cameraIndex not in self.cameraBindings:
            log.err(f"No camera defined for index {cameraIndex}")
            return False

        camera_config = self.cameraBindings[cameraIndex]
        path = (
            int(camera_config.path)
            if isinstance(camera_config.path, int)
            else camera_config.path
        )

        try:
            camera = CsCoreCamera.create(
                devPath=camera_config.path,
                name=f"{NtClient.NT_TABLE}/camera{cameraIndex}/input",
            )
            camera.setIndex(cameraIndex)
        except Exception as e:
            log.err(f"Failed to start camera capture: {e}")
            return False

        count = 0
        MAX_RETRIES = 30
        DELAY = 1

        while not camera.isConnected() and count < MAX_RETRIES:
            log.err(f"Trying to open camera #{cameraIndex} ({path})")
            count += 1
            time.sleep(DELAY)

        if camera.isConnected():
            self.cameras[cameraIndex] = camera
            log.log(f"Camera ({camera_config}, id={cameraIndex}) added successfully.")
            return True

        log.err(
            f"Failed to open camera #{cameraIndex} ({path}) after {MAX_RETRIES} retries."
        )
        return False

    def __setupPipelineForCamera(
        self,
        cameraIndex: int,
        pipelineType: Type[Pipeline],
        pipeline_config: PipelineSettings,
    ):
        """
        Sets the pipeline(s) to be used for a specific camera.
        :param cameraIndex: Index of the camera
        :param pipeline: A pipeline class or list of pipeline classes to assign to the camera
        """
        # Create instances for each pipeline only when setting them

        self.pipelineInstanceBindings[cameraIndex] = pipelineType(
            settings=self.pipelineSettings[self.pipelineBindings[cameraIndex]],
            cameraIndex=cameraIndex,
        )

        currPipeline = self.pipelineInstanceBindings[cameraIndex]
        if NtClient.INSTANCE is not None:
            camera_table = getCameraTable(cameraIndex)

            self.setCameraConfigs(pipeline_config.getMap(), self.cameras[cameraIndex])

            if camera_table is not None:
                setattr(currPipeline, "nt_table", camera_table)
                setattr(currPipeline, "builder_cache", {})
                currPipeline.setup()
                pipeline_config.sendSettings(camera_table.getSubTable("settings"))

                def updateSettingListener(event: Event):
                    prop: str = event.data.topic.getName().split("/")[-1]  # pyright: ignore
                    value: Any = self.getEventDataValue(event)
                    self.pipelineSettings[self.pipelineBindings[cameraIndex]][prop] = (
                        value
                    )
                    self.updateCameraProperty(
                        camera=self.cameras[cameraIndex],
                        prop=prop,
                        value=value,
                    )

                for key in pipeline_config.getMap().keys():
                    nt_table = getCameraTable(cameraIndex)
                    if nt_table is not None:
                        entry = nt_table.getSubTable("settings").getEntry(key)

                        NtClient.INSTANCE.nt_inst.addListener(
                            entry, EventFlags.kValueRemote, updateSettingListener
                        )

    @cache
    @staticmethod
    def getEventDataValue(event: Event) -> Any:
        topic = event.data.topic  # pyright: ignore
        topicType = topic.getType()
        value = event.data.value  # pyright: ignore

        if topicType == NetworkTableType.kBoolean:
            return value.getBoolean()
        elif topicType == NetworkTableType.kDouble:
            return value.getDouble()
        elif topicType == NetworkTableType.kInteger:
            return value.getInteger()
        elif topicType == NetworkTableType.kString:
            return value.getString()
        elif topicType == NetworkTableType.kBooleanArray:
            return value.getBooleanArray()
        elif topicType == NetworkTableType.kDoubleArray:
            return value.getDoubleArray()
        elif topicType == NetworkTableType.kIntegerArray:
            return value.getIntegerArray()
        elif topicType == NetworkTableType.kStringArray:
            return value.getStringArray()
        else:
            raise ValueError(f"Unsupported topic type: {topicType}")

    def setPipelineByIndex(self, cameraIndex: int, pipeline_index: int):
        if cameraIndex not in self.cameras.keys():
            log.err(
                f"Invalid cameraIndex {cameraIndex}. Must be in range(0, {len(self.cameras.keys())-1})."
            )
            return

        if pipeline_index not in self.pipelineTypes.keys():
            log.err(
                f"Invalid pipeline index {pipeline_index}. Must be one of {list(self.pipelineTypes.keys())}."
            )
            self.setNTPipelineIndex(cameraIndex, self.pipelineBindings[cameraIndex])
            return

        # If both indices are valid, proceed with the pipeline setting
        self.pipelineBindings[cameraIndex] = pipeline_index

        self.setNTPipelineIndex(cameraIndex=cameraIndex, pipeline_index=pipeline_index)

        settings = self.pipelineSettings[pipeline_index]

        self.__setupPipelineForCamera(
            cameraIndex=cameraIndex,
            pipelineType=self.pipelines[self.pipelineTypes[pipeline_index]],
            pipeline_config=settings,
        )

        log.log(f"Set pipeline #{pipeline_index} for camera ({cameraIndex})")

    def setNTPipelineIndex(self, cameraIndex: int, pipeline_index: int):
        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.nt_inst.getTable(NtClient.NT_TABLE).getEntry(
                f"{getCameraTableName(cameraIndex)}/pipeline"
            ).setInteger(pipeline_index)

    def getCameraOutputs(self):
        def getStreamRes(i: int) -> Tuple[int, int]:
            if "camera_configs" in GlobalSettings:
                cameraConfigs = GlobalSettings.get("camera_configs")
                if cameraConfigs is not None:
                    streamRes = cameraConfigs[i]["stream_res"]
                    self.streamSizes[i] = streamRes
                    return (streamRes[0], streamRes[1])

            return self.DEFAULT_STREAM_SIZE

        return {
            i: cs.CameraServer.putVideo(
                f"{NtClient.NT_TABLE}/{getCameraTableName(i)}",
                width=getStreamRes(i)[0],
                height=getStreamRes(i)[1],
            )
            for i in self.cameras.keys()
        }

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """
        self.outputs = self.getCameraOutputs()
        self.recordingOutputs = self.generateRecordingOutputs(list(self.cameras.keys()))

        def processCamera(cameraIndex: int):
            output = self.outputs[cameraIndex]
            recordingOutput = self.recordingOutputs[cameraIndex]
            camera: SynapseCamera = self.cameras[cameraIndex]

            log.log(f"Started Camera #{cameraIndex} loop")

            while True:
                start_time = Timer.getFPGATimestamp()  # Start time for FPS calculation
                ret, frame = camera.grabFrame()

                captureLatency = Timer.getFPGATimestamp() - start_time
                if not ret or frame is None:
                    continue

                frame = self.fixtureFrame(cameraIndex, frame)

                process_start = Timer.getFPGATimestamp()
                # Retrieve the pipeline instances for the current camera
                pipeline = self.pipelineInstanceBindings.get(cameraIndex, None)
                processed_frame: Frame = frame

                if pipeline is not None:
                    # Process the frame through each assigned pipeline
                    result = pipeline.processFrame(frame, start_time)
                    frame = self.handleResults(result, cameraIndex)

                    if frame is not None:
                        processed_frame = frame

                end_time = Timer.getFPGATimestamp()  # End time for FPS calculation
                processLatency = end_time - process_start
                fps = 1.0 / (end_time - start_time)  # Calculate FPS

                self.sendLatency(cameraIndex, captureLatency, processLatency)

                # Overlay FPS on the frame
                cv2.putText(
                    processed_frame,
                    f"FPS: {fps:.2f}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
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
            for index in self.cameras.keys():
                thread = threading.Thread(target=processCamera, args=(index,))
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

    def handleResults(self, frames: FrameResult, cameraIndex: int) -> Optional[Frame]:
        if frames is not None:
            return self.handleFramePiblishing(frames, cameraIndex)

    def handleFramePiblishing(
        self, result: FrameResult, cameraIndex: int
    ) -> Optional[Frame]:
        entry = getCameraTable(cameraIndex).getEntry("view_id")
        DEFAULT_STEP: str = "step_0"
        if result is None:
            return
        if isinstance(result, Frame):
            if not entry.exists():
                entry.setString(DEFAULT_STEP)
            if entry.getString(defaultValue=DEFAULT_STEP) == DEFAULT_STEP:
                return result
        else:
            for i, var in enumerate(result):
                if not entry.exists():
                    entry.setString(DEFAULT_STEP)
                if entry.getString(defaultValue=DEFAULT_STEP) == f"step_{i}":
                    return var

    def sendLatency(
        self, cameraIndex: int, captureLatency: seconds, processingLatency: seconds
    ) -> None:
        cameraTable = getCameraTable(cameraIndex)
        cameraTable.getEntry("captureLatency").setDouble(captureLatency)
        cameraTable.getEntry("processLatency").setDouble(processingLatency)

    def setupNetworkTables(self) -> None:
        for cameraIndex, camera in self.cameras.items():
            entry = camera.getSettingEntry(CameraSettingsKeys.pipeline.value)

            if entry is not None:
                NetworkTableInstance.getDefault().addListener(
                    entry,
                    EventFlags.kValueRemote,
                    lambda event: self.setPipelineByIndex(
                        cameraIndex,
                        event.data.value.getInteger(),  # pyright: ignore
                    ),
                )

                entry.setInteger(self.defaultPipelineIndexes[cameraIndex])

    def loadPipelineSettings(self) -> None:
        settings: dict = Config.getInstance().getConfigMap()
        camera_configs = settings["global"]["camera_configs"]

        for cameraIndex in camera_configs:
            if not (self.addCamera(cameraIndex)):
                return
            self.defaultPipelineIndexes[cameraIndex] = camera_configs[cameraIndex][
                "default_pipeline"
            ]

        pipelines = settings["pipelines"]

        for index, _ in enumerate(pipelines):
            pipeline = pipelines[index]

            log.log(f"Loaded pipeline #{index} with type {pipeline['type']}")

            self.setPipelineSettings(index, pipeline["settings"])

            self.pipelineTypes[index] = pipeline["type"]

        for cameraIndex in self.cameras.keys():
            pipeline = self.defaultPipelineIndexes[cameraIndex]
            self.setPipelineByIndex(
                cameraIndex=cameraIndex,
                pipeline_index=pipeline,
            )
            log.log(f"Setup default pipeline (#{pipeline}) for camera ({cameraIndex})")

        log.log("Loaded pipelines successfully")
        self.setupNetworkTables()

    def setCameraConfigs(
        self, settings: Dict[str, Any], camera: SynapseCamera
    ) -> Dict[str, Any]:
        updated_settings = {}
        excluded = [
            "",
            "sharpness",
            "raw_sharpness",
            "raw_saturation",
            "white_balance_automatic",
            "raw_gain",
            "raw_hue",
            "raw_brightness",
            "raw_contrast",
            "raw_exposure_time_absolute",
            "power_line_frequency",
            "exposure_time_absolute",
            "gamma",
            "white_balance_temperature",
            "connect_verbose",
            "exposure_dynamic_framerate",
            "backlight_compensation",
            "auto_exposure",
        ]

        for name in settings.keys():
            if name not in excluded:
                setting_value = settings.get(name)
                if setting_value is not None:
                    self.updateCameraProperty(
                        camera=camera,
                        prop=name,
                        value=setting_value,
                    )

        camera.setVideoMode(
            width=settings["width"],
            height=settings["height"],
            fps=100,
        )

        return updated_settings

    def updateCameraProperty(self, camera: SynapseCamera, prop: str, value: Any):
        camera.setProperty(prop, value)

    def rotateCameraBySettings(self, settings: PipelineSettings, frame: Frame) -> Frame:
        settings_map = settings.getMap()
        orientation = settings_map.get("orientation")

        rotations = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE,
        }

        if orientation in rotations:
            frame = cv2.rotate(frame, rotations[orientation])

        return frame

    def fixBlackLevelOffset(self, settings: PipelineSettings, frame: Frame) -> Frame:
        blackLevelOffset = settings.get("black_level_offset")

        if blackLevelOffset == 0 or blackLevelOffset is None:
            return frame  # No adjustment needed

        blackLevelOffset = -blackLevelOffset / 100

        # Convert to float32 for better precision
        image = frame.astype(np.float32) / 255.0  # Normalize to range [0,1]

        # Apply black level offset: lift only the darkest values
        image = np.power(image + blackLevelOffset, 1.0)  # Apply a soft offset

        # Clip to valid range and convert back to uint8
        return np.clip(image * 255, 0, 255).astype(np.uint8)

    def fixtureFrame(self, cameraIndex: int, frame: Frame) -> Frame:
        settings = self.pipelineSettings[self.pipelineBindings[cameraIndex]]
        frame = self.rotateCameraBySettings(settings, frame)
        # frame = self.fixBlackLevelOffset(settings, frame)

        return frame

    def setPipelineSettings(
        self,
        pipeline_index: int,
        settings: PipelineSettings.PipelineSettingsMap,
    ) -> None:
        self.pipelineSettings[pipeline_index] = PipelineSettings(settings)

    def cleanup(self) -> None:
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        for record in self.recordingOutputs.values():
            record.release()
        log.log("Cleaned up all resources.")
