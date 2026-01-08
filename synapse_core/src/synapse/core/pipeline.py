# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import (Any, Callable, Dict, Generic, Iterable, List, Optional,
                    Type, TypeVar, Union, overload)

from ntcore import GenericPublisher, NetworkTable, Value
from synapse_net.proto.v1 import (MessageTypeProto, PipelineProto,
                                  PipelineResultProto)
from synapse_net.socketServer import WebSocketServer

from ..log import createMessage, err, warn
from ..stypes import CameraID, Frame, PipelineID, Resolution
from .camera_factory import SynapseCamera
from .global_settings import GlobalSettings
from .results_api import (PipelineResult, parsePipelineResult,
                          serializePipelineResult)
from .settings_api import (CameraSettings, PipelineSettings, Setting,
                           SettingsAPI, SettingsValue, TConstraintType,
                           TSettingValueType, settingValueToProto)

FrameResult = Optional[Frame]


def _makeNtValue(value: Any, isMsgpack: bool) -> Value:
    if isMsgpack:
        return Value.makeRaw(value)

    if isinstance(value, bool):
        return Value.makeBoolean(value)
    if isinstance(value, int):
        return Value.makeInteger(value)
    if isinstance(value, float):
        return Value.makeDouble(value)
    if isinstance(value, str):
        return Value.makeString(value)
    if isinstance(value, bytes):
        return Value.makeRaw(value)
    if isinstance(value, tuple) or isinstance(value, list):
        if all(isinstance(x, float) for x in value):
            return Value.makeDoubleArray(list(value))
        if all(isinstance(x, int) for x in value):
            return Value.makeIntegerArray(list(value))
        if all(isinstance(x, bool) for x in value):
            return Value.makeBooleanArray(list(value))
        if all(isinstance(x, str) for x in value):
            return Value.makeStringArray(list(value))

    raise TypeError(f"Unsupported NT value type: {type(value)}")


def isFrameResult(value: object) -> bool:
    if value is None or isinstance(value, Frame):
        return True
    if isinstance(value, Iterable):
        return all(isinstance(f, Frame) for f in value)
    return False


TSettingsType = TypeVar("TSettingsType", bound=PipelineSettings)
TResultType = TypeVar("TResultType", bound=PipelineResult)

PipelineProcessFrameResult = FrameResult

DataTableKey = "data"
ResultsTopicKey = "results"


