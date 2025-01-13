import importlib.util
import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, Union

import cv2
import ntcore
import numpy as np
from cscore import CameraServer, CvSink, CvSource, UsbCamera, VideoMode
from ntcore import Event, EventFlags, NetworkTable
from synapse.log import err, log
from synapse.nt_client import NtClient
from synapse.pipeline import Pipeline, PipelineSettings


@dataclass
class CameraBinding:
    path: str
    name: str


class PipelineHandler:
    NT_TABLE = "Synapse"

    def __init__(self, directory: str):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param directory: Root directory to search for pipeline files
        """
        self.directory = directory
        self.cameras: Dict[int, UsbCamera] = {}
        self.pipeline_map: Dict[int, Union[Type[Pipeline], List[Type[Pipeline]]]] = {}
        self.pipeline_instances: Dict[int, List[Pipeline]] = {}
        self.pipeline_settings: Dict[int, PipelineSettings] = {}
        self.default_pipeline_indexes: Dict[int, int] = {}
        self.pipeline_bindings: Dict[int, int] = {}
        self.pipeline_types: Dict[int, str] = {}
        self.pipeline_subscribers: Dict[int, ntcore.IntegerSubscriber] = {}
        self.outputs: Dict[int, CvSource] = {}
        self.sinks: Dict[int, CvSink] = {}

    def setup(self, settings: Dict[Any, Any]):
        self.pipelines = self.loadPipelines()
        self.camera_bindings = self.setupCameraBindings(
            settings["global"]["camera_configs"]
        )

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
        log("Loading pipelines...")
        pipelines = {}
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith(".py"):
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
                                    log(f"Loaded {cls.__name__} pipeline")
                                    pipelines[cls.__name__] = cls
                    except Exception as e:
                        err(
                            f"while loading {file_path}: {e}"
                        )  # Consider using logging instead
                        traceback.print_exc()

        log("Loaded pipelines successfully")
        return pipelines

    def addCamera(self, camera_index: int) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.
        :param camera_index: Camera index to open
        """
        if camera_index not in self.camera_bindings.keys():
            err(f"No camera defined for index {camera_index}")
            return False

        camera_config = self.camera_bindings[camera_index]

        path = camera_config.path

        if isinstance(path, int):
            path = int(path)

        camera = CameraServer.startAutomaticCapture(
            f"{PipelineHandler.NT_TABLE}/{self.getCameraTableName(camera_index)}/input",
            path,
        )

        if camera.isConnected():
            self.cameras[camera_index] = camera
            log(f"Camera ({camera_config}, id={camera_index}) added successfully.")
            return True
        else:
            err(f"Failed to open camera {camera_index}.")
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
        self.pipeline_map[camera_index] = pipeline
        # Create instances for each pipeline only when setting them
        if isinstance(pipeline, Type):
            pipeline = [pipeline]

        self.pipeline_instances[camera_index] = [
            pipeline_cls(
                settings=self.pipeline_settings[self.pipeline_bindings[camera_index]],
                camera_index=camera_index,
            )
            for pipeline_cls in pipeline
        ]

        for currPipeline in self.pipeline_instances[camera_index]:
            if NtClient.INSTANCE is not None:
                camera_table = self.getCameraTable(camera_index)

                if camera_table is not None:
                    setattr(currPipeline, "nt_table", camera_table)
                    setattr(currPipeline, "builder_cache", {})
                    currPipeline.setup()
                    pipeline_config.sendSettings(camera_table.getSubTable("settings"))
            self.setCameraConfigs(pipeline_config.getMap(), self.cameras[camera_index])

        # log(f"Set pipeline(s) for camera {camera_index}: {str(pipeline)}")

    def syncCurrentPipeline(self, camera_index: int):
        if NtClient.INSTANCE is not None:
            entry = NtClient.INSTANCE.nt_inst.getTable(
                PipelineHandler.NT_TABLE
            ).getEntry(f"{self.getCameraTableName(camera_index)}/pipeline")

            nt_pipeline = entry.getInteger(None)

            # print(f"pipeline: {pipeline}, entry : {entry.getName()}")

            if (
                nt_pipeline != self.pipeline_bindings[camera_index]
                and nt_pipeline is not None
            ):
                self.setPipelineByIndex(camera_index, nt_pipeline)

    def syncPipelineSettings(self, camera_index: int):
        settings = self.pipeline_settings[self.pipeline_bindings[camera_index]]
        for key, value in settings.getMap().items():
            nt_table = self.getCameraTable(camera_index)
            if nt_table is not None:
                nt_val = nt_table.getSubTable("settings").getValue(key, None)
                if nt_val != value:
                    self.pipeline_settings[self.pipeline_bindings[camera_index]][
                        key
                    ] = nt_val

                    self.setCameraConfigs(
                        settings=self.pipeline_settings[
                            self.pipeline_bindings[camera_index]
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
            err(
                f"Invalid camera_index {camera_index}. Must be in range(0, {len(self.cameras.keys())-1})."
            )
            return

        if pipeline_index not in self.pipeline_types.keys():
            err(
                f"Invalid pipeline_index {pipeline_index}. Must be one of {list(self.pipeline_types.keys())}."
            )
            self.setNTPipelineIndex(camera_index, self.pipeline_bindings[camera_index])
            return

        # If both indices are valid, proceed with the pipeline setting
        self.pipeline_bindings[camera_index] = pipeline_index

        self.setNTPipelineIndex(
            camera_index=camera_index, pipeline_index=pipeline_index
        )

        settings = self.pipeline_settings[pipeline_index]

        self.__setPipelineForCamera(
            camera_index=camera_index,
            pipeline=self.pipelines[self.pipeline_types[pipeline_index]],
            pipeline_config=settings,
        )

        log(f"Set pipeline #{pipeline_index} for camera ({camera_index})")

    def setNTPipelineIndex(self, camera_index: int, pipeline_index: int):
        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.nt_inst.getTable(PipelineHandler.NT_TABLE).getEntry(
                f"{self.getCameraTableName(camera_index)}/pipeline"
            ).setInteger(pipeline_index)

    def getCameraOutputs(self):
        def getSettingsMap(camera_index: int) -> dict:
            return self.pipeline_settings[self.pipeline_bindings[camera_index]].getMap()

        return {
            i: CameraServer.putVideo(
                f"{PipelineHandler.NT_TABLE}/{self.getCameraTableName(i)}/output",
                width=int(getSettingsMap(i)["width"]),
                height=int(getSettingsMap(i)["height"]),
            )
            for i in self.cameras.keys()
        }

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """
        try:
            self.sinks = {
                i: CameraServer.getVideo(self.cameras[i]) for i in self.cameras.keys()
            }

            log("Set up sinks array")
            frame_buffers = {
                i: np.zeros((1920, 1080, 3), dtype=np.uint8)
                for i in self.cameras.keys()
            }

            log("Set up frame buffers")

            self.outputs = self.getCameraOutputs()
            log("Set up outputs array")

            def process_camera(camera_index: int):
                sink = self.sinks[camera_index]
                frame_buffer = frame_buffers[camera_index]
                output = self.outputs[camera_index]

                while True:
                    start_time = time.time()  # Start time for FPS calculation
                    ret, frame = sink.grabFrame(frame_buffer)

                    if ret == 0 or frame is None:
                        continue

                    # Retrieve the pipeline instances for the current camera
                    assigned_pipelines = self.pipeline_instances.get(camera_index, [])
                    processed_frame: Any = frame

                    # Process the frame through each assigned pipeline
                    for pipeline in assigned_pipelines:
                        processed_frame = pipeline.process_frame(frame, start_time)

                    end_time = time.time()  # End time for FPS calculation
                    fps = 1.0 / (end_time - start_time)  # Calculate FPS

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
                        output.putFrame(processed_frame)

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

            # Keep the main thread alive to allow all camera threads to run
            while True:
                time.sleep(1)

        finally:
            self.cleanup()

    def setupNetworkTables(self):
        log("Setting up networktables...")

        def keepCurrentPipelineUpdatedListener(
            table: ntcore.NetworkTable, key: str, _: Event
        ) -> None:
            index = int(key.replace("camera", "").replace("pipeline", ""))
            self.setPipelineByIndex(
                camera_index=index,
                pipeline_index=table.getEntry(key).getInteger(
                    defaultValue=self.default_pipeline_indexes[index]
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
                pub.setDefault(self.default_pipeline_indexes[i])

                sub = topic.subscribe(
                    self.default_pipeline_indexes[i],
                    ntcore.PubSubOptions(keepDuplicates=True, pollStorage=10),
                )

                NtClient.INSTANCE.nt_inst.getTable(PipelineHandler.NT_TABLE).getEntry(
                    topicName
                ).setInteger(sub.get())

                self.pipeline_subscribers[i] = sub

                log(f"Added listener for camera {i}, entry:{topic.getName()}")

                table.addListener(
                    key=topicName,
                    eventMask=EventFlags.kImmediate,
                    listener=keepCurrentPipelineUpdatedListener,
                )
            log("Set up settings successfully")
        else:
            err("NtClient instance is None")

    def getCameraTableName(self, index: int) -> str:
        return f"camera{index}"

    def loadSettings(self):
        import yaml

        log("Loading settings...")
        with open(r"./config/settings.yml") as file:
            settings = yaml.full_load(file)

            camera_configs = settings["global"]["camera_configs"]

            for camera_index in camera_configs:
                self.addCamera(camera_index)
                self.default_pipeline_indexes[camera_index] = camera_configs[
                    camera_index
                ]["default_pipeline"]

            pipelines = settings["pipelines"]

            for index, _ in enumerate(pipelines):
                pipeline = pipelines[index]

                log(f"Loaded pipeline #{index} with type {pipeline['type']}")

                self.setPipelineSettings(index, pipeline["settings"])

                self.pipeline_types[index] = pipeline["type"]

        for camera_index in self.cameras.keys():
            pipeline = self.default_pipeline_indexes[camera_index]
            self.setPipelineByIndex(
                camera_index=camera_index,
                pipeline_index=pipeline,
            )
            log(f"Setup default pipeline (#{pipeline}) for camera ({camera_index})")

        log("Loaded pipelines successfully")
        self.setupNetworkTables()

    @staticmethod
    def setCameraConfigs(
        settings: Dict[str, Any],
        camera: UsbCamera,
        brightness: int = 0,
        contrast: int = 12,
        saturation: int = 25,
        hue: int = 50,
        exposure: int = 120,
        gain: int = 31,
        sharpness: int = 0,
        white_balance_auto: bool = False,
        gain_auto: bool = False,
        horizontal_flip: bool = False,
        vertical_flip: bool = False,
        power_line_frequency: int = 0,  # Enum: 0 (Disabled), 1 (50Hz)
    ):
        camera.setVideoMode(
            fps=settings.get("fps", 30),
            pixelFormat=VideoMode.PixelFormat.kMJPEG,
            width=int(settings["width"]),
            height=int(settings["height"]),
        )
        # Set brightness
        camera.setBrightness(settings.get("brightness", brightness))

        # Set contrast
        camera.getProperty("contrast").set(settings.get("contrast", contrast))

        # Set saturation
        camera.getProperty("saturation").set(settings.get("saturation", saturation))

        # Set hue
        camera.getProperty("hue").set(settings.get("hue", hue))

        # Set exposure
        camera.setExposureManual(settings.get("exposure", exposure))

        # Set gain
        camera.getProperty("gain").set(settings.get("gain", gain))

        # Set sharpness
        camera.getProperty("sharpness").set(settings.get("sharpness", sharpness))

        # Set white balance (automatic or manual)
        if settings.get("white_balance_automatic", white_balance_auto):
            camera.setWhiteBalanceAuto()
        else:
            camera.setWhiteBalanceManual(
                settings.get("white_balance", 0)
            )  # Adjust based on manual value in settings

        autoGain = settings.get("gain_automatic", gain_auto)
        if "gain_automatic" in settings.keys():
            camera.getProperty("gain_automatic").set(autoGain)
        else:
            camera.getProperty("raw_gain").set(
                settings.get("raw_gain", 20)
            )  # Use raw gain for manual gain adjustment

        # Set horizontal flip
        camera.getProperty("horizontal_flip").set(
            settings.get("horizontal_flip", horizontal_flip)
        )

        # Set vertical flip
        camera.getProperty("vertical_flip").set(
            settings.get("vertical_flip", vertical_flip)
        )

        # Set power line frequency (0: Disabled, 1: 50Hz)
        camera.getProperty("power_line_frequency").set(
            settings.get("power_line_frequency", power_line_frequency)
        )

    def setPipelineSettings(
        self,
        pipeline_index: int,
        settings: PipelineSettings.PipelineSettingsMap,
    ):
        self.pipeline_settings[pipeline_index] = PipelineSettings(settings)

    def cleanup(self):
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()

        for sub in self.pipeline_subscribers.values():
            name = sub.getTopic().getName()
            sub.close()
            log(f"Close sub : {name}")

        log("Cleaned up all resources.")
