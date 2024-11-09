import os
import importlib.util
import cv2
from typing import Any, List, Type, Dict, Union
from synapse.pipeline import Pipeline
from cscore import CameraServer, UsbCamera
import numpy as np
import time  # Import time for FPS calculation
from synapse.log import log
from synapse.pipeline_settings import PipelineSettings


class PipelineHandler:
    def __init__(self, directory: str):
        """
        Initializes the handler, loads all pipeline classes in the specified directory.
        :param directory: Root directory to search for pipeline files
        """
        self.directory = directory
        self.pipelines = self.load_pipelines()
        self.cameras: List[UsbCamera] = []
        self.pipeline_map: Dict[int, Union[Type[Pipeline], List[Type[Pipeline]]]] = {}
        self.pipeline_instances: Dict[int, List[Pipeline]] = {}
        self.pipeline_settings: Dict[int, PipelineSettings] = {}

    def load_pipelines(self) -> Dict[str, Type[Pipeline]]:
        """
        Loads all classes that extend Pipeline from Python files in the directory.
        :return: A dictionary of Pipeline subclasses
        """
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
                                    pipelines[cls.__name__] = cls
                    except Exception as e:
                        log(
                            f"Error loading {file_path}: {e}"
                        )  # Consider using logging instead
        return pipelines

    def add_camera(self, camera_index: int) -> bool:
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

    def set_pipeline_for_camera_by_name(self, camera_index: int, pipline_name: str):
        pipeline = self.pipelines.get(pipline_name, None)

        if pipeline is None:
            log(
                f'Invalid pipeline name "{pipline_name}", avilable options are: {list(self.pipelines.keys())}'
            )
            return

        self.set_pipeline_for_camera(camera_index, pipeline)

    def set_pipeline_for_camera(
        self, camera_index: int, pipeline: Union[Type[Pipeline], List[Type[Pipeline]]]
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
            pipeline_cls(self.pipeline_settings[camera_index])
            for pipeline_cls in pipeline
        ]
        log(f"Set pipeline(s) for camera {camera_index}: {pipeline}")

    def switch_pipeline_at_runtime(
        self, camera_index: int, pipeline: Union[Type[Pipeline], List[Type[Pipeline]]]
    ):
        """
        Allows switching the pipeline for a specific camera at runtime.
        :param camera_index: Index of the camera to update
        :param pipeline: A new pipeline or list of pipelines to assign to the camera
        """
        self.set_pipeline_for_camera(camera_index, pipeline)
        log(f"Switched pipeline(s) for camera {camera_index} at runtime.")

    def run(self):
        """
        Runs the assigned pipelines on each frame captured from the cameras.
        """
        try:
            sinks = [CameraServer.getVideo(camera) for camera in self.cameras]
            frame_buffers = [
                np.zeros((600, 600, 3), dtype=np.uint8) for _ in self.cameras
            ]
            outputs = [
                CameraServer.putVideo(f"Camera {i} output", 600, 600)
                for i in range(len(self.cameras))
            ]

            while True:
                for i, sink in enumerate(sinks):
                    start_time = time.time()  # Start time for FPS calculation

                    ret, frame = sink.grabFrame(frame_buffers[i])

                    if ret == 0 or frame is None:
                        continue

                    # Retrieve the pipeline instances for the current camera
                    assigned_pipelines = self.pipeline_instances.get(i, [])
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
                        outputs[i].putFrame(processed_frame)
        finally:
            self.cleanup()

    def load_settings(self):
        import yaml

        with open(r"./internal_files/settings.yml") as file:
            settings = yaml.full_load(file)
            pipeline_settings = settings["pipeline_settings"]

            for index, camera in enumerate(self.cameras):
                self.set_pipeline_settings(index, pipeline_settings[index]["settings"])
                self.set_pipeline_for_camera_by_name(
                    index, pipline_name=pipeline_settings[index]["type"]
                )
                self.set_camera_configs(settings, camera)

    def set_camera_configs(self, settings: Dict[str, Any], camera: UsbCamera):
        camera.setBrightness(settings.get("brightness", 100))
        # TODO: more configs

    def set_pipeline_settings(self, camera_index: int, settings):
        self.pipeline_settings[camera_index] = PipelineSettings(settings)

    def cleanup(self):
        """
        Releases all cameras and closes OpenCV windows.
        """
        cv2.destroyAllWindows()
        log("Cleaned up all resources.")
