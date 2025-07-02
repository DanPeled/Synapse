from abc import ABC, abstractmethod
from typing import Any, Generic, Iterable, Optional, TypeVar, Union, overload

from ntcore import NetworkTable
from synapse_net.proto.v1 import PipelineProto
from wpilib import SendableBuilderImpl
from wpiutil import Sendable, SendableBuilder

from ..stypes import CameraID, Frame
from .settings_api import (PipelineSettings, Setting, SettingsValue,
                           settingValueToProto)

FrameResult = Optional[Union[Iterable[Frame], Frame]]

TSettingsType = TypeVar("TSettingsType", bound=PipelineSettings)


class Pipeline(ABC, Generic[TSettingsType]):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any
    nt_table: Optional[NetworkTable] = None
    builder_cache: dict[str, SendableBuilder] = {}

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
        self.name: str = "new pipeline"

    def bind(self, cameraIndex: CameraID):
        """Binds a camera index to this pipeline instance.

        Args:
            cameraIndex (CameraID): The index of the camera.
        """
        self.cameraIndex = cameraIndex

    @abstractmethod
    def processFrame(self, img, timestamp: float) -> FrameResult:
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
            if isinstance(value, Sendable):
                builder = self.__getOrCreateBuilder(key)
                value.initSendable(builder)
                builder.update()
            else:
                self.nt_table.getSubTable("data").putValue(key, value)

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getSetting(self, setting: Setting) -> Any: ...

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

    def __getOrCreateBuilder(self, key: str) -> SendableBuilder:
        """
        Retrieves a cached builder for the given key, or creates and caches a new one.

        :param key: The key associated with the builder.
        :return: A SendableBuilder instance.
        """
        if key not in self.builder_cache and self.nt_table is not None:
            sub_table = self.nt_table.getSubTable(f"data/{key}")
            builder = SendableBuilderImpl()
            builder.setTable(sub_table)
            builder.startListeners()
            self.builder_cache[key] = builder
        return self.builder_cache[key]

    def toDict(self, type: str) -> dict:
        return {"type": type, "settings": self.settings.toDict(), "name": self.name}


def disabled(cls):
    cls.__is_enabled__ = False
    return cls


def pipelineToProto(inst: Pipeline, index: int) -> PipelineProto:
    api = inst.settings.getAPI()

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
