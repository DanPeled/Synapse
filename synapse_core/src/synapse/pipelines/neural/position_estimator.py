# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from synapse.core.camera_factory import Resolution
from synapse.pipelines.neural.constants import (OBJECT_DIMENSIONS, CameraFrame,
                                                NeuralDetection,
                                                PositionEstimate)


# ---------- Config Dataclass ----------
@dataclass
class PositionEstimatorConfig:
    cameraMatrix: np.ndarray
    distCoeffs: np.ndarray
    calibResolution: Resolution  # (width, height)
    minDistance: float
    maxDistance: float
    minBboxArea: float


# ---------- Main Estimator ----------
class PositionEstimator:
    def __init__(self, config: PositionEstimatorConfig):
        self.config = config
        self._baseCameraMatrix = config.cameraMatrix.copy()
        self._cameraMatrix = config.cameraMatrix.copy()
        self._currentResolution: Optional[Resolution] = None

    def setConfig(self, config: PositionEstimatorConfig) -> None:
        self.config = config
        self._baseCameraMatrix = config.cameraMatrix.copy()
        self._cameraMatrix = config.cameraMatrix.copy()
        self._currentResolution = None

    # ---------- Resolution Handling ----------
    def updateForResolution(self, resolution: Resolution) -> None:
        if resolution == self._currentResolution:
            return

        width, height = resolution
        calibW, calibH = self.config.calibResolution

        scaleX = width / calibW
        scaleY = height / calibH

        self._cameraMatrix = self._baseCameraMatrix.copy()
        self._cameraMatrix[0, 0] *= scaleX
        self._cameraMatrix[1, 1] *= scaleY
        self._cameraMatrix[0, 2] *= scaleX
        self._cameraMatrix[1, 2] *= scaleY

        self._currentResolution = resolution

    # ---------- Geometry Helpers ----------
    @staticmethod
    def _objectPoints(dimensions: Dict[str, float]) -> np.ndarray:
        halfW = dimensions["width"] / 2
        halfH = dimensions["height"] / 2
        return np.array(
            [
                [-halfW, -halfH, 0],
                [halfW, -halfH, 0],
                [halfW, halfH, 0],
                [-halfW, halfH, 0],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _imagePoints(bbox: Tuple[float, float, float, float]) -> np.ndarray:
        x1, y1, x2, y2 = bbox
        return np.array([[x1, y2], [x2, y2], [x2, y1], [x1, y1]], dtype=np.float32)

    @staticmethod
    def _bboxArea(bbox: Tuple[float, float, float, float]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, (x2 - x1) * (y2 - y1))

    # ---------- Core Math ----------
    def _solvePnP(self, objectPoints, imagePoints):
        return cv2.solvePnP(
            objectPoints,
            imagePoints,
            self._cameraMatrix,
            self.config.distCoeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )

    def _reprojectionError(self, objectPoints, imagePoints, rvec, tvec) -> float:
        projected, _ = cv2.projectPoints(
            objectPoints, rvec, tvec, self._cameraMatrix, self.config.distCoeffs
        )
        projected = projected.reshape(-1, 2)
        return float(np.mean(np.linalg.norm(projected - imagePoints, axis=1)))

    # ---------- Coordinate Transforms ----------
    @staticmethod
    def _cameraToField(
        tvec, cameraPose: Dict[str, float]
    ) -> Tuple[float, float, float, CameraFrame]:
        camX, camY, camZ = tvec.flatten()

        yaw = cameraPose["yaw"]
        pitch = cameraPose["pitch"]

        cosP, sinP = np.cos(pitch), np.sin(pitch)
        camY_Pitched = camY * cosP - camZ * sinP
        camZ_Pitched = camY * sinP + camZ * cosP

        cosY, sinY = np.cos(yaw), np.sin(yaw)
        fieldX = camZ_Pitched * cosY + camX * sinY
        fieldY = camZ_Pitched * sinY - camX * cosY
        fieldZ = cameraPose["z"] - camY_Pitched

        cameraFrame = CameraFrame(camX, camY, camZ)
        return fieldX, fieldY, fieldZ, cameraFrame

    # ---------- Quality Scoring ----------
    def _qualityScore(self, confidence, bboxArea, distance, reprojectionError) -> float:
        sizeScore = min(bboxArea / 50_000, 1.0)
        distanceScore = max(0.0, 1.0 - distance / self.config.maxDistance)
        reprojScore = max(0.0, 1.0 - reprojectionError / 50.0)

        return (
            confidence * 0.4 + reprojScore * 0.3 + sizeScore * 0.2 + distanceScore * 0.1
        )

    # ---------- Public API ----------
    def estimate3DPosition(
        self,
        detection: NeuralDetection,
        cameraPose: Dict[str, float],
        frameShape: Optional[np.ndarray] = None,
    ) -> Optional[PositionEstimate]:
        """Estimate 3D position from detection."""
        if frameShape is not None:
            height, width = frameShape[:2]
            self.updateForResolution((width, height))

        bboxArea = self._bboxArea(detection.bbox)
        if bboxArea < self.config.minBboxArea:
            return None

        objDims = OBJECT_DIMENSIONS.get(detection.className)
        if objDims is None:
            return None

        objPts = self._objectPoints(objDims)
        imgPts = self._imagePoints(detection.bbox)

        success, rvec, tvec = self._solvePnP(objPts, imgPts)
        if not success:
            return None

        reprojError = self._reprojectionError(objPts, imgPts, rvec, tvec)
        distance = float(np.linalg.norm(tvec))
        if not (self.config.minDistance <= distance <= self.config.maxDistance):
            return None

        fieldX, fieldY, fieldZ, cameraFrame = self._cameraToField(tvec, cameraPose)

        return PositionEstimate(
            fieldX=fieldX,
            fieldY=fieldY,
            fieldZ=fieldZ,
            distance=distance,
            qualityScore=self._qualityScore(
                detection.confidence, bboxArea, distance, reprojError
            ),
            reprojectionError=reprojError,
            bboxArea=bboxArea,
            cameraFrame=cameraFrame,
        )
