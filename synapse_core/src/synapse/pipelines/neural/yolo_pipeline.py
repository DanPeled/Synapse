# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from pathlib import Path
from typing import List

import cv2
import numpy as np
import synapse.log as log
import torch
from synapse.core.pipeline import (CameraSettings, Pipeline, PipelineSettings,
                                   Setting, SettingsValue, SynapseCamera)
from synapse.core.settings_api import (BooleanConstraint, NumberConstraint,
                                       StringConstraint, settingField)
from synapse.pipelines.neural.constants import (DEFAULT_CAMERA_POSITION,
                                                NeuralDetection, NeuralResult)
from synapse.pipelines.neural.position_estimator import (
    PositionEstimator, PositionEstimatorConfig)
from synapse.stypes import CameraID, Frame
from ultralytics import YOLO

YOLO_MODEL_PATH = "coralAlgae-640-640-yolov8s.pt"


class YOLOSettings(PipelineSettings):
    yolo_model_path = settingField(
        StringConstraint(minLength=0, maxLength=None), default=YOLO_MODEL_PATH
    )
    yolo_confidence = settingField(
        NumberConstraint(minValue=0, maxValue=1), default=0.3
    )
    yolo_iou_threshold = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=0.45
    )

    min_confidence = settingField(NumberConstraint(minValue=0, maxValue=1), default=0.3)
    min_bbox_area = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=100
    )
    max_distance = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=50.0
    )
    min_distance = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=0.1
    )
    min_reprojection_error = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=100.0
    )

    debug_logging = settingField(BooleanConstraint(), default=True)


class ProcessingDevice(Enum):
    cuda = "cuda"
    cpu = "cpu"


