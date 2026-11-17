# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""YOLO object-detection pipeline.

The pipeline works with any Ultralytics-compatible detection model. Class names
come from the model itself, so nothing in the pipeline is tied to a specific
model or class set.

The pipeline is optional because PyTorch and Ultralytics are large
dependencies. Install them with::

    pip install "synapsefrc[yolo]"

The model is selected from the pipeline settings. Its value is stored relative
to the Synapse project root, so the same path works in the UI file browser and
on the processor. Models are loaded when the pipeline starts and reloaded when
the setting changes. If the model is missing or cannot be loaded, the pipeline
keeps publishing results with an explanatory ``error`` instead of interrupting
the camera stream.

Position estimation needs an approximate physical size for each class. The
``default_object_width`` and ``default_object_height`` settings cover classes
without a specific entry. To improve accuracy, select an
``object_dimensions_file`` containing a JSON object keyed by class name::

    {
      "coral": {"width": 0.30, "height": 0.30},
      "person": {"width": 0.45, "height": 1.70},
      "sports ball": [0.22, 0.22]
    }

Invalid entries are ignored and reported in the log.
"""

import importlib
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import synapse.log as log
from synapse import Pipeline, PipelineSettings
from synapse.core.camera.synapse_camera import SynapseCamera
from synapse.core.config import Config
from synapse.core.settings_api import (
    BooleanConstraint,
    FileConstraint,
    NumberConstraint,
    Setting,
    SettingsValue,
    settingField,
)
from synapse.pipelines.neural.constants import (
    DEFAULT_OBJECT_HEIGHT,
    DEFAULT_OBJECT_WIDTH,
    NeuralDetection,
    NeuralResult,
    ObjectSize,
)
from synapse.pipelines.neural.position_estimator import (
    PositionEstimator,
    PositionEstimatorConfig,
    parseObjectDimensions,
)
from synapse.stypes import CameraID, Frame, Resolution

# Bundled example model. Any Ultralytics-compatible model can be selected
# through the model_file setting instead.
DEFAULT_MODEL_PATH = "config/models/coralAlgae-640-640-yolov8s.pt"


def _hasOptionalDependencies() -> bool:
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("ultralytics") is not None
    )


def _projectRoot() -> Path:
    """Resolve file setting values against the Synapse project root."""
    try:
        return Config.getInstance().path.parent.parent.resolve()
    except (AttributeError, TypeError, OSError):
        return Path.cwd().resolve()


_YOLO_AVAILABLE = _hasOptionalDependencies()


class YOLOSettings(PipelineSettings):
    model_file = settingField(
        FileConstraint(path="config/models", fileTypes=["pt", "onnx", "engine"]),
        default=DEFAULT_MODEL_PATH,
        description="Object detection model file (.pt, .onnx, or .engine)",
        category="Model",
    )
    confidence_threshold = settingField(
        NumberConstraint(0.0, 1.0, 0.01),
        default=0.3,
        description="Minimum detection confidence",
        category="Model",
    )
    iou_threshold = settingField(
        NumberConstraint(0.0, 1.0, 0.01),
        default=0.45,
        description="Non-maximum suppression IoU threshold",
        category="Model",
    )

    object_dimensions_file = settingField(
        FileConstraint(path="config/models", fileTypes=["json"]),
        default="",
        description=(
            "Optional JSON file mapping class names to object sizes in meters. "
            "Classes without an entry use the default size below."
        ),
        category="Object Size",
    )
    default_object_width = settingField(
        NumberConstraint(0.0, None, 0.01),
        default=DEFAULT_OBJECT_WIDTH,
        description="Assumed object width (meters) for classes without an entry",
        category="Object Size",
    )
    default_object_height = settingField(
        NumberConstraint(0.0, None, 0.01),
        default=DEFAULT_OBJECT_HEIGHT,
        description="Assumed object height (meters) for classes without an entry",
        category="Object Size",
    )

    min_bbox_area = settingField(
        NumberConstraint(0.0, None, 1.0),
        default=100.0,
        description="Ignore detections smaller than this pixel area",
        category="Filtering",
    )
    min_distance = settingField(
        NumberConstraint(0.0, None, 0.1),
        default=0.1,
        description="Minimum estimated distance in meters",
        category="Filtering",
    )
    max_distance = settingField(
        NumberConstraint(0.0, None, 0.1),
        default=50.0,
        description="Maximum estimated distance in meters",
        category="Filtering",
    )
    max_reprojection_error = settingField(
        NumberConstraint(0.0, None, 1.0),
        default=50.0,
        description="Maximum reprojection error for a valid 3D estimate",
        category="Filtering",
    )

    draw_detections = settingField(
        BooleanConstraint(),
        default=True,
        description="Draw detection boxes and labels on the camera feed",
        category="Display",
    )
    debug_logging = settingField(
        BooleanConstraint(),
        default=False,
        description="Log detection timing and counts",
        category="Display",
    )

    camera_x = settingField(
        NumberConstraint(),
        default=0.0,
        description="Camera X position on the field (meters)",
        category="Camera Pose",
    )
    camera_y = settingField(
        NumberConstraint(),
        default=0.0,
        description="Camera Y position on the field (meters)",
        category="Camera Pose",
    )
    camera_z = settingField(
        NumberConstraint(),
        default=1.0,
        description="Camera Z position on the field (meters)",
        category="Camera Pose",
    )
    camera_roll = settingField(
        NumberConstraint(-180.0, 180.0, 1.0),
        default=0.0,
        description="Camera roll (degrees)",
        category="Camera Pose",
    )
    camera_pitch = settingField(
        NumberConstraint(-180.0, 180.0, 1.0),
        default=0.0,
        description="Camera pitch (degrees, positive tilts down)",
        category="Camera Pose",
    )
    camera_yaw = settingField(
        NumberConstraint(-180.0, 180.0, 1.0),
        default=0.0,
        description="Camera yaw (degrees, counter-clockwise from +X)",
        category="Camera Pose",
    )


class YOLOPipeline(Pipeline[YOLOSettings, NeuralResult]):
    """Object detection and approximate 3D localization for any Ultralytics model.

    Developed in partnership with Team #4744 Ninjas.
    """

    __is_enabled__ = _YOLO_AVAILABLE

    def __init__(self, settings: YOLOSettings):
        super().__init__(settings)
        self.settings: YOLOSettings = settings

        self.model: Optional[Any] = None
        self._modelName = ""
        self._modelError = "Model has not been loaded"
        self._loadedModelValue: Optional[str] = None
        self._device = "cpu"

        self._objectDimensions: Dict[str, ObjectSize] = {}
        self._loadedDimensionsValue: Optional[str] = None

        self._cameraMatrix = np.eye(3, dtype=np.float64)
        self._distCoeffs = np.zeros(5, dtype=np.float64)
        self._calibResolution: Resolution = (640, 480)
        self._loadObjectDimensions()
        self.poseEstimator = PositionEstimator(self._poseEstimatorConfig())

        self._loadModel()

    def _poseEstimatorConfig(self) -> PositionEstimatorConfig:
        return PositionEstimatorConfig(
            cameraMatrix=self._cameraMatrix,
            distCoeffs=self._distCoeffs,
            calibResolution=self._calibResolution,
            minDistance=float(self.getSetting(self.settings.min_distance)),
            maxDistance=float(self.getSetting(self.settings.max_distance)),
            minBboxArea=float(self.getSetting(self.settings.min_bbox_area)),
            maxReprojectionError=float(
                self.getSetting(self.settings.max_reprojection_error)
            ),
            objectDimensions=dict(self._objectDimensions),
            defaultObjectWidth=float(
                self.getSetting(self.settings.default_object_width)
            ),
            defaultObjectHeight=float(
                self.getSetting(self.settings.default_object_height)
            ),
        )

    def _refreshCameraCalibration(self) -> None:
        matrix = self.getCameraMatrix(self.cameraIndex)
        self._cameraMatrix = (
            np.array(matrix, dtype=np.float64)
            if matrix
            else np.eye(3, dtype=np.float64)
        )

        coeffs = self.getDistCoeffs(self.cameraIndex)
        self._distCoeffs = (
            np.array(coeffs, dtype=np.float64)
            if coeffs
            else np.zeros(5, dtype=np.float64)
        )

        self._calibResolution = self.getResolution()
        self.poseEstimator.setConfig(self._poseEstimatorConfig())

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        super().bind(cameraIndex, camera)
        self._refreshCameraCalibration()

    def close(self) -> None:
        self.model = None
        self._modelError = "Pipeline closed"
        super().close()

    def _currentModelValue(self) -> str:
        value = self.getSetting(self.settings.model_file)
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _resolveProjectPath(value: str) -> Optional[Path]:
        value = value.strip()
        if not value:
            return None

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = _projectRoot() / path
        return path

    def _modelPath(self) -> Optional[Path]:
        return self._resolveProjectPath(self._currentModelValue())

    def _currentDimensionsValue(self) -> str:
        value = self.getSetting(self.settings.object_dimensions_file)
        return value.strip() if isinstance(value, str) else ""

    def _dimensionsPath(self) -> Optional[Path]:
        return self._resolveProjectPath(self._currentDimensionsValue())

    def _loadObjectDimensions(self) -> None:
        self._loadedDimensionsValue = self._currentDimensionsValue()
        self._objectDimensions = {}

        path = self._dimensionsPath()
        if path is None:
            return

        if not path.is_file():
            log.err(f"Object dimensions file not found: {path}")
            return

        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
            dimensions = parseObjectDimensions(data)
        except (OSError, ValueError) as error:
            log.err(f"Failed to load object dimensions from '{path.name}': {error}")
            return

        if isinstance(data, dict) and len(dimensions) != len(data):
            log.warn(
                f"Ignored {len(data) - len(dimensions)} invalid object "
                f"dimension entries in '{path.name}'"
            )

        self._objectDimensions = dimensions
        log.info(
            f"Loaded object dimensions for {len(dimensions)} class(es) "
            f"from '{path.name}'"
        )

    @staticmethod
    def _createModel(ultralyticsModule: Any, path: Path) -> Any:
        """Load a model through Ultralytics, including non-YOLO detectors."""
        modelClass = getattr(ultralyticsModule, "YOLO")
        try:
            return modelClass(str(path))
        except Exception as yoloError:
            rtdetrClass = getattr(ultralyticsModule, "RTDETR", None)
            if rtdetrClass is None:
                raise
            log.warn(
                f"YOLO loader failed for '{path.name}' ({yoloError}); "
                "retrying with RTDETR"
            )
            return rtdetrClass(str(path))

    def _loadModel(self) -> None:
        self.model = None
        self._modelName = ""
        self._loadedModelValue = self._currentModelValue()

        path = self._modelPath()
        if path is None:
            self._modelError = "No model file selected"
            log.warn("Object detection model file is not set")
            return

        if not path.is_file():
            self._modelError = f"Model file not found: {path.name}"
            log.err(f"Object detection model file not found: {path}")
            return

        try:
            torchModule: Any = importlib.import_module("torch")
            ultralyticsModule: Any = importlib.import_module("ultralytics")
        except ImportError as error:
            self._modelError = f"Missing optional dependency: {error}"
            log.err(
                "Object detection dependencies are not installed. "
                'Install them with: pip install "synapsefrc[yolo]"'
            )
            return

        try:
            self._device = "cuda:0" if torchModule.cuda.is_available() else "cpu"
            log.info(
                f"Loading object detection model '{path.name}' on {self._device}..."
            )
            start = time.perf_counter()
            model = self._createModel(ultralyticsModule, path)

            names = model.names
            if not names:
                raise RuntimeError("model does not define any class names")

            self.model = model
            self._modelName = path.name
            self._modelError = ""
            elapsed = time.perf_counter() - start
            log.info(
                f"Object detection model loaded in {elapsed:.2f}s "
                f"({len(names)} classes) on {self._device}"
            )
        except Exception as error:
            self.model = None
            self._modelError = str(error)
            log.err(f"Failed to load object detection model '{path.name}': {error}")

    def _className(self, classId: int) -> str:
        if self.model is None:
            return str(classId)

        names = self.model.names
        if isinstance(names, dict):
            name = names.get(classId)
            if name is None:
                name = names.get(str(classId), classId)
            return str(name)
        if isinstance(names, (list, tuple)) and 0 <= classId < len(names):
            return str(names[classId])
        return str(classId)

    def _cameraPose(self) -> Dict[str, float]:
        return {
            "x": float(self.getSetting(self.settings.camera_x)),
            "y": float(self.getSetting(self.settings.camera_y)),
            "z": float(self.getSetting(self.settings.camera_z)),
            "roll": math.radians(float(self.getSetting(self.settings.camera_roll))),
            "pitch": math.radians(float(self.getSetting(self.settings.camera_pitch))),
            "yaw": math.radians(float(self.getSetting(self.settings.camera_yaw))),
        }

    def detect_objects(self, frame: Frame) -> List[NeuralDetection]:
        """Run the model and estimate a position for every detection."""
        if self.model is None:
            return []

        image = np.asarray(frame)
        start = time.perf_counter()
        try:
            results = self.model(
                image,
                conf=float(self.getSetting(self.settings.confidence_threshold)),
                iou=float(self.getSetting(self.settings.iou_threshold)),
                device=self._device,
                verbose=False,
            )
        except Exception as error:
            # A failed inference should not take down the camera stream. Drop the
            # model so the error is published once instead of on every frame.
            self.model = None
            self._modelName = ""
            self._modelError = f"Inference failed: {error}"
            log.err(f"Object detection inference failed: {error}")
            return []

        minArea = float(self.getSetting(self.settings.min_bbox_area))
        cameraPose = self._cameraPose()
        detections: List[NeuralDetection] = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            coordinates = boxes.xyxy.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()
            classes = boxes.cls.cpu().numpy().astype(int)

            for (x1, y1, x2, y2), confidence, classId in zip(
                coordinates, confidences, classes
            ):
                bbox = (float(x1), float(y1), float(x2), float(y2))
                bboxArea = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
                if bboxArea < minArea:
                    continue

                detection = NeuralDetection(
                    className=self._className(int(classId)),
                    x=(bbox[0] + bbox[2]) / 2.0,
                    y=(bbox[1] + bbox[3]) / 2.0,
                    confidence=float(confidence),
                    bbox=bbox,
                )
                detection.position3D = self.poseEstimator.estimate3DPosition(
                    detection, cameraPose, frameShape=image.shape
                )
                detections.append(detection)

        if bool(self.getSetting(self.settings.debug_logging)):
            elapsed = (time.perf_counter() - start) * 1000.0
            log.info(f"Detected {len(detections)} object(s) in {elapsed:.1f}ms")

        return detections

    def draw_detections(self, frame: Frame, detections: List[NeuralDetection]) -> Frame:
        """Draw detection boxes, labels, and estimated distances."""
        display = np.asarray(frame).copy()

        for detection in detections:
            x1, y1, x2, y2 = (int(value) for value in detection.bbox)

            if detection.confidence > 0.8:
                color = (0, 255, 0)
            elif detection.confidence > 0.6:
                color = (0, 255, 255)
            else:
                color = (0, 165, 255)

            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

            label = f"{detection.className}: {detection.confidence:.2f}"
            position = detection.position3D
            if position is not None:
                label += f" | {position.distance:.2f}m"

            cv2.putText(
                display,
                label,
                (x1, max(y1 - 8, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

            if position is not None:
                cv2.putText(
                    display,
                    f"Field: ({position.fieldX:.2f}, {position.fieldY:.2f})",
                    (x1, max(y1 - 24, 24)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1,
                )

        return display

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        if setting.key == self.settings.model_file.key:
            newValue = value.strip() if isinstance(value, str) else ""
            if newValue == self._loadedModelValue:
                return
            log.info("Model setting changed; reloading...")
            self._loadModel()
            return

        if setting.key == self.settings.object_dimensions_file.key:
            newValue = value.strip() if isinstance(value, str) else ""
            if newValue == self._loadedDimensionsValue:
                return
            log.info("Object dimensions setting changed; reloading...")
            self._loadObjectDimensions()
            self.poseEstimator.setConfig(self._poseEstimatorConfig())
            return

        if setting.key in {
            self.settings.min_distance.key,
            self.settings.max_distance.key,
            self.settings.min_bbox_area.key,
            self.settings.max_reprojection_error.key,
            self.settings.default_object_width.key,
            self.settings.default_object_height.key,
        }:
            self.poseEstimator.setConfig(self._poseEstimatorConfig())

    def processFrame(self, img, timestamp: float) -> Frame:
        if self.getResolution() != self._calibResolution:
            self._refreshCameraCalibration()

        detections = self.detect_objects(img)
        self.setResults(
            NeuralResult(
                detections=detections,
                model=self._modelName,
                error=self._modelError,
            )
        )

        if detections and bool(self.getSetting(self.settings.draw_detections)):
            return self.draw_detections(img, detections)

        return img
