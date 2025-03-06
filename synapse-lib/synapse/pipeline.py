from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from typing_extensions import Dict
from ntcore import NetworkTable, Event, EventFlags, NetworkTableEntry
from wpilib import SendableBuilderImpl
from wpiutil import Sendable, SendableBuilder
from synapse import log
from synapse.stypes import Frame


class PipelineSettings:
    """
    A class for managing and sending pipeline settings to a NetworkTable.

    Attributes:
        PipelineSettingsMap: A dictionary representing the settings for the pipeline.
        PipelineSettingsMapValue: A type alias for the allowed values in the settings map.

    Methods:
        sendSettings: Sends the current settings to a NetworkTable.
        get: Retrieves a setting by its key.
        set: Sets a setting with a specified key and value.
        getMap: Returns the entire settings map.
        setEntryValue: A static method for setting a NetworkTable entry's value.
    """

    PipelineSettingsMapValue = Any

    PipelineSettingsMap = Dict[str, PipelineSettingsMapValue]

    def __init__(
        self,
        settings: Optional[PipelineSettingsMap] = None,
    ):
        """
        Initializes the PipelineSettings instance with optional settings.

        Args:
            settings (Optional[PipelineSettingsMap]): A dictionary of settings to initialize with.
        """
        self.__settings = settings if settings is not None else {}

    def sendSettings(self, nt_table: NetworkTable):
        """
        Sends the current settings to the specified NetworkTable.

        Args:
            nt_table (NetworkTable): The NetworkTable to send the settings to.
        """
        for key in self.__settings.keys():
            value = self.__settings[key]
            PipelineSettings.setEntryValue(nt_table.getEntry(key), value)

    def get(self, key: str) -> Optional[PipelineSettingsMapValue]:
        """
        Retrieves the setting for a given key.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettingsMapValue]: The value of the setting, or None if not found.
        """
        return self.__settings.get(key)

    def set(self, key: str, value: PipelineSettingsMapValue):
        """
        Sets a new value for a given setting key.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettingsMapValue): The value to set for the setting.
        """
        self.__settings[key] = value
        # TODO: Send to NetworkTables, update, and save to file

    def __getitem__(self, key: str):
        """
        Retrieves the setting for a given key using the indexing syntax.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettingsMapValue]: The value of the setting.
        """
        return self.get(key)

    def __setitem__(self, key: str, value: PipelineSettingsMapValue):
        """
        Sets a value for a given setting key using the indexing syntax.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettingsMapValue): The value to set for the setting.
        """
        self.set(key, value)

    def __delitem__(self, key: str):
        """
        Deletes a setting for a given key.

        Args:
            key (str): The key of the setting to delete.
        """
        del self.__settings[key]

    def __str__(self) -> str:
        """
        Returns a string representation of the settings map.

        Returns:
            str: A string representation of the settings.
        """
        return str(self.__settings)

    def getMap(self) -> PipelineSettingsMap:
        """
        Returns the entire settings map.

        Returns:
            PipelineSettingsMap: The dictionary of settings.
        """
        return self.__settings

    def setMap(self, map: Dict[str, Any]) -> None:
        self.__settings = map

    @staticmethod
    def setEntryValue(entry: NetworkTableEntry, value):
        """
        Sets the value of a NetworkTable entry based on the type of value.

        Args:
            entry (NetworkTableEntry): The NetworkTable entry to set the value for.
            value: The value to set in the entry, which can be an int, float, bool, string, or list.

        Raises:
            ValueError: If the value type is unsupported.
        """
        if isinstance(value, int):
            entry.setInteger(value)
        elif isinstance(value, float):
            entry.setFloat(value)
        elif isinstance(value, bool):
            entry.setBoolean(value)
        elif isinstance(value, str):
            entry.setString(value)
        elif isinstance(value, list):
            if all(isinstance(i, int) for i in value):
                entry.setIntegerArray(value)
            elif all(isinstance(i, float) for i in value):
                entry.setFloatArray(value)
            elif all(isinstance(i, bool) for i in value):
                entry.setBooleanArray(value)
            elif all(isinstance(i, str) for i in value):
                entry.setStringArray(value)
            else:
                raise ValueError("Unsupported list type")
        else:
            raise ValueError("Unsupported type")


class Pipeline(ABC):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any

    @abstractmethod
    def __init__(self, settings: PipelineSettings, camera_index: int):
        self.nt_table: Optional[NetworkTable] = None
        self.builder_cache: dict[str, SendableBuilder] = {}
        self.settings = settings
        self.camera_index = camera_index

    def setup(self):
        pass

    @abstractmethod
    def process_frame(self, img, timestamp: float) -> Frame:
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

    def getSetting(self, key: str) -> Optional[Any]:
        if self.nt_table is not None:
            return self.nt_table.getSubTable("settings").getValue(key, None)
        else:
            return self.settings.get(key)

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
            log.err(f"trying to set data listener (key = {key}), for None table")

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

    Attributes:
        __settings (Optional[PipelineSettings]): The global pipeline settings instance.

    Methods:
        setup: Initializes the global settings.
        get: Retrieves a setting by key from the global settings.
        set: Sets a setting in the global settings.
        getMap: Returns the global settings map.
    """

    __settings: Optional[PipelineSettings] = None

    def setup(cls, settings: PipelineSettings.PipelineSettingsMap):
        """
        Initializes the global settings with the provided settings map.

        Args:
            settings (PipelineSettings.PipelineSettingsMap): The settings to initialize with.
        """
        cls.__settings = PipelineSettings(settings)

    def get(cls, key: str) -> Optional[PipelineSettings.PipelineSettingsMapValue]:
        """
        Retrieves a setting by its key from the global settings.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettings.PipelineSettingsMapValue]: The value of the setting, or None if not found.
        """
        if cls.__settings is not None:
            return cls.__settings.get(key)
        return None

    def set(cls, key: str, value: PipelineSettings.PipelineSettingsMapValue) -> None:
        """
        Sets a new value for a given setting key in the global settings.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettings.PipelineSettingsMapValue): The value to set for the setting.
        """
        if cls.__settings is not None:
            cls.__settings.set(key, value)

    def __getitem__(
        cls, key: str
    ) -> Optional[PipelineSettings.PipelineSettingsMapValue]:
        """
        Retrieves a setting by its key using indexing syntax.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            Optional[PipelineSettings.PipelineSettingsMapValue]: The value of the setting.
        """
        return cls.get(key) or None

    def __setitem__(cls, key: str, value: PipelineSettings.PipelineSettingsMapValue):
        """
        Sets a value for a given setting key using indexing syntax.

        Args:
            key (str): The key of the setting to set.
            value (PipelineSettings.PipelineSettingsMapValue): The value to set for the setting.
        """
        cls.set(key, value)

    def __delitem__(cls, key: str):
        """
        Deletes a setting for a given key from the global settings.

        Args:
            key (str): The key of the setting to delete.
        """
        if cls.__settings is not None:
            del cls.__settings.getMap()[key]

    def getMap(cls) -> PipelineSettings.PipelineSettingsMap:
        """
        Returns the global settings map.

        Returns:
            PipelineSettings.PipelineSettingsMap: The dictionary of global settings.
        """
        if cls.__settings is not None:
            return cls.__settings.getMap()
        return {}


class GlobalSettings(metaclass=GlobalSettingsMeta):
    """
    A class for managing global pipeline settings using a metaclass.
    """

    pass
