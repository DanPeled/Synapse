# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Estimate field-space positions for 2D neural-network detections."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from synapse.pipelines.neural.constants import (
    OBJECT_DIMENSIONS,
    CameraFrame,
    NeuralDetection,
    PositionEstimate,
)
from synapse.stypes import Resolution


@dataclass
class PositionEstimatorConfig:
    """Calibration and filtering values used by :class:`PositionEstimator`."""

    cameraMatrix: np.ndarray
    distCoeffs: np.ndarray
    calibResolution: Resolution
    minDistance: float
    maxDistance: float
    minBboxArea: float
    maxReprojectionError: float = 50.0


class PositionEstimator:
    """Convert a detection bounding box into a position relative to the camera.

    The estimator solves a planar PnP problem using the known approximate size
    of the detected object. It then rotates the resulting camera-space vector
    into field space using the configured camera pose.
    """

    def __init__(self, config: PositionEstimatorConfig):
        self.config = config
        self._baseCameraMatrix = np.array(config.cameraMatrix, dtype=np.float64)
        self._cameraMatrix = self._baseCameraMatrix.copy()
        self._currentResolution: Optional[Resolution] = None
        self.updateForResolution(config.calibResolution)

    def setConfig(self, config: PositionEstimatorConfig) -> None:
        self.config = config
        self._baseCameraMatrix = np.array(config.cameraMatrix, dtype=np.float64)
        self._cameraMatrix = self._baseCameraMatrix.copy()
        self._currentResolution = None
        self.updateForResolution(config.calibResolution)

    def updateForResolution(self, resolution: Resolution) -> None:
        """Scale the calibration matrix to the resolution of the current frame."""
        width, height = int(resolution[0]), int(resolution[1])
        if width <= 0 or height <= 0:
            return
        if self._currentResolution == (width, height):
            return

        calibWidth, calibHeight = self.config.calibResolution
        if calibWidth <= 0 or calibHeight <= 0:
            return

        scaleX = width / calibWidth
        scaleY = height / calibHeight

        matrix = self._baseCameraMatrix.copy()
        matrix[0, 0] *= scaleX
        matrix[1, 1] *= scaleY
        matrix[0, 2] *= scaleX
        matrix[1, 2] *= scaleY

        self._cameraMatrix = matrix
        self._currentResolution = (width, height)

    @staticmethod
    def _objectPoints(dimensions: Dict[str, float]) -> np.ndarray:
        halfWidth = dimensions["width"] / 2
        halfHeight = dimensions["height"] / 2
        return np.array(
            [
                [-halfWidth, -halfHeight, 0],
                [halfWidth, -halfHeight, 0],
                [halfWidth, halfHeight, 0],
                [-halfWidth, halfHeight, 0],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _imagePoints(bbox: Tuple[float, float, float, float]) -> np.ndarray:
        x1, y1, x2, y2 = bbox
        return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)

    @staticmethod
    def _bboxArea(bbox: Tuple[float, float, float, float]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, (x2 - x1) * (y2 - y1))

    def _solvePnP(
        self, objectPoints: np.ndarray, imagePoints: np.ndarray
    ) -> Tuple[bool, np.ndarray, np.ndarray]:
        return cv2.solvePnP(
            objectPoints,
            imagePoints,
            self._cameraMatrix,
            self.config.distCoeffs,
            flags=cv2.SOLVEPNP_IPPE,
        )

    def _reprojectionError(
        self,
        objectPoints: np.ndarray,
        imagePoints: np.ndarray,
        rvec: np.ndarray,
        tvec: np.ndarray,
    ) -> float:
        projected, _ = cv2.projectPoints(
            objectPoints, rvec, tvec, self._cameraMatrix, self.config.distCoeffs
        )
        projected = projected.reshape(-1, 2)
        return float(np.mean(np.linalg.norm(projected - imagePoints, axis=1)))

    @staticmethod
    def _rotationMatrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
        cosRoll, sinRoll = np.cos(roll), np.sin(roll)
        cosPitch, sinPitch = np.cos(pitch), np.sin(pitch)
        cosYaw, sinYaw = np.cos(yaw), np.sin(yaw)

        rotationX = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, cosRoll, -sinRoll],
                [0.0, sinRoll, cosRoll],
            ],
            dtype=np.float64,
        )
        rotationY = np.array(
            [
                [cosPitch, 0.0, sinPitch],
                [0.0, 1.0, 0.0],
                [-sinPitch, 0.0, cosPitch],
            ],
            dtype=np.float64,
        )
        rotationZ = np.array(
            [
                [cosYaw, -sinYaw, 0.0],
                [sinYaw, cosYaw, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        return rotationZ @ rotationY @ rotationX

    @classmethod
    def _cameraToField(
        cls, tvec: np.ndarray, cameraPose: Dict[str, float]
    ) -> Tuple[float, float, float, CameraFrame]:
        camX, camY, camZ = (float(value) for value in tvec.flatten())

        # OpenCV camera axes are x-right, y-down, z-forward. Robot/field axes
        # are x-forward, y-left, z-up.
        cameraFrame = CameraFrame(camX, camY, camZ)
        body = np.array([camZ, -camX, -camY], dtype=np.float64)

        rotation = cls._rotationMatrix(
            cameraPose.get("roll", 0.0),
            cameraPose.get("pitch", 0.0),
            cameraPose.get("yaw", 0.0),
        )
        position = np.array(
            [
                cameraPose.get("x", 0.0),
                cameraPose.get("y", 0.0),
                cameraPose.get("z", 0.0),
            ],
            dtype=np.float64,
        )

        field = position + rotation @ body
        return (
            float(field[0]),
            float(field[1]),
            float(field[2]),
            cameraFrame,
        )

    def _qualityScore(
        self,
        confidence: float,
        bboxArea: float,
        distance: float,
        reprojectionError: float,
    ) -> float:
        sizeScore = min(bboxArea / 50_000.0, 1.0)
        distanceScore = max(0.0, 1.0 - distance / max(self.config.maxDistance, 1e-6))
        reprojScore = max(
            0.0,
            1.0 - reprojectionError / max(self.config.maxReprojectionError, 1e-6),
        )

        return (
            confidence * 0.4 + reprojScore * 0.3 + sizeScore * 0.2 + distanceScore * 0.1
        )

    def estimate3DPosition(
        self,
        detection: NeuralDetection,
        cameraPose: Dict[str, float],
        frameShape: Optional[Tuple[int, ...]] = None,
    ) -> Optional[PositionEstimate]:
        """Estimate the detection's position, or return ``None`` if it is invalid."""
        if frameShape is not None and len(frameShape) >= 2:
            self.updateForResolution((int(frameShape[1]), int(frameShape[0])))

        bboxArea = self._bboxArea(detection.bbox)
        if bboxArea < self.config.minBboxArea:
            return None

        objectDimensions = OBJECT_DIMENSIONS.get(detection.className)
        if objectDimensions is None:
            return None

        objectPoints = self._objectPoints(objectDimensions)
        imagePoints = self._imagePoints(detection.bbox)

        success, rvec, tvec = self._solvePnP(objectPoints, imagePoints)
        if not success:
            return None

        reprojectionError = self._reprojectionError(
            objectPoints, imagePoints, rvec, tvec
        )
        if reprojectionError > self.config.maxReprojectionError:
            return None

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
                detection.confidence, bboxArea, distance, reprojectionError
            ),
            reprojectionError=reprojectionError,
            bboxArea=bboxArea,
            cameraFrame=cameraFrame,
        )
