from typing import Optional, Union, Dict, List

from ntcore import NetworkTable, NetworkTableEntry


class PipelineSettings:
    PipelineSettingsMapValue = Union[
        float,
        int,
        str,
        List[float],
        List[int],
        List[str],
        List[List[int]],
        List[List[float]],
        List[List[str]],
        Dict,
    ]
    PipelineSettingsMap = Dict[str, PipelineSettingsMapValue]

    def __init__(
        self,
        settings: Optional[PipelineSettingsMap] = None,
    ):
        self.__settings = settings if settings is not None else {}

    def sendSettings(self, nt_table: NetworkTable):
        for key in self.__settings.keys():
            value = self.__settings[key]
            PipelineSettings.setEntryValue(nt_table.getEntry(key), value)

    def get(self, key: str) -> Optional[PipelineSettingsMapValue]:
        return self.__settings.get(key)

    def set(self, key: str, value: PipelineSettingsMapValue):
        self.__settings[key] = value
        # TODO: Send to NetworkTables, update, and save to file

    def __getitem__(self, key: str):
        return self.get(key)

    def __setitem__(self, key: str, value: PipelineSettingsMapValue):
        self.set(key, value)

    def __delitem__(self, key: str):
        del self.__settings[key]

    def __str__(self) -> str:
        return str(self.__settings)

    def getMap(self) -> PipelineSettingsMap:
        return self.__settings

    @staticmethod
    def setEntryValue(entry: NetworkTableEntry, value):
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


class GlobalSettingsMeta(type):
    __settings: Optional[PipelineSettings] = None

    def setup(cls, settings: PipelineSettings.PipelineSettingsMap):
        cls.__settings = PipelineSettings(settings)

    def get(cls, key: str) -> Optional[PipelineSettings.PipelineSettingsMapValue]:
        if cls.__settings is not None:
            return cls.__settings.get(key)
        return None

    def set(cls, key: str, value: PipelineSettings.PipelineSettingsMapValue):
        if cls.__settings is not None:
            cls.__settings.set(key, value)

    def __getitem__(cls, key: str):
        return cls.get(key)

    def __setitem__(cls, key: str, value: PipelineSettings.PipelineSettingsMapValue):
        cls.set(key, value)

    def __delitem__(cls, key: str):
        if cls.__settings is not None:
            del cls.__settings.getMap()[key]

    def getMap(cls) -> PipelineSettings.PipelineSettingsMap:
        if cls.__settings is not None:
            return cls.__settings.getMap()
        return {}


class GlobalSettings(metaclass=GlobalSettingsMeta):
    pass
