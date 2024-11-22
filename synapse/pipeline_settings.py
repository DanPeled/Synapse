from typing_extensions import Dict


class PipelineSettings:
    PipelineSettingsMapValue = float | int | str | list[float] | list[int] | list[str]
    PipelineSettingsMap = Dict[str, PipelineSettingsMapValue]

    def __init__(self, settings: PipelineSettingsMap | None):
        self.__settings = settings if settings is not None else {}

    def get(self, key: str) -> PipelineSettingsMapValue | None:
        if key in self.__settings.keys():
            return self.__settings.get(key)

    def set(
        self, key: str, value: PipelineSettingsMapValue
    ): ...  # TODO: also send to networktables and update, and save to file

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
