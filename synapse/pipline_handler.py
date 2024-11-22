import os
import importlib.util
import cv2
from typing import Any, List, Type, Dict, Union

from ntcore import Event, EventFlags
import ntcore

from ntcore._ntcore import (
    IntegerSubscriber,
    NetworkTable,
)

from synapse.nt_client import NtClient
from synapse.pipeline import Pipeline
from cscore import CameraServer, UsbCamera
import numpy as np
import time
from synapse.log import log
from synapse.pipeline_settings import PipelineSettings
import threading


class PipelineHandler:
    def __init__(self, directory: str):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param directory: Root directory to search for pipeline files
        """
        self.directory = directory

    def setup(self):
        self.pipelines = self.loadPipelines()
        self.cameras: List[UsbCamera] = []
        self.pipeline_map: Dict[int, Union[Type[Pipeline], List[Type[Pipeline]]]] = {}
        self.pipeline_instances: Dict[int, List[Pipeline]] = {}
        self.pipeline_settings: Dict[int, PipelineSettings] = {}
        self.default_pipeline_indexes: Dict[int, int] = {}
        self.pipeline_bindings: Dict[int, int] = {}
        self.pipeline_types: Dict[int, str] = {}
        self.pipeline_subscribers: Dict[int, IntegerSubscriber] = {}

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
                        log(
                            f"Error loading {file_path}: {e}"
                        )  # Consider using logging instead

        log("Loaded pipelines successfully")
        return pipelines

    def addCamera(self, camera_index: int) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.
        :param camera_index: Camera index to open
        """
        camera = CameraServer.startAutomaticCapture(camera_index)

        if camera.isConnected():
            self.cameras.append(camera)
            log(f"Camera {camera_index} added successfully.")
            return True
        else:
            log(f"Failed to open camera {camera_index}.")
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
                self.pipeline_settings[camera_index],
            )
            for pipeline_cls in pipeline
        ]

        for pipelines in self.pipeline_instances[camera_index]:
            if NtClient.INSTANCE is not None:
                setattr(
                    pipelines,
                    "nt_table",
                    NtClient.INSTANCE.nt_inst.getTable("Synapse"),
                )
            self.setCameraConfigs(pipeline_config.getMap(), self.cameras[camera_index])

        log(f"Set pipeline(s) for camera {camera_index}: {str(pipeline)}")

    def setPipelineByIndex(self, camera_index: int, pipeline_index: int):
        if camera_index not in range(len(self.cameras)):
            log(
                f"Error: Invalid camera_index {camera_index}. Must be in range(0, {len(self.cameras)-1})."
            )
            return

        if pipeline_index not in self.pipeline_types.keys():
            log(
                f"Error: Invalid pipeline_index {pipeline_index}. Must be one of {list(self.pipeline_types.keys())}."
            )
            self.setNTPipelineIndex(camera_index, self.pipeline_bindings[camera_index])
            return

        # If both indices are valid, proceed with the pipeline setting
        self.pipeline_bindings[camera_index] = pipeline_index

        log(f"Set pipeline #{pipeline_index} for camera ({camera_index})")

        self.setNTPipelineIndex(
            camera_index=camera_index, pipeline_index=pipeline_index
        )

        self.__setPipelineForCamera(
            camera_index=camera_index,
            pipeline=self.pipelines[self.pipeline_types[pipeline_index]],
            pipeline_config=self.pipeline_settings[pipeline_index],
        )

    def setNTPipelineIndex(self, camera_index: int, pipeline_index: int):
        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.nt_inst.getTable("Synapse").getEntry(
                f"camera{camera_index}pipeline"
            ).setInteger(pipeline_index)

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras in parallel.
        """
        try:
            sinks = [CameraServer.getVideo(camera) for camera in self.cameras]
            log("Set up sinks array")
            frame_buffers = [
                np.zeros((600, 600, 3), dtype=np.uint8) for _ in self.cameras
            ]

            log("Set up frame buffers")

            outputs = [
                CameraServer.putVideo(f"Camera {i} output", 600, 600)
                for i in range(len(self.cameras))
            ]

            log("Set up outputs array")

            def process_camera(index):
                sink = sinks[index]
                frame_buffer = frame_buffers[index]
                output = outputs[index]

                while True:
                    start_time = time.time()  # Start time for FPS calculation
                    ret, frame = sink.grabFrame(frame_buffer)

                    if ret == 0 or frame is None:
                        continue

                    # Retrieve the pipeline instances for the current camera
                    assigned_pipelines = self.pipeline_instances.get(index, [])
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

                    for i in range(len(self.cameras)):
                        if NtClient.INSTANCE is not None:
                            entry = NtClient.INSTANCE.nt_inst.getTable(
                                "Synapse"
                            ).getEntry(f"camera{i}pipeline")

                            pipeline = entry.getInteger(None)

                            # print(f"pipeline: {pipeline}, entry : {entry.getName()}")

                            if (
                                pipeline != self.pipeline_bindings[i]
                                and pipeline is not None
                            ):
                                self.setPipelineByIndex(i, pipeline)

            # Create and start a thread for each camera
            threads = []
            for i in range(len(self.cameras)):
                thread = threading.Thread(target=process_camera, args=(i,))
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

        def addCurrentPipelineListener(table: NetworkTable, key: str, _: Event) -> None:
            index = int(key.replace("camera", "").replace("pipeline", ""))
            self.setPipelineByIndex(
                camera_index=index,
                pipeline_index=table.getEntry(key).getInteger(
                    defaultValue=self.default_pipeline_indexes[index]
                ),
            )

        if NtClient.INSTANCE is not None:
            inst = NtClient.INSTANCE.server or NtClient.INSTANCE.nt_inst

            table: NetworkTable = inst.getTable("Synapse")

            for i, _ in enumerate(self.cameras):
                topic = inst.getTable("Synapse").getIntegerTopic(f"camera{i}pipeline")

                pub = topic.publish(ntcore.PubSubOptions(keepDuplicates=True))
                pub.setDefault(self.pipeline_bindings[i])

                sub = topic.subscribe(
                    0, ntcore.PubSubOptions(keepDuplicates=True, pollStorage=10)
                )

                NtClient.INSTANCE.nt_inst.getTable("Synapse").getEntry(
                    f"camera{i}pipeline"
                ).setInteger(sub.get())

                self.pipeline_subscribers[i] = sub

                log(f"Added listener for camera {i}, entry:{topic.getName()}")

                table.addListener(
                    key=f"camera{i}pipeline",
                    eventMask=EventFlags.kImmediate,
                    listener=addCurrentPipelineListener,
                )
            log("Set up settings successfully")
        else:
            log("Error: NtClient instance is None")

    def loadSettings(self):
        import yaml

        log("Loading settings...")
        with open(r"./config/settings.yml") as file:
            settings = yaml.full_load(file)

            camera_configs = settings["camera_configs"]

            for config in camera_configs:
                self.default_pipeline_indexes[config] = camera_configs[config][
                    "default_pipeline"
                ]

            pipelines = settings["pipelines"]

            for index, _ in enumerate(pipelines):
                pipeline = pipelines[index]

                log(f"Loaded pipeline #{index} with type {pipeline['type']}")

                self.setPipelineSettings(index, pipeline["settings"])

                self.pipeline_types[index] = pipeline["type"]

        for camera_index in range(len(self.cameras)):
            pipeline = self.default_pipeline_indexes[camera_index]
            self.setPipelineByIndex(
                camera_index=camera_index,
                pipeline_index=pipeline,
            )
            log(f"Setup default pipeline (#{pipeline}) for camera ({camera_index})")

        log("Loaded pipelines successfully")
        self.setupNetworkTables()

    def setCameraConfigs(self, settings: Dict[str, Any], camera: UsbCamera):
        camera.setBrightness(settings.get("brightness", 100))
        default_width = 1920
        default_height = 1080

        camera.setResolution(
            settings.get("width", default_width), settings.get("height", default_height)
        )

    def setPipelineSettings(self, camera_index: int, settings):
        self.pipeline_settings[camera_index] = PipelineSettings(settings)

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
