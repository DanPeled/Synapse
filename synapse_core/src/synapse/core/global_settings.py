from typing import Dict, Optional, Union, overload

from synapse.core.settings_api import (
    Setting,
    SettingsCollection,
    SettingsMap,
    SettingsMapValue,
)
from synapse.log import err
from synapse.stypes import CameraID
from synapse.util import listToTransform3d

from .camera_factory import CameraConfig, CameraConfigKey


class GlobalSettingsMeta(type):
    """Metaclass for managing global pipeline settings at the class level.

    Provides centralized access, modification, and serialization of settings,
    including camera-specific configurations.
    """

    kCameraConfigsKey: str = "camera_configs"
    __settings: Optional[SettingsCollection] = None

    def setup(cls, settings: SettingsMap) -> bool:
        """Initializes the global settings with the provided settings map.

        This method also parses and stores camera configurations if available.

        Args:
            settings (PipelineSettingsMap): The full settings map to initialize from.

        Returns:
            bool: True if initialization succeeded and camera configs were provided,
                  False otherwise.
        """
        cls.__settings = SettingsCollection(settings)
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
    def getSetting(cls, setting: str) -> Optional[SettingsMapValue]: ...
    @overload
    def getSetting(cls, setting: Setting) -> SettingsMapValue: ...

    def getSetting(cls, setting: Union[Setting, str]) -> Optional[SettingsMapValue]:
        """Retrieves the value of a setting by key or Setting object.

        Args:
            setting (Union[Setting, str]): The setting key or object.

        Returns:
            Optional[MapValue]: The current value, or None if not found.
        """
        if cls.__settings is not None:
            return cls.__settings.getSetting(setting)
        return None if isinstance(setting, str) else setting.defaultValue

    def setSetting(cls, setting: Union[Setting, str], value: SettingsMapValue) -> None:
        """Sets the value for a setting in the global settings map.

        Args:
            setting (Union[Setting, str]): The setting key or object.
            value (MapValue): The new value to assign.
        """
        if cls.__settings is not None:
            cls.__settings.setSetting(setting, value)

    def __getitem__(cls, setting: Union[str, Setting]) -> Optional[SettingsMapValue]:
        """Enables dictionary-style access for getting setting values.

        Args:
            setting (Union[str, Setting]): The setting key or object.

        Returns:
            Optional[MapValue]: The setting value, or None if not found.
        """
        return cls.getSetting(setting)

    def __setitem__(cls, setting: Union[str, Setting], value: SettingsMapValue):
        """Enables dictionary-style access for setting values.

        Args:
            setting (Union[str, Setting]): The setting key or object.
            value (MapValue): The new value to assign.
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

    def getMap(cls) -> SettingsMap:
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
