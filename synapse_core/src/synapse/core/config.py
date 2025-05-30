from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProjectConfig:
    hostname: str
    username: str
    password: str

    def __init__(self, filePath: Path) -> None:
        with open(filePath) as file:
            dictData: dict = yaml.full_load(file)
            self.hostname = dictData["hostname"]
            self.username = dictData["username"]
            self.password = dictData["username"]


@dataclass
class NetworkConfig:
    """
    Represents the network configuration for a team.

    Attributes:
        teamNumber (int): The team number.
        name (str): The name of the team or network.
        hostname (str): The hostname of the networked device.
        user (str): The username for accessing the device.
        password (str): The password for the user.
    """

    teamNumber: int
    name: str

    @classmethod
    def fromJson(cls, data: dict) -> "NetworkConfig":
        """
        Creates a NetworkConfig object from a dictionary.

        Args:
            data (dict): A dictionary containing the network configuration keys.

        Returns:
            NetworkConfig: An instance populated with values from the dictionary.
        """
        return NetworkConfig(
            teamNumber=data["team_number"],
            name=data["name"],
        )


class Config:
    """
    Singleton-style class for loading and accessing configuration data.
    """

    __inst: "Config"

    def load(self, filePath: Path) -> None:
        """
        Loads configuration data from a YAML file and sets the singleton instance.

        Args:
            filePath (Path): The path to the YAML configuration file.
        """
        with open(filePath) as file:
            self.__dictData: dict = yaml.full_load(file)
            Config.__inst = self

    @classmethod
    def getInstance(cls) -> "Config":
        """
        Returns the current singleton instance of the Config class.

        Returns:
            Config: The current loaded instance.
        """
        return cls.__inst

    def getConfigMap(self) -> dict:
        """
        Returns the raw configuration dictionary.

        Returns:
            dict: The parsed configuration data.
        """
        return self.__dictData

    @property
    def network(self) -> NetworkConfig:
        """
        Returns the network configuration parsed into a NetworkConfig object.

        Returns:
            NetworkConfig: The network settings from the config map.
        """
        return NetworkConfig.fromJson(self.getConfigMap()["network"])
