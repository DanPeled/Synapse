from pathlib import Path

import yaml


class Config:
    __inst: "Config"

    def load(self, filePath: Path) -> None:
        with open(filePath) as file:
            self.__dictData: dict = yaml.full_load(file)
            Config.__inst = self

    @classmethod
    def getConfigMap(cls) -> dict:
        return cls.__inst.__dictData
