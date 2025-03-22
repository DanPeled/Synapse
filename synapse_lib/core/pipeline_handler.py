import importlib.util
import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Optional, Tuple, Type, Union
import cv2
import ntcore
import numpy as np
from cscore import CameraServer, CvSource
from ntcore import Event, EventFlags, NetworkTable
from core.camera_factory import CsCoreCamera, SynapseCamera
import core.log as log
from hardware.metrics import MetricsManager
from networking import NtClient
from core.pipeline import GlobalSettings, Pipeline, PipelineSettings
from core.stypes import Frame
from wpimath.units import seconds


@dataclass
class CameraBinding:
    path: str
    name: str


class PipelineHandler:
    NT_TABLE: Final[str] = "Synapse"
    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)

    def __init__(self, directory: str):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param directory: Root directory to search for pipeline files
        """
        self.directory = directory
        self.metricsManager: Final[MetricsManager] = MetricsManager()
        self.metricsManager.setConfig(None)
        self.cameras: Dict[int, SynapseCamera] = {}
        self.pipelineMap: Dict[int, Union[Type[Pipeline], List[Type[Pipeline]]]] = {}
        self.pipelineInstances: Dict[int, List[Pipeline]] = {}
        self.pipelineSettings: Dict[int, PipelineSettings] = {}
        self.defaultPipelineIndexes: Dict[int, int] = {}
        self.pipelineBindings: Dict[int, int] = {}
        self.streamSizes: Dict[int, Tuple[int, int]] = {}
        self.pipelineTypes: Dict[int, str] = {}
        self.pipelineSubscribers: Dict[int, ntcore.IntegerSubscriber] = {}
        self.outputs: Dict[int, CvSource] = {}
        self.recordingOutputs: Dict[int, cv2.VideoWriter] = {}

    def setup(self, settings: Dict[Any, Any]):
        import atexit

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
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith("_pipeline.py") and file not in ignoredFiles:
                    file_path = os.path.join(root, file)
                    module_name = file[:-3]  # Remove .py extension

                    try:
                        # Load module directly from file path
                        spec = importlib.util.spec_from_file_location(
                            module_name, file_path
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

    def addCamera(self, camera_index: int) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.
        :param camera_index: Camera index to open
        """
        if camera_index not in self.cameraBindings:
            log.err(f"No camera defined for index {camera_index}")
            return False

        camera_config = self.cameraBindings[camera_index]
        path = (
            int(camera_config.path)
            if isinstance(camera_config.path, int)
            else camera_config.path
        )

        try:
            camera = CsCoreCamera()
            camera.create(
                devPath=camera_config.path,
                name=f"{self.NT_TABLE}/camera{camera_index}/input",
            )
        except Exception as e:
            log.err(f"Failed to start camera capture: {e}")
            return False

        count = 0
        MAX_RETRIES = 30
        DELAY = 1

        while not camera.isConnected() and count < MAX_RETRIES:
            log.err(f"Trying to open camera #{camera_index} ({path})")
            count += 1
            time.sleep(DELAY)

        if camera.isConnected():
            self.cameras[camera_index] = camera
            log.log(f"Camera ({camera_config}, id={camera_index}) added successfully.")
            return True

        log.err(
            f"Failed to open camera #{camera_index} ({path}) after {MAX_RETRIES} retries."
        )
        return False

    def __setPipelineForCamera(
        self,
        camera_index: int,
        pipeline: Union[Type[Pipeline], List[Type[Pipeline]]],
        pipeline_config: PipelineSettings,
    ):
        """
        Sets the pipeline(s) to be used for a specific camera.
        :param camera_index: Index of the camera
        :param pipeline: A pipeline class or list of pipeline classes to assign to the camera
        """
        self.pipelineMap[camera_index] = pipeline
        # Create instances for each pipeline only when setting them
        if isinstance(pipeline, Type):
            pipeline = [pipeline]

        self.pipelineInstances[camera_index] = [
            pipeline_cls(
                settings=self.pipelineSettings[self.pipelineBindings[camera_index]],
                camera_index=camera_index,
            )
            for pipeline_cls in pipeline
        ]

        for currPipeline in self.pipelineInstances[camera_index]:
            if NtClient.INSTANCE is not None:
                camera_table = self.getCameraTable(camera_index)

                self.setCameraConfigs(
                    pipeline_config.getMap(), self.cameras[camera_index]
                )

                if camera_table is not None:
                    setattr(currPipeline, "nt_table", camera_table)
                    setattr(currPipeline, "builder_cache", {})
                    currPipeline.setup()
                    pipeline_config.sendSettings(camera_table.getSubTable("settings"))

        # log.log(f"Set pipeline(s) for camera {camera_index}: {str(pipeline)}")

    def syncCurrentPipeline(self, camera_index: int):
        if NtClient.INSTANCE is not None:
            entry = NtClient.INSTANCE.nt_inst.getTable(
                PipelineHandler.NT_TABLE
            ).getEntry(f"{self.getCameraTableName(camera_index)}/pipeline")

            nt_pipeline = entry.getInteger(None)

            # print(f"pipeline: {pipeline}, entry : {entry.getName()}")

            if (
                nt_pipeline != self.pipelineBindings[camera_index]
                and nt_pipeline is not None
            ):
                self.setPipelineByIndex(camera_index, nt_pipeline)

    def syncPipelineSettings(self, camera_index: int):
        settings = self.pipelineSettings[self.pipelineBindings[camera_index]]
        somethingChanged = False
        for key, value in settings.getMap().items():
            nt_table = self.getCameraTable(camera_index)
            if nt_table is not None:
                nt_val = nt_table.getSubTable("settings").getValue(key, None)
                if nt_val != value:
                    self.pipelineSettings[self.pipelineBindings[camera_index]][key] = (
                        nt_val
                    )

                    somethingChanged = True

        if somethingChanged:
            self.setCameraConfigs(
                settings=self.pipelineSettings[
                    self.pipelineBindings[camera_index]
                ].getMap(),
                camera=self.cameras[camera_index],
            )

    def getCameraTable(self, camera_index: int) -> Optional[NetworkTable]:
        if NtClient.INSTANCE is not None:
            return NtClient.INSTANCE.nt_inst.getTable(
                PipelineHandler.NT_TABLE
            ).getSubTable(self.getCameraTableName(camera_index))

    def setPipelineByIndex(self, camera_index: int, pipeline_index: int):
        if camera_index not in self.cameras.keys():
            log.err(
                f"Invalid camera_index {camera_index}. Must be in range(0, {len(self.cameras.keys())-1})."
            )
            return

        if pipeline_index not in self.pipelineTypes.keys():
            log.err(
                f"Invalid pipeline_index {pipeline_index}. Must be one of {list(self.pipelineTypes.keys())}."
            )
            self.setNTPipelineIndex(camera_index, self.pipelineBindings[camera_index])
            return

        # If both indices are valid, proceed with the pipeline setting
        self.pipelineBindings[camera_index] = pipeline_index

        self.setNTPipelineIndex(
            camera_index=camera_index, pipeline_index=pipeline_index
        )

        settings = self.pipelineSettings[pipeline_index]

        self.__setPipelineForCamera(
            camera_index=camera_index,
            pipeline=self.pipelines[self.pipelineTypes[pipeline_index]],
            pipeline_config=settings,
        )

        log.log(f"Set pipeline #{pipeline_index} for camera ({camera_index})")

    def setNTPipelineIndex(self, camera_index: int, pipeline_index: int):
        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.nt_inst.getTable(PipelineHandler.NT_TABLE).getEntry(
                f"{self.getCameraTableName(camera_index)}/pipeline"
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
            i: CameraServer.putVideo(
                f"{PipelineHandler.NT_TABLE}/{self.getCameraTableName(i)}/output",
                width=getStreamRes(i)[0],
                height=getStreamRes(i)[1],
            )
            for i in self.cameras.keys()
        }

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """
        try:
            self.outputs = self.getCameraOutputs()
            log.log("Set up outputs array")
            self.recordingOutputs = self.generateRecordingOutputs(
                list(self.cameras.keys())
            )
            log.log("Set up recording outputs array")

            def process_camera(camera_index: int):
                output = self.outputs[camera_index]
                recordingOutput = self.recordingOutputs[camera_index]
                SHOULD_RECORD = True
                while True:
                    start_time = time.time()  # Start time for FPS calculation
                    ret, frame = self.cameras[camera_index].grabFrame()

                    captureLatency = time.time() - start_time
                    if not ret or frame is None:
                        continue

                    frame = self.fixtureFrame(camera_index, frame)

                    process_start = time.time()
                    # Retrieve the pipeline instances for the current camera
                    assigned_pipelines = self.pipelineInstances.get(camera_index, [])
                    processed_frame: Any = frame
                    # Process the frame through each assigned pipeline
                    for pipeline in assigned_pipelines:
                        processed_frame = pipeline.process_frame(frame, start_time)

                    end_time = time.time()  # End time for FPS calculation
                    processLatency = end_time - process_start
                    fps = 1.0 / (end_time - start_time)  # Calculate FPS

                    self.sendLatency(camera_index, captureLatency, processLatency)
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
                        output.putFrame(
                            cv2.resize(
                                processed_frame,
                                self.streamSizes[camera_index],
                            )
                        )
                        if SHOULD_RECORD:
                            recordingOutput.write(processed_frame)

                    if NtClient.INSTANCE is not None:
                        self.syncCurrentPipeline(camera_index)
                        self.syncPipelineSettings(camera_index)

            # Create and start a thread for each camera
            threads = []
            for pipeline_index in self.cameras.keys():
                thread = threading.Thread(target=process_camera, args=(pipeline_index,))
                thread.daemon = True  # Daemon threads will automatically close on exit
                threads.append(thread)
                thread.start()

            while True:
                time.sleep(1)
                self.metricsManager.publishMetrics()

        finally:
            self.cleanup()

    def sendLatency(self, camera_index: int, capture: seconds, process: seconds):
        if NtClient.INSTANCE is not None:
            cameraTable = self.getCameraTable(camera_index)
            if cameraTable is not None:
                cameraTable.getEntry("captureLatency").setDouble(capture)
                cameraTable.getEntry("processLatency").setDouble(process)

    def setupNetworkTables(self):
        log.log("Setting up networktables...")

        def keepCurrentPipelineUpdatedListener(
            table: ntcore.NetworkTable, key: str, _: Event
        ) -> None:
            index = int(key.replace("camera", "").replace("pipeline", ""))
            self.setPipelineByIndex(
                camera_index=index,
                pipeline_index=table.getEntry(key).getInteger(
                    defaultValue=self.defaultPipelineIndexes[index]
                ),
            )

        if NtClient.INSTANCE is not None:
            inst = NtClient.INSTANCE.server or NtClient.INSTANCE.nt_inst

            table: ntcore.NetworkTable = inst.getTable(PipelineHandler.NT_TABLE)

            for i in self.cameras.keys():
                topicName = f"{self.getCameraTableName(i)}/pipeline"

                topic = inst.getTable(PipelineHandler.NT_TABLE).getIntegerTopic(
                    topicName
                )

                pub = topic.publish(ntcore.PubSubOptions(keepDuplicates=True))
                pub.setDefault(self.defaultPipelineIndexes[i])

                sub = topic.subscribe(
                    self.defaultPipelineIndexes[i],
                    ntcore.PubSubOptions(keepDuplicates=True, pollStorage=10),
                )

                NtClient.INSTANCE.nt_inst.getTable(PipelineHandler.NT_TABLE).getEntry(
                    topicName
                ).setInteger(sub.get())

                self.pipelineSubscribers[i] = sub

                log.log(f"Added listener for camera {i}, entry:{topic.getName()}")

                table.addListener(
                    key=topicName,
                    eventMask=EventFlags.kImmediate,
                    listener=keepCurrentPipelineUpdatedListener,
                )
            log.log("Set up settings successfully")
        else:
            log.err("NtClient instance is None")

    def getCameraTableName(self, index: int) -> str:
        return f"camera{index}"

    def loadSettings(self):
        import yaml

        log.log("Loading settings...")
        with open(r"./config/settings.yml") as file:
            settings = yaml.full_load(file)

            camera_configs = settings["global"]["camera_configs"]

            for camera_index in camera_configs:
                if not (self.addCamera(camera_index)):
                    return
                self.defaultPipelineIndexes[camera_index] = camera_configs[
                    camera_index
                ]["default_pipeline"]

            pipelines = settings["pipelines"]

            for index, _ in enumerate(pipelines):
                pipeline = pipelines[index]

                log.log(f"Loaded pipeline #{index} with type {pipeline['type']}")

                self.setPipelineSettings(index, pipeline["settings"])

                self.pipelineTypes[index] = pipeline["type"]

        for camera_index in self.cameras.keys():
            pipeline = self.defaultPipelineIndexes[camera_index]
            self.setPipelineByIndex(
                camera_index=camera_index,
                pipeline_index=pipeline,
            )
            log.log(f"Setup default pipeline (#{pipeline}) for camera ({camera_index})")

        log.log("Loaded pipelines successfully")
        self.setupNetworkTables()

    @staticmethod
    def setCameraConfigs(
        settings: Dict[str, Any], camera: SynapseCamera
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

        def set_property(name: str, value: int):
            """Set property if it exists, clamping the value within bounds."""
            camera.setProperty(name, value)

        for name in settings.keys():
            if name not in excluded:
                setting_value = settings.get(name)
                if setting_value is not None:
                    set_property(name, setting_value)

        # Desired mode
        desired_mode = (
            int(settings["width"]),
            int(settings["height"]),
        )

        # Check if the desired mode is valid
        if True:
            # if desired_mode in valid_modes:
            camera.setVideoMode(
                width=desired_mode[0],
                height=desired_mode[1],
                fps=100,
            )
            updated_settings.update(
                {
                    "fps": settings.get("fps", 100),
                    "width": int(settings["width"]),
                    "height": int(settings["height"]),
                }
            )
        else:
            log.err(
                f"Warning: Invalid video mode {desired_mode}. Using default settings."
            )

        return updated_settings

    def rotateCameraBySettings(self, settings: PipelineSettings, frame: Frame) -> Frame:
        if "orientation" in settings.getMap():
            orientation = settings.get("orientation")

            if orientation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif orientation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif orientation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

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

    def fixtureFrame(self, camera_index: int, frame: Frame) -> Frame:
        settings = self.pipelineSettings[self.pipelineBindings[camera_index]]
        frame = self.rotateCameraBySettings(settings, frame)
        # frame = self.fixBlackLevelOffset(settings, frame)

        return frame

    def setPipelineSettings(
        self,
        pipeline_index: int,
        settings: PipelineSettings.PipelineSettingsMap,
    ):
        self.pipelineSettings[pipeline_index] = PipelineSettings(settings)

    def cleanup(self):
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        for sub in self.pipelineSubscribers.values():
            name = sub.getTopic().getName()
            sub.close()
            log.log(f"Close sub : {name}")
        for record in self.recordingOutputs.values():
            record.release()
        log.log("Cleaned up all resources.")
