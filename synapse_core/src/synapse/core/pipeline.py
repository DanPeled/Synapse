# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import (Any, Callable, Generic, Iterable, List, Optional, Type,
                    TypeVar, Union, overload)

from ntcore import NetworkTable
from synapse.core.global_settings import GlobalSettings
from synapse.log import createMessage, err
from synapse_net.proto.v1 import (MessageTypeProto, PipelineProto,
                                  PipelineResultProto)
from synapse_net.socketServer import WebSocketServer
from wpimath.geometry import Transform3d

from ..stypes import CameraID, Frame, PipelineID
from .results_api import (PipelineResult, parsePipelineResult,
                          serializePipelineResult)
from .settings_api import (PipelineSettings, Setting, SettingsAPI,
                           SettingsValue, TConstraintType, TSettingValueType,
                           settingValueToProto)

FrameResult = Optional[Frame]


def isFrameResult(value: object) -> bool:
    if value is None or isinstance(value, Frame):
        return True
    if isinstance(value, Iterable):
        for f in value:
            if not isinstance(f, Frame):
                return False
        return True
    return False


TSettingsType = TypeVar("TSettingsType", bound=PipelineSettings)
TResultType = TypeVar("TResultType", bound=PipelineResult)


PipelineProcessFrameResult = FrameResult

DataTableKey = "data"
ResultsTopicKey = "results"


class Pipeline(ABC, Generic[TSettingsType, TResultType]):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any
    nt_table: Optional[NetworkTable] = None

    @abstractmethod
    def __init__(
        self,
        settings: TSettingsType,
    ):
        """Initializes the pipeline with the provided settings.

        Args:
            settings (TSettingsType): The settings object to use for the pipeline.
        """
        self.settings: TSettingsType = settings
        self.cameraIndex: CameraID = -1
        self.pipelineIndex: PipelineID = -1
        self.name: str = "new pipeline"

    def bind(self, cameraIndex: CameraID):
        """Binds a camera index to this pipeline instance.

        Args:
            cameraIndex (CameraID): The index of the camera.
        """
        self.cameraIndex = cameraIndex

    @abstractmethod
    def processFrame(self, img, timestamp: float) -> PipelineProcessFrameResult:
        """
        Abstract method that processes a single frame.

        :param img: The frame image
        :param timestamp: The time the frame was captured
        """
        pass

    def setDataValue(self, key: str, value: Any, isMsgpack: bool = False) -> None:
        if isinstance(value, (bytes, int, float, str, bool)):
            parsed = value
        elif isinstance(value, (list, tuple)) and all(
            isinstance(x, (int, float, bytes, bool)) for x in value
        ):
            parsed = (
                value if isinstance(value, tuple) else tuple(value)
            )  # make immutable
        else:
            parsed = parsePipelineResult(value)

        if self.nt_table:
            self.nt_table.getSubTable(DataTableKey).putValue(key, parsed)

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

    def setResults(self, value: TResultType) -> None:
        self.setDataValue(
            ResultsTopicKey, serializePipelineResult(value), isMsgpack=True
        )

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getSetting(
        self,
        setting: Union[Setting, str],
    ) -> Optional[Any]:
        """Retrieves a setting value by its name or Setting object.

        Args:
            setting (Union[Setting, str]): The setting to retrieve.

        Returns:
            Optional[Any]: The value of the setting if found, else None.
        """
        return self.settings.getSetting(setting)

    def setSetting(self, setting: Union[Setting, str], value: SettingsValue) -> None:
        if isinstance(setting, str):
            self.settings.getAPI().setValue(setting, value)
        elif isinstance(setting, Setting):
            self.setSetting(setting.key, value)

    def toDict(self, type: str) -> dict:
        return {"type": type, "settings": self.settings.toDict(), "name": self.name}

    def getCameraMatrix(self, cameraIndex: CameraID) -> Optional[List[List[float]]]:
        camConfig = GlobalSettings.getCameraConfig(cameraIndex)
        if not camConfig:
            err("No camera matrix found, invalid results for AprilTag detection")
            return None

        currRes = self.getSetting(self.settings.resolution)
        matrixData = camConfig.calibration.get(currRes)
        if matrixData:
            lst = matrixData.matrix
            return [lst[i : i + 3] for i in range(0, 9, 3)]
        return None

    def getDistCoeffs(self, cameraIndex: CameraID) -> Optional[List[float]]:
        data = GlobalSettings.getCameraConfig(cameraIndex)
        currRes = self.getSetting(self.settings.resolution)
        if data and currRes in data.calibration:
            return data.calibration[currRes].distCoeff
        return None

    def getCameraTransform(self, cameraIndex: CameraID) -> Optional[Transform3d]:
        data = GlobalSettings.getCameraConfig(cameraIndex)
        if data:
            return data.transform
        return None


def disabled(cls):
    cls.__is_enabled__ = False
    return cls


def pipelineToProto(inst: Pipeline, index: int) -> PipelineProto:
    api: SettingsAPI = inst.settings.getAPI()

    msg = PipelineProto(
        name=inst.name,
        index=index,
        type=type(inst).__name__,
        settings_values={
            key: settingValueToProto(api.getValue(key))
            for key in api.getSettingsSchema().keys()
        },
    )

    return msg


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
        resultingName: str = name or cls.__name__
        resultingName = f"$${resultingName}$$"
        setattr(cls, "__typename", resultingName)
        return cls

    return wrap


def pipelineResult(cls):
    new_cls = type(
        cls.__name__,
        (PipelineResult, cls),
        dict(cls.__dict__),
    )
    return dataclass(new_cls)


def pipelineSettings(cls):
    new_cls = type(
        cls.__name__,
        (PipelineSettings, cls),
        dict(cls.__dict__),
    )
    return new_cls


@lru_cache(maxsize=128)
def getPipelineTypename(pipelineType: Type[Pipeline]) -> str:
    if hasattr(pipelineType, "__typename"):
        return getattr(pipelineType, "__typename")
    elif hasattr(pipelineType, "__name__"):
        return pipelineType.__name__
    else:
        return str(pipelineType)
