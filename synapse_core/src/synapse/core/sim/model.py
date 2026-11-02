# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared camera model and defaults for the simulated field camera."""

from math import radians, tan
from typing import List, Tuple

import numpy as np

from ..camera_factory import CalibrationData
from ...stypes import Resolution

#: Horizontal field of view of the simulated camera, in degrees.
FIELD_OF_VIEW_DEGREES = 70.0

#: Render rate of the simulated camera.
MAX_FPS = 30.0

#: Resolutions the simulated camera can produce. These mirror the options
#: exposed by ``CameraSettings`` so any pipeline resolution can be selected.
SUPPORTED_RESOLUTIONS: Tuple[Resolution, ...] = (
    (1920, 1080),
    (1640, 1232),
    (1296, 972),
    (1280, 960),
    (1280, 720),
    (1024, 768),
    (800, 600),
    (640, 480),
    (640, 360),
    (320, 240),
    (320, 180),
)

#: Default robot pose published/consumed on NetworkTables: ``[x, y, yaw]``.
DEFAULT_ROBOT_POSE: List[float] = [9.0, 4.2, 0.0]

#: Default camera offset relative to the robot:
#: ``[x, y, z, roll, pitch, yaw]`` (meters, radians).
DEFAULT_CAMERA_OFFSET: List[float] = [0.35, 0.0, 1.4, 0.0, radians(20.0), 0.0]

#: Field map used when the deploy directory does not contain one.
DEFAULT_FIELD_LENGTH_METERS = 16.541
DEFAULT_FIELD_WIDTH_METERS = 8.069


def cameraMatrix(width: int, height: int) -> np.ndarray:
    """Returns the pinhole camera matrix used by the renderer and calibration."""
    width = max(1, int(width))
    height = max(1, int(height))

    fx = (width * 0.5) / tan(radians(FIELD_OF_VIEW_DEGREES) * 0.5)
    fy = fx
    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5

    return np.array(
        [
            [fx, 0.0, cx],
            [0.0, fy, cy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def calibrationFor(width: int, height: int) -> CalibrationData:
    """Builds calibration data matching the simulated camera's projection."""
    matrix = cameraMatrix(width, height)
    return CalibrationData(
        matrix=matrix.flatten().tolist(),
        distCoeff=[0.0, 0.0, 0.0, 0.0, 0.0],
        meanErr=0.0,
        measuredRes=(int(width), int(height)),
    )
