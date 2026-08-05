# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Dict, List, Optional, Type, Union
from .camera.synapse_camera import SynapseCamera
from ntcore import NetworkTable, NetworkTableEntry, NetworkTableInstance
from .camera.cscore_camera import CsCoreCamera
from synapse_net.generated.messages.v1 import CalibrationDataProto
from synapse_net.nt_client import NtClient
from wpimath import geometry

from ..log import err
from ..stypes import (
    CameraID,
    Resolution,
    ResolutionString,
)


class CameraPropKeys(Enum):
    kBrightness = "brightness"
    kContrast = "contrast"
    kSaturation = "saturation"
    kHue = "hue"
    kGain = "gain"
    kExposure = "exposure"
    kWhiteBalanceTemperature = "white_balance_temperature"
    kSharpness = "sharpness"
    kOrientation = "orientation"


class CameraSettingsKeys(Enum):
    kViewID = "view_id"
    kRecord = "record"
    kPipeline = "pipeline"
    kPipelineType = "pipeline_t"


@dataclass
class CalibrationData:
    matrix: List[float]
    distCoeff: List[float]
    meanErr: float
    measuredRes: Resolution

    def toDict(self) -> Dict[str, Any]:
        return {
            CameraConfigKey.kMatrix.value: self.matrix,
            CameraConfigKey.kDistCoeff.value: self.distCoeff,
            CameraConfigKey.kMeasuredRes.value: self.measuredRes,
            CameraConfigKey.kMeanErr.value: self.meanErr,
        }

    @staticmethod
    def fromDict(data: Dict[str, Any]) -> "CalibrationData":
        return CalibrationData(
            matrix=data[CameraConfigKey.kMatrix.value],
            distCoeff=data[CameraConfigKey.kDistCoeff.value],
            measuredRes=data[CameraConfigKey.kMeasuredRes.value],
            meanErr=data[CameraConfigKey.kMeanErr.value],
        )

    def toProto(self, cameraIndex: CameraID) -> CalibrationDataProto:
        return CalibrationDataProto(
            camera_index=cameraIndex,
            mean_error=self.meanErr,
            resolution="x".join([str(dim) for dim in self.measuredRes]),
            camera_matrix=self.matrix,
            dist_coeffs=self.distCoeff,
        )


@dataclass
class CameraConfig:
    name: str
    id: str
    calibration: Dict[ResolutionString, CalibrationData]
    defaultPipeline: int
    streamRes: Resolution

    def toDict(self) -> Dict[str, Any]:
        return {
            CameraConfigKey.kName.value: self.name,
            CameraConfigKey.kPath.value: self.id,
            CameraConfigKey.kDefaultPipeline.value: self.defaultPipeline,
            CameraConfigKey.kStreamRes.value: list(self.streamRes),
            CameraConfigKey.kCalibration.value: {
                resolution: calib.toDict()
                for resolution, calib in self.calibration.items()
            },
        }

    @staticmethod
    def fromDict(data: Dict[str, Any]) -> "CameraConfig":
        calib = {
            key: CalibrationData.fromDict(calib)
            for key, calib in data.get(CameraConfigKey.kCalibration.value, {}).items()
        }

        return CameraConfig(
            name=data[CameraConfigKey.kName.value],
            id=data[CameraConfigKey.kPath.value],
            streamRes=data[CameraConfigKey.kStreamRes.value],
            defaultPipeline=data[CameraConfigKey.kDefaultPipeline.value],
            calibration=calib,
        )


class CameraConfigKey(Enum):
    kName = "name"
    kPath = "id"
    kDefaultPipeline = "default_pipeline"
    kMatrix = "matrix"
    kDistCoeff = "distCoeffs"
    kMeasuredRes = "measured_res"
    kStreamRes = "stream_res"
    kCalibration = "calibration"
    kMeanErr = "mean_err"


def listToTransform3d(dataList: List[List[float]]) -> geometry.Transform3d:
    """
    Converts a 2D list containing position and rotation data into a Transform3d object.

    The input list must contain exactly two sublists:
    - The first sublist represents the translation (x, y, z).
    - The second sublist represents the rotation (roll, pitch, yaw) in degrees.

    Args:
        dataList (List[List[float]]): A list with two elements, each being a list of three floats.

    Returns:
        geometry.Transform3d: The resulting Transform3d object. Returns an identity transform
        if the input list does not contain exactly two elements.
    """
    if len(dataList) != 2:
        err("Invalid transform length")
        return geometry.Transform3d()
    else:
        poseList = dataList[0]
        rotationList = dataList[1]

        return geometry.Transform3d(
            translation=geometry.Translation3d(poseList[0], poseList[1], poseList[2]),
            rotation=geometry.Rotation3d.fromDegrees(
                rotationList[0], rotationList[1], rotationList[2]
            ),
        )


@cache
def getCameraTable(camera: SynapseCamera) -> NetworkTable:
    return (
        NetworkTableInstance.getDefault()
        .getTable(NtClient.NT_TABLE)
        .getSubTable(getCameraTableName(camera))
    )


def getCameraTableName(camera: SynapseCamera) -> str:
    return camera.name


class CameraFactory:
    kCameraServer: Type[SynapseCamera] = CsCoreCamera
    kDefault: Type[SynapseCamera] = kCameraServer

    @classmethod
    def create(
        cls,
        *_,
        cameraType: Type[SynapseCamera] = kDefault,
        cameraIndex: CameraID,
        path: Union[str, int],
        name: str = "",
    ) -> "SynapseCamera":
        cam: SynapseCamera = cameraType.create(
            path=path,
            name=name,
            index=cameraIndex,
        )
        cam.setIndex(cameraIndex)
        return cam


def getCameraSettingEntry(
    camera: SynapseCamera, key: str
) -> Optional[NetworkTableEntry]:
    table: NetworkTable = getCameraTable(camera)
    entry: NetworkTableEntry = table.getEntry(key)
    return entry
