from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Optional, Union

from ntcore import Event, EventFlags, NetworkTable
from synapse.log import err
from synapse.stypes import Frame
from typing_extensions import Dict
from wpilib import SendableBuilderImpl
from wpiutil import Sendable, SendableBuilder

from ..util import listToTransform3d
from .camera_factory import CameraConfig, CameraConfigKey
from .settings_api import (
    PipelineSettings,
    PipelineSettingsMap,
    PipelineSettingsMapValue,
)

FrameResult = Optional[Union[Iterable[Frame], Frame]]


class Pipeline(ABC):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any

    @abstractmethod
    def __init__(self, settings: PipelineSettings, cameraIndex: int):
        self.nt_table: Optional[NetworkTable] = None
        self.builder_cache: dict[str, SendableBuilder] = {}
        self.settings = settings
        self.cameraIndex = cameraIndex

    def setup(self):
        pass

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

    def getSetting(
        self,
        key: str,
    ) -> Optional[Any]:
        if self.nt_table is not None:
            return self.nt_table.getSubTable("settings").getValue(key, None)
        else:
            return self.settings.getSetting(key)

    def setDataListener(
        self,
        key: str,
        setter: Callable[[VALID_ENTRY_TYPES], None],
        getter: Callable[[], VALID_ENTRY_TYPES],
    ):
        if self.nt_table is not None:
            self.__setListener(
                key=key,
                setter=setter,
                getter=getter,
                table=self.nt_table.getSubTable("data"),
            )
        else:
            err(f"trying to set data listener (key = {key}), for None table")

    def __setListener(
        self,
        key: str,
        setter: Callable[[VALID_ENTRY_TYPES], None],
        getter: Callable[[], VALID_ENTRY_TYPES],
        table: NetworkTable,
    ):
        def listener(_: NetworkTable, key: str, event: Event):
            setter(event.data.value.value())  # pyright: ignore

        table.addListener(eventMask=EventFlags.kValueAll, listener=listener, key=key)
        table.putValue(key, getter())

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


def disabled(cls):
    cls.__is_enabled__ = False
    return cls


class GlobalSettingsMeta(type):
    """
    A metaclass for managing global settings at the class level.
    """

    kCameraConfigsKey: str = "camera_configs"
    __settings: Optional[PipelineSettings] = None

    def setup(cls, settings: PipelineSettingsMap) -> bool:
        """
        Initializes the global settings with the provided settings map.

        Args:
            settings (PipelineSettings.PipelineSettingsMap): The settings to initialize with.
        """
        cls.__settings = PipelineSettings(settings)
        cls.__cameraConfigs: Dict[int, CameraConfig] = {}

        if cls.kCameraConfigsKey in settings:
            for index, camData in dict(settings[cls.kCameraConfigsKey]).items():
                camConfig: CameraConfig = CameraConfig(
                    name=camData[CameraConfigKey.kName.value],
                    path=camData[CameraConfigKey.kPath.value],
                    distCoeff=camData[CameraConfigKey.kDistCoeff.value],
                    matrix=camData[CameraConfigKey.kMatrix.value],
                    measuredRes=camData[CameraConfigKey.kMeasuredRes.value],
                    streamRes=camData[CameraConfigKey.kStreamRes.value],
                    transform=listToTransform3d(
                        camData[CameraConfigKey.kTransform.value]
                    ),
                    defaultPipeline=camData[CameraConfigKey.kDefaultPipeline.value],
                )
                cls.__cameraConfigs[index] = camConfig
            return True
        else:
            err("No camera configs provided")
            return False

    def hasCameraData(cls, cameraIndex: int) -> bool:
        return cameraIndex in cls.__cameraConfigs.keys()

    def getCameraConfig(cls, cameraIndex: int) -> Optional[CameraConfig]:
        if cls.hasCameraData(cameraIndex):
            return cls.__cameraConfigs[cameraIndex]
        return None

    def getCameraConfigMap(cls) -> Dict[int, CameraConfig]:
        return cls.__cameraConfigs

    def getSetting(cls, key: str) -> Optional[PipelineSettingsMapValue]:
        """
        Retrieves a setting by its key from the global settings.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettings.PipelineSettingsMapValue]: The value of the setting, or None if not found.
        """
        if cls.__settings is not None:
            return cls.__settings.getSetting(key)
        return None

    def setSetting(cls, key: str, value: PipelineSettingsMapValue) -> None:
        """
        Sets a new value for a given setting key in the global settings.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettings.PipelineSettingsMapValue): The value to set for the setting.
        """
        if cls.__settings is not None:
            cls.__settings.setSetting(key, value)

    def __getitem__(cls, key: str) -> Optional[PipelineSettingsMapValue]:
        """
        Retrieves a setting by its key using indexing syntax.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettings.PipelineSettingsMapValue]: The value of the setting.
        """
        return cls.getSetting(key) or None

    def __setitem__(cls, key: str, value: PipelineSettingsMapValue):
        """
        Sets a value for a given setting key using indexing syntax.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettings.PipelineSettingsMapValue): The value to set for the setting.
        """
        cls.setSetting(key, value)

    def __delitem__(cls, key: str):
        """
        Deletes a setting for a given key from the global settings.

        Args:
            key (str): The key of the setting to delete.
        """
        if cls.__settings is not None:
            del cls.__settings.getMap()[key]

    def getMap(cls) -> PipelineSettingsMap:
        """
        Returns the global settings map.

        Returns:
            PipelineSettings.PipelineSettingsMap: The dictionary of global settings.
        """
        if cls.__settings is not None:
            return cls.__settings.getMap()
        return {}

    def __contains__(cls, key: str) -> bool:
        """
        Check if the specified key exists in the settings.

        Args:
            key (str): The key to check for in the settings.

        Returns:
            bool: True if the key exists in the settings, False otherwise.
        """
        if cls.__settings is not None:
            return key in cls.__settings
        return False


class GlobalSettings(metaclass=GlobalSettingsMeta):
    """
    A class for managing global pipeline settings using a metaclass.
    """

    pass
