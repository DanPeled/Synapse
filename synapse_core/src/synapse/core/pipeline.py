from abc import ABC, abstractmethod
from typing import Any, Generic, Iterable, Optional, TypeVar, Union, overload

from ntcore import NetworkTable
from synapse.log import err
from synapse.stypes import Frame
from typing_extensions import Dict
from wpilib import SendableBuilderImpl
from wpiutil import Sendable, SendableBuilder

from ..stypes import CameraID
from ..util import listToTransform3d
from .camera_factory import CameraConfig, CameraConfigKey
from .settings_api import (
    PipelineSettings,
    PipelineSettingsMap,
    PipelineSettingsMapValue,
    Setting,
)

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
        return {"type": type, "settings": self.settings.toDict()}


def disabled(cls):
    cls.__is_enabled__ = False
    return cls


class GlobalSettingsMeta(type):
    """Metaclass for managing global pipeline settings at the class level.

    Provides centralized access, modification, and serialization of settings,
    including camera-specific configurations.
    """

    kCameraConfigsKey: str = "camera_configs"
    __settings: Optional[PipelineSettings] = None

    def setup(cls, settings: PipelineSettingsMap) -> bool:
        """Initializes the global settings with the provided settings map.

        This method also parses and stores camera configurations if available.

        Args:
            settings (PipelineSettingsMap): The full settings map to initialize from.

        Returns:
            bool: True if initialization succeeded and camera configs were provided,
                  False otherwise.
        """
        cls.__settings = PipelineSettings(settings)
        cls.__cameraConfigs: Dict[CameraID, CameraConfig] = {}

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

    def hasCameraData(cls, cameraIndex: CameraID) -> bool:
        """Checks if camera data exists for the given camera index.

        Args:
            cameraIndex (CameraID): The ID of the camera.

        Returns:
            bool: True if camera data is available, False otherwise.
        """
        return cameraIndex in cls.__cameraConfigs.keys()

    def getCameraConfig(cls, cameraIndex: CameraID) -> Optional[CameraConfig]:
        """Retrieves the camera configuration for the given camera index.

        Args:
            cameraIndex (CameraID): The ID of the camera.

        Returns:
            Optional[CameraConfig]: The camera configuration, or None if not available.
        """
        if cls.hasCameraData(cameraIndex):
            return cls.__cameraConfigs[cameraIndex]
        return None

    def getCameraConfigMap(cls) -> Dict[CameraID, CameraConfig]:
        """Returns the full map of camera configurations.

        Returns:
            Dict[CameraID, CameraConfig]: Mapping from camera ID to configuration.
        """
        return cls.__cameraConfigs

    @overload
    def getSetting(cls, setting: str) -> Optional[PipelineSettingsMapValue]: ...
    @overload
    def getSetting(cls, setting: Setting) -> PipelineSettingsMapValue: ...

    def getSetting(
        cls, setting: Union[Setting, str]
    ) -> Optional[PipelineSettingsMapValue]:
        """Retrieves the value of a setting by key or Setting object.

        Args:
            setting (Union[Setting, str]): The setting key or object.

        Returns:
            Optional[PipelineSettingsMapValue]: The current value, or None if not found.
        """
        if cls.__settings is not None:
            return cls.__settings.getSetting(setting)
        return None if isinstance(setting, str) else setting.defaultValue

    def setSetting(
        cls, setting: Union[Setting, str], value: PipelineSettingsMapValue
    ) -> None:
        """Sets the value for a setting in the global settings map.

        Args:
            setting (Union[Setting, str]): The setting key or object.
            value (PipelineSettingsMapValue): The new value to assign.
        """
        if cls.__settings is not None:
            cls.__settings.setSetting(setting, value)

    def __getitem__(
        cls, setting: Union[str, Setting]
    ) -> Optional[PipelineSettingsMapValue]:
        """Enables dictionary-style access for getting setting values.

        Args:
            setting (Union[str, Setting]): The setting key or object.

        Returns:
            Optional[PipelineSettingsMapValue]: The setting value, or None if not found.
        """
        return cls.getSetting(setting)

    def __setitem__(cls, setting: Union[str, Setting], value: PipelineSettingsMapValue):
        """Enables dictionary-style access for setting values.

        Args:
            setting (Union[str, Setting]): The setting key or object.
            value (PipelineSettingsMapValue): The new value to assign.
        """
        cls.setSetting(setting, value)

    def __delitem__(cls, key: str):
        """Deletes a setting from the global settings map.

        Args:
            key (str): The key of the setting to delete.
        """
        if cls.__settings is not None:
            del cls.__settings.getMap()[key]

    def toDict(self) -> dict:
        """Serializes all current settings into a dictionary.

        Returns:
            dict: Dictionary of all settings and their current values.
        """
        if self.__settings is not None:
            return {key: self.getSetting(key) for key in self.__settings.getMap()}
        return {}

    def getMap(cls) -> PipelineSettingsMap:
        """Returns the internal settings map as a dictionary.

        Returns:
            PipelineSettingsMap: Dictionary of current global settings.
        """
        if cls.__settings is not None:
            return cls.__settings.toDict()
        return {}

    def __contains__(cls, key: str) -> bool:
        """Checks whether a setting exists.

        Args:
            key (str): The key to check for existence.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        if cls.__settings is not None:
            return key in cls.__settings
        return False


class GlobalSettings(metaclass=GlobalSettingsMeta):
    """Global access point for pipeline settings using the GlobalSettingsMeta metaclass.

    This class is used as a singleton-like interface to access and modify global settings
    from anywhere in the program.
    """

    pass
