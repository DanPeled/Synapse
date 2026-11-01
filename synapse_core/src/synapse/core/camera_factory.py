# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import cache
from math import isfinite
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from ntcore import NetworkTable, NetworkTableEntry, NetworkTableInstance
from synapse_net.generated.messages.v1 import CalibrationDataProto
from synapse_net.nt_client import NtClient
from wpimath import geometry

from ..log import err
from ..stypes import CameraID, Resolution, ResolutionString
from .camera.camera_handle import CameraHandle
from .camera.cscore_camera import CsCoreCamera
from .camera.synapse_camera import SynapseCamera


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


_kMatrixKeys = ("camera_matrix", "cameraMatrix", "matrix", "K")
_kDistortionKeys = (
    "distortion_coefficients",
    "distortionCoefficients",
    "distCoeffs",
    "dist_coeffs",
    "D",
)
_kMeanErrorKeys = (
    "avg_reprojection_error",
    "mean_error",
    "meanError",
    "mean_err",
    "reprojection_error",
)
_kResolutionKeys = (
    "img_size",
    "image_size",
    "resolution",
    "measured_res",
)


def _firstValue(data: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _readNumberList(value: Any, fieldName: str) -> List[float]:
    if value is None:
        raise ValueError(f"Calibration JSON is missing `{fieldName}`")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]

    if isinstance(value, dict) and "data" in value:
        return _readNumberList(value["data"], fieldName)

    if not isinstance(value, (list, tuple)):
        raise ValueError(f"`{fieldName}` must be a number or a list of numbers")

    result: List[float] = []
    for item in value:
        result.extend(_readNumberList(item, fieldName))
    return result


def _parseResolution(value: Any) -> Optional[Resolution]:
    if isinstance(value, str):
        parts = value.lower().replace("*", "x").split("x")
        if len(parts) != 2:
            return None
        return _makeResolution(parts[0], parts[1])

    if isinstance(value, dict):
        return _makeResolution(
            value.get("width", value.get("w")),
            value.get("height", value.get("h")),
        )

    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _makeResolution(value[0], value[1])

    return None


def _makeResolution(width: Any, height: Any) -> Optional[Resolution]:
    try:
        parsedWidth = int(width)
        parsedHeight = int(height)
    except (TypeError, ValueError):
        return None

    if isinstance(width, bool) or isinstance(height, bool):
        return None
    if parsedWidth <= 0 or parsedHeight <= 0:
        return None
    return parsedWidth, parsedHeight


def _resolutionFromJson(data: Dict[str, Any]) -> Optional[Resolution]:
    for key in _kResolutionKeys:
        resolution = _parseResolution(data.get(key))
        if resolution is not None:
            return resolution

    width = data.get("image_width", data.get("width"))
    height = data.get("image_height", data.get("height"))
    if width is not None and height is not None:
        return _makeResolution(width, height)

    return None


def _resolutionKey(resolution: Resolution) -> ResolutionString:
    return f"{resolution[0]}x{resolution[1]}"


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

    @staticmethod
    def fromCalibDbJson(
        data: Dict[str, Any],
        fallbackResolution: Optional[ResolutionString] = None,
    ) -> Tuple["CalibrationData", ResolutionString]:
        """Builds calibration data from a CalibDB/WPIcal camera JSON file.

        Both the OpenCV shape exported by CalibDB and the flat custom shape
        documented by WPIcal are accepted. When the JSON does not contain an
        image size, ``fallbackResolution`` (for example the camera's current
        resolution) is used instead.
        """
        if not isinstance(data, dict):
            raise ValueError("Calibration JSON must be a JSON object")

        matrix = _readNumberList(
            _firstValue(data, _kMatrixKeys),
            "camera_matrix",
        )
        if len(matrix) != 9:
            raise ValueError(
                f"`camera_matrix` must contain exactly 9 values, got {len(matrix)}"
            )

        distCoeff = _readNumberList(
            _firstValue(data, _kDistortionKeys),
            "distortion_coefficients",
        )
        if not distCoeff:
            raise ValueError("`distortion_coefficients` must not be empty")

        meanErrValue = _firstValue(data, _kMeanErrorKeys)
        if meanErrValue is None:
            meanErr = 0.0
        else:
            try:
                meanErr = float(meanErrValue)
            except (TypeError, ValueError) as e:
                raise ValueError("`avg_reprojection_error` must be a number") from e

        if not isfinite(meanErr):
            raise ValueError("`avg_reprojection_error` must be finite")

        if not all(isfinite(value) for value in matrix + distCoeff):
            raise ValueError("Calibration values must be finite")

        resolution = _resolutionFromJson(data)
        if resolution is None:
            resolution = _parseResolution(fallbackResolution)
        if resolution is None:
            raise ValueError(
                "Calibration JSON has no image size; provide a resolution to import it"
            )

        return (
            CalibrationData(
                matrix=matrix,
                distCoeff=distCoeff,
                meanErr=meanErr,
                measuredRes=resolution,
            ),
            _resolutionKey(resolution),
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
def getCameraTable(handle: CameraHandle) -> NetworkTable:
    return (
        NetworkTableInstance.getDefault()
        .getTable(NtClient.NT_TABLE)
        .getSubTable(getCameraTableName(handle))
    )


def getCameraTableName(handle: CameraHandle) -> str:
    return handle.name


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
    ) -> "SynapseCamera":
        cam: SynapseCamera = cameraType.create(
            path=path,
            index=cameraIndex,
        )
        return cam


def getCameraSettingEntry(
    handle: CameraHandle, key: str
) -> Optional[NetworkTableEntry]:
    table: NetworkTable = getCameraTable(handle)
    entry: NetworkTableEntry = table.getEntry(key)
    return entry