class Pipeline(ABC, Generic[TSettingsType, TResultType]):
    __is_enabled__ = True
    ntTable: Optional[NetworkTable] = None

    _ntDataTable: Optional[NetworkTable]
    _ntPublishers: Dict[str, GenericPublisher]

    @abstractmethod
    def __init__(self, settings: TSettingsType):
        self.settings: TSettingsType = settings
        self.cameraSettings: CameraSettings = CameraSettings()
        self.cameraIndex: CameraID = -1
        self.pipelineIndex: PipelineID = -1
        self.name: str = "new pipeline"

        self._ntDataTable = None
        self._ntPublishers = {}

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        self.invalidateCachedEntries()
        self.cameraIndex = cameraIndex

        self.cameraSettings.fromCamera(camera)

    @abstractmethod
    def processFrame(self, img, timestamp: float) -> PipelineProcessFrameResult:
        pass

    def invalidateCachedEntries(self) -> None:
        for pub in self._ntPublishers.values():
            try:
                del pub
            except Exception:
                pass
        self._ntPublishers.clear()
        self._ntDataTable = None

    def _getDataTable(self) -> Optional[NetworkTable]:
        if not self.ntTable:
            return None
        if self._ntDataTable is None:
            self._ntDataTable = self.ntTable.getSubTable(DataTableKey)
        return self._ntDataTable

    def _ntTypeString(self, value: Any, isMsgpack: bool) -> str:
        if isMsgpack:
            return "raw"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "string"
        if isinstance(value, bytes):
            return "raw"
        if isinstance(value, tuple) or isinstance(value, list):
            if all(isinstance(x, float) for x in value):
                return "double[]"
            if all(isinstance(x, int) for x in value):
                return "int[]"
            if all(isinstance(x, bool) for x in value):
                return "boolean[]"
            if all(isinstance(x, str) for x in value):
                return "string[]"
        raise TypeError(f"Unsupported NT type: {type(value)}")

    def _getPublisher(self, key: str, typeString: str) -> Optional[GenericPublisher]:
        pub = self._ntPublishers.get(key)
        if pub:
            return pub

        table = self._getDataTable()
        if not table:
            return None

        topic = table.getTopic(key)
        pub = topic.genericPublish(typeString)
        self._ntPublishers[key] = pub
        return pub

    def setDataValue(self, key: str, value: Any, isMsgpack: bool = False) -> None:
        if value == bytes():
            parsed = bytes()
        elif isinstance(value, (bytes, int, float, str, bool)):
            parsed = value
        elif isinstance(value, (list, tuple)):
            parsed = tuple(value)
        else:
            parsed = parsePipelineResult(value)

        typeString = self._ntTypeString(parsed, isMsgpack)
        pub = self._getPublisher(key, typeString)
        if pub:
            pub.set(_makeNtValue(parsed, isMsgpack=isMsgpack))

        if WebSocketServer.kInstance:
            WebSocketServer.kInstance.sendToAllSync(
                createMessage(
                    MessageTypeProto.SET_PIPELINE_RESULT,
                    PipelineResultProto(
                        is_msgpack=isMsgpack,
                        key=key,
                        value=settingValueToProto(parsed),
                        pipeline_index=self.pipelineIndex,
                    ),
                )
            )

    def setResults(self, value: TResultType | None) -> None:
        self.setDataValue(
            ResultsTopicKey,
            serializePipelineResult(value) if value is not None else bytes(),
            isMsgpack=True,
        )

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getSetting(self, setting: Union[Setting, str]) -> Optional[Any]:
        return self.settings.getSetting(setting)

    def setSetting(self, setting: Union[Setting, str], value: SettingsValue) -> None:
        settingObj = (
            setting
            if isinstance(setting, Setting)
            else self.settings.getAPI().getSetting(setting)
        )
        if settingObj:
            self.settings.setSetting(settingObj, value)
            self.onSettingChanged(settingObj, self.getSetting(setting))
        elif setting in CameraSettings():
            collection = self.getCurrentCameraSettingCollection()
            assert collection is not None
            collection.setSetting(setting, value)
        else:
            err(f"Setting {setting} was not found for pipeline {self.pipelineIndex}")

    def toDict(self, type_: str, cameraIndex: int) -> dict:
        settingsDict = self.settings.toDict()
        settingsDict.update(self.cameraSettings.toDict())
        return {
            "name": self.name,
            "type": type_,
            "settings": settingsDict,
        }

    def getCameraMatrix(self, cameraIndex: CameraID) -> Optional[List[List[float]]]:
        camConfig = GlobalSettings.getCameraConfig(cameraIndex)
        if not camConfig:
            err("No camera matrix found, may result in invalid results")
            return None

        currRes = self.getCameraSetting(CameraSettings.resolution)
        if not currRes:
            return None

        def parse_res(res):
            if isinstance(res, str):
                w, h = res.lower().split("x")
                return int(w), int(h)
            return int(res[0]), int(res[1])

        calib = camConfig.calibration

        # 1) Exact match
        matrixData = calib.get(currRes)
        if matrixData:
            lst = matrixData.matrix
            return [lst[i : i + 3] for i in range(0, 9, 3)]

        if len(calib.keys()) == 0:
            warn(f"No calibrations found for camera {self.cameraIndex}")
            return

        # 2) Fallback: largest available resolution
        try:
            currW, currH = parse_res(currRes)

            bestRes = max(calib.keys(), key=lambda r: parse_res(r)[0] * parse_res(r)[1])
            baseW, baseH = parse_res(bestRes)

            baseMat = calib[bestRes].matrix
            fx, _, cx, _, fy, cy, _, _, _ = baseMat

            sx = currW / baseW
            sy = currH / baseH

            scaled = [
                fx * sx,
                0.0,
                cx * sx,
                0.0,
                fy * sy,
                cy * sy,
                0.0,
                0.0,
                1.0,
            ]

            warn(f"Camera resolution {currRes} not calibrated, scaling from {bestRes}")

            return [scaled[i : i + 3] for i in range(0, 9, 3)]

        except Exception as e:
            err(f"Failed to scale camera matrix: {e}")
            return None

    def getResolution(self) -> Resolution:
        resString = self.getCameraSetting(CameraSettings.resolution)
        split = resString.split("x")
        return int(split[0]), int(split[1])

    def getDistCoeffs(self, cameraIndex: CameraID) -> Optional[List[float]]:
        data = GlobalSettings.getCameraConfig(cameraIndex)
        currRes = self.getCameraSetting(CameraSettings.resolution)
        if data and currRes in data.calibration:
            return data.calibration[currRes].distCoeff
        return None

    @overload
    def getCameraSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getCameraSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getCameraSetting(self, setting: Union[str, Setting]) -> Optional[Any]:
        return self.cameraSettings.getSetting(setting)

    def setCameraSetting(
        self, setting: Union[str, Setting], value: SettingsValue
    ) -> None:
        collection = self.getCurrentCameraSettingCollection()
        assert collection is not None
        collection.setSetting(setting, value)

    def getCurrentCameraSettingCollection(self) -> Optional[CameraSettings]:
        return self.cameraSettings

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        pass


def disabled(cls):
    cls.__is_enabled__ = False
    return cls


def pipelineToProto(inst: Pipeline, index: int, cameraId: CameraID) -> PipelineProto:
    api: SettingsAPI = inst.settings.getAPI()
    settingsValues = {
        key: settingValueToProto(api.getValue(key))
        for key in api.getSettingsSchema().keys()
    }

    cameraSettings = inst.getCurrentCameraSettingCollection()
    if cameraSettings:
        cameraAPI = cameraSettings.getAPI()
        settingsValues.update(
            {
                key: settingValueToProto(cameraAPI.getValue(key))
                for key in cameraAPI.getSettingsSchema().keys()
            }
        )

    return PipelineProto(
        name=inst.name,
        index=index,
        type=type(inst).__name__,
        settings_values=settingsValues,
        cameraid=cameraId,
    )


TClass = TypeVar("TClass")


def pipelineName(name: str) -> Callable[[Type[TClass]], Type[TClass]]:
    def wrap(cls: Type[TClass]) -> Type[TClass]:
        setattr(cls, "__typename", name)
        return cls

    return wrap


def systemPipeline(
    name: Optional[str] = None,
) -> Callable[[Type[TClass]], Type[TClass]]:
    def wrap(cls: Type[TClass]) -> Type[TClass]:
        resultingName = f"$${name or cls.__name__}$$"
        setattr(cls, "__typename", resultingName)
        return cls

    return wrap


def pipelineResult(cls):
    new_cls = type(cls.__name__, (PipelineResult, cls), dict(cls.__dict__))
    return dataclass(new_cls)


def pipelineSettings(cls):
    return type(cls.__name__, (PipelineSettings, cls), dict(cls.__dict__))


@lru_cache(maxsize=128)
def getPipelineTypename(pipelineType: Type[Pipeline]) -> str:
    if hasattr(pipelineType, "__typename"):
        return getattr(pipelineType, "__typename")
    if hasattr(pipelineType, "__name__"):
        return pipelineType.__name__
    return str(pipelineType)
