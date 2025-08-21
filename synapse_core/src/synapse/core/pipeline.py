# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cache
from typing import (Any, Callable, Generic, Iterable, Optional, Type, TypeVar,
                    Union, overload)

from ntcore import NetworkTable
from synapse.log import createMessage
from synapse_net.proto.v1 import (MessageTypeProto, PipelineProto,
                                  PipelineResultProto)
from synapse_net.socketServer import WebSocketServer

from ..stypes import CameraID, Frame, PipelineID
from .results_api import PipelineResult
from .settings_api import (PipelineSettings, Setting, SettingsAPI,
                           SettingsValue, TConstraintType, TSettingValueType,
                           settingValueToProto)

FrameResult = Optional[Frame]


def isFrameResult(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Frame):
        return True
    if isinstance(value, Iterable):
        return all(isinstance(f, Frame) for f in value)
    return False


TSettingsType = TypeVar("TSettingsType", bound=PipelineSettings)
TResultType = TypeVar("TResultType", bound=PipelineResult)


PipelineProcessFrameResult = FrameResult


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
        self.settings = settings
        self.cameraIndex = -1
        self.pipelineIndex: PipelineID
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

    def setDataValue(self, key: str, value: Any) -> None:
        """
        Sets a value in the network table.

        :param key: The key for the value.
        :param value: The value to store.
        """
        if self.nt_table is not None:
            self.nt_table.getSubTable("data").putValue(key, value)

        if WebSocketServer.kInstance is not None:
            WebSocketServer.kInstance.sendToAllSync(
                createMessage(
                    MessageTypeProto.SET_PIPELINE_RESULT,
                    PipelineResultProto(
                        is_msgpack=False,
                        key=key,
                        value=settingValueToProto(value),
                        pipeline_index=self.pipelineIndex,
                    ),
                )
            )

    def setResults(self, value: TResultType) -> None:
        self.setDataValue("results", value)  # TODO: Make it use msgpack to serialize

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


@cache
def getPipelineTypename(pipelineType: Type[Pipeline]) -> str:
    if hasattr(pipelineType, "__typename"):
        return getattr(pipelineType, "__typename")
    elif hasattr(pipelineType, "__name__"):
        return pipelineType.__name__
    else:
        return str(pipelineType)