class YOLOPipeline(Pipeline[YOLOSettings, NeuralResult]):
    """
    Developed in partnership with Team #4744 Ninjas
    """

    def setupModel(self, settings: YOLOSettings):
        log.log(f"Loading YOLO model: {settings.getSetting(settings.yolo_model_path)}")

        if not Path.exists(
            Path.cwd() / self.settings.getSetting(self.settings.yolo_model_path)
        ):
            log.log(
                f"Model not found. Downloading {self.getSetting(self.settings.yolo_model_path)}..."
            )

        try:
            self.yolo_model = YOLO(settings.getSetting(settings.yolo_model_path))
            self.yolo_model.to(self.device.value)

            if self.yolo_model.names is None:
                log.err("Yolo Model Names are None!!")
                raise Exception("Yolo Model Names are None!!")
            else:
                log.log(
                    f"YOLO model loaded successfully on {self.device.value.upper()}!"
                )
                log.log(f"Model can detect: {list(self.yolo_model.names.values())}")
        except Exception as e:
            log.err(f"Error loading YOLO model: {e}")
            log.log("Trying to download fresh model...")
            self.yolo_model = YOLO(settings.getSetting(settings.yolo_model_path))
            self.yolo_model.to(self.device.value)

    def __init__(self, settings: YOLOSettings):
        super().__init__(settings)

        log.log(f"Is Cuda enabled {torch.cuda.is_available()}")  # Should log.log True
        if torch.cuda.is_available():
            log.log(torch.cuda.get_device_name(0))

        self.camera_matrix = np.array(self.getCameraMatrix(self.cameraIndex)) or np.eye(
            3, 3
        )
        self.dist_coeffs = np.array(self.getDistCoeffs(self.cameraIndex)) or np.zeros(5)

        self.device = ProcessingDevice.cpu
        if torch.cuda.is_available():
            self.device = ProcessingDevice.cuda

        self.config = PositionEstimatorConfig(
            self.camera_matrix,
            self.dist_coeffs,
            self.getResolution(),
            self.getSetting(self.settings.min_distance),
            self.getSetting(self.settings.max_distance),
            self.getSetting(self.settings.min_bbox_area),
        )
        self.pose_estimator = PositionEstimator(self.config)

        self.setupModel(settings)

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        super().bind(cameraIndex, camera)
        self.camera_matrix = np.array(self.getCameraMatrix(self.cameraIndex)) or np.eye(
            3, 3
        )
        self.dist_coeffs = np.array(self.getDistCoeffs(self.cameraIndex)) or np.zeros(5)

    def detect_objects(
        self, frame: Frame, camera_position: dict
    ) -> List[NeuralDetection]:
        """Detect objects and estimate their 3D positions."""
        results = self.yolo_model(
            frame,
            conf=self.getSetting(self.settings.yolo_confidence),
            iou=self.getSetting(self.settings.yolo_iou_threshold),
            device=self.device.value,
            verbose=False,
        )

        detections = []

        for result in results:
            boxes = result.boxes

            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                cls = int(box.cls[0].cpu().numpy())
                if self.yolo_model.names is None:
                    return []
                class_name = self.yolo_model.names[cls]

                # Filter by confidence
                if conf < self.getSetting(self.settings.min_confidence):
                    continue

                # Filter by bbox area
                bbox_area = (x2 - x1) * (y2 - y1)
                if bbox_area < self.getSetting(self.settings.min_bbox_area):
                    continue

                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                detection = NeuralDetection(
                    class_name,
                    float(center_x),
                    float(center_y),
                    conf,
                    (float(x1), float(y1), float(x2), float(y2)),
                    None,
                )

                # Estimate 3D position using camera pose from PhotonVision
                position_3d = self.pose_estimator.estimate3DPosition(
                    detection, camera_position, frameShape=frame.shape
                )

                if position_3d is not None:
                    detection.position3D = position_3d
                    detections.append(detection)

        return detections

    def draw_detections(
        self, frame: Frame, yolo_results: List[NeuralDetection]
    ) -> Frame:
        """Draw detections with 3D position info."""
        display_frame = frame.copy()

        for detection in yolo_results:
            bbox = detection.bbox
            x1, y1, x2, y2 = map(int, bbox)

            # Color based on confidence
            confidence = detection.confidence

            if confidence > 0.8:
                color = (0, 255, 0)  # Green - high confidence
            elif confidence > 0.6:
                color = (0, 255, 255)  # Yellow - medium confidence
            else:
                color = (0, 165, 255)  # Orange - lower confidence

            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)

            # Draw label
            label = f"{detection.className}: {detection.confidence:.2f}"

            if detection.position3D is not None:
                pos = detection.position3D
                label += f" | {pos.distance:.2f}m"
                label2 = f"Field: ({pos.fieldY:.2f})"
                label3 = f"Q:{pos.qualityScore:.2f}"

                cv2.putText(
                    display_frame,
                    label,
                    (x1, y1 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )
                cv2.putText(
                    display_frame,
                    label2,
                    (x1, y1 - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1,
                )
                cv2.putText(
                    display_frame,
                    label3,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    color,
                    1,
                )
            else:
                cv2.putText(
                    display_frame,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

        return display_frame

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        if setting.key == self.settings.yolo_model_path.key:
            log.warn("Model changed, reloading....")
            self.setupModel(self.settings)

        elif setting.key in [
            self.settings.min_distance.key,
            self.settings.max_distance.key,
            self.settings.min_bbox_area.key,
            CameraSettings.resolution.key,
        ]:
            cfg = self.config

            cfg.cameraMatrix = self.camera_matrix
            cfg.distCoeffs = self.dist_coeffs
            cfg.calibResolution = self.getResolution()
            cfg.minDistance = self.getSetting(self.settings.min_distance)
            cfg.maxDistance = self.getSetting(self.settings.max_distance)
            cfg.minBboxArea = self.getSetting(self.settings.min_bbox_area)

            self.config = cfg
            self.pose_estimator.setConfig(cfg)

    def processFrame(self, img, timestamp: float) -> Frame:
        detections = self.detect_objects(
            img, DEFAULT_CAMERA_POSITION
        )  # TODO: get camera pose
        if len(detections) > 0:
            drawn = self.draw_detections(img, detections)

            self.setResults(NeuralResult(detections))

            return drawn

        return img
