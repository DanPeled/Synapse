from pathlib import Path

import yaml


class Config:
    __inst: "Config"

    def load(self, filePath: Path) -> None:
        with open(filePath) as file:
            self.__dictData: dict = yaml.full_load(file)
            Config.__inst = self

    @classmethod
    def getInstance(cls) -> "Config":
        return cls.__inst

    def getConfigMap(self) -> dict:
        return self.__dictData
