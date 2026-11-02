# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Installs the simulated camera into an existing runtime."""

from typing import Dict, SupportsFloat, cast

from ntcore import NetworkTableInstance
from synapse_net.nt_client import NtClient

from ...log import info
from ...stypes import ResolutionString
from ..camera_factory import CalibrationData, CameraConfig
from ..global_settings import GlobalSettings
from .camera import SimCamera
from .model import (
    DEFAULT_CAMERA_OFFSET,
    DEFAULT_ROBOT_POSE,
    SUPPORTED_RESOLUTIONS,
    calibrationFor,
)

DEFAULT_CAMERA_INDEX = 0
DEFAULT_STREAM_RESOLUTION = (320, 240)


def installSimulation(runtimeHandler) -> None:
    """Makes the runtime use simulated cameras instead of USB cameras.

    The runtime only changes which camera implementation it creates. Everything
    downstream (frame grabbing, streaming, pipelines) keeps using the normal
    camera path. Every configured camera becomes a simulated camera so that
    multi-camera setups also work, and a default camera is created when the
    project has none configured.
    """
    cameraHandler = runtimeHandler.cameraHandler
    cameraHandler.setCameraType(SimCamera)

    cameraConfigs = GlobalSettings.getCameraConfigMap()
    if not cameraConfigs:
        cameraConfigs[DEFAULT_CAMERA_INDEX] = CameraConfig(
            name="Sim Camera",
            id=_simCameraID(DEFAULT_CAMERA_INDEX),
            calibration=_simCalibrations(),
            defaultPipeline=0,
            streamRes=DEFAULT_STREAM_RESOLUTION,
        )

    for cameraIndex, config in cameraConfigs.items():
        config.calibration.update(_simCalibrations())
        if not config.id:
            config.id = _simCameraID(cameraIndex)

    table = (
        NetworkTableInstance.getDefault()
        .getTable(NtClient.NT_TABLE)
        .getSubTable(SimCamera.TABLE_NAME)
    )
    table.getEntry(SimCamera.ROBOT_POSE_KEY).setDefaultDoubleArray(
        cast(list[SupportsFloat], DEFAULT_ROBOT_POSE)
    )
    table.getEntry(SimCamera.CAMERA_OFFSET_KEY).setDefaultDoubleArray(
        cast(list[SupportsFloat], DEFAULT_CAMERA_OFFSET)
    )

    camerasTable = table.getSubTable(SimCamera.CAMERAS_TABLE)
    for cameraIndex in cameraConfigs:
        cameraTable = camerasTable.getSubTable(str(cameraIndex))
        # Empty defaults keep the entries visible without overriding the shared
        # values, so per-camera placement is opt-in.
        cameraTable.getEntry(SimCamera.ROBOT_POSE_KEY).setDefaultDoubleArray([])
        cameraTable.getEntry(SimCamera.CAMERA_OFFSET_KEY).setDefaultDoubleArray([])
        cameraTable.getEntry(SimCamera.CAMERA_POSE_KEY).setDefaultDoubleArray([])

    prefix = f"{NtClient.NT_TABLE}/{SimCamera.TABLE_NAME}"
    cameraPrefix = f"{prefix}/{SimCamera.CAMERAS_TABLE}/<index>"
    info(
        "Simulation cameras enabled for camera(s): "
        f"{', '.join(str(index) for index in cameraConfigs)}.\n"
        "Set poses on NetworkTables:\n"
        f"  {prefix}/{SimCamera.ROBOT_POSE_KEY} = [x, y, yaw]\n"
        f"  {prefix}/{SimCamera.CAMERA_OFFSET_KEY} = [x, y, z, roll, pitch, yaw]\n"
        f"  {prefix}/{SimCamera.CAMERA_POSE_KEY} = optional absolute camera pose\n"
        "Per-camera overrides use the same keys under:\n"
        f"  {cameraPrefix}"
    )


def _simCameraID(cameraIndex) -> str:
    return f"sim_camera_{cameraIndex}"


def _simCalibrations() -> Dict[ResolutionString, CalibrationData]:
    return {
        f"{width}x{height}": calibrationFor(width, height)
        for width, height in SUPPORTED_RESOLUTIONS
    }
