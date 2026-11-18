# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from synapse_net.generated.messages.v1 import SetNetworkSettingsProto


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
            self.password = dictData["password"]


@dataclass
class NetworkConfig:
    """
    Represents the network configuration for a team.

    Attributes:
        teamNumber (int): The team number.
        name (str): The NetworkTables name.
        hostname (str): The hostname of the networked device.
        ip (Optional[str]): Static IPv4 address added alongside DHCP, if any.
        networkInterface (Optional[str]): Interface for the static address.
        prefixLength (int): CIDR prefix length for the static address.
    """

    teamNumber: int
    name: str
    hostname: str
    ip: Optional[str]
    networkInterface: Optional[str]
    prefixLength: int

    @classmethod
    def fromJson(cls, data: dict) -> "NetworkConfig":
        """
        Creates a NetworkConfig object from a dictionary.

        Args:
            data (dict): A dictionary containing the network configuration keys.

        Returns:
            NetworkConfig: An instance populated with values from the dictionary.
        """
        # Older configs wrote the interface key with a typo. Keep reading it so
        # existing devices pick up their settings after an upgrade.
        interface = data.get("interface") or data.get("interfrace")

        try:
            prefixLength = int(data.get("prefix_length", 24))
        except (TypeError, ValueError):
            prefixLength = 24

        return NetworkConfig(
            teamNumber=data.get("team_number", 0),
            name=data.get("name", "Synapse"),
            hostname=data.get("hostname") or socket.gethostname(),
            ip=data.get("ip") or None,
            networkInterface=interface or None,
            prefixLength=prefixLength,
        )

    def toJson(self) -> Dict[str, Any]:
        return {
            "team_number": self.teamNumber,
            "name": self.name,
            "hostname": self.hostname,
            "ip": self.ip,
            "interface": self.networkInterface,
            "prefix_length": self.prefixLength,
        }

    def toProto(self) -> SetNetworkSettingsProto:
        return SetNetworkSettingsProto(
            hostname=self.hostname,
            ip=self.ip or "",
            network_interface=self.networkInterface or "",
            network_table=self.name,
            team_number=self.teamNumber,
            prefix_length=self.prefixLength,
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
        self.__path = filePath
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
        return self.__dictData or {}

    @property
    def path(self) -> Path:
        return self.__path

    @property
    def network(self) -> NetworkConfig:
        """
        Returns the network configuration parsed into a NetworkConfig object.

        Returns:
            NetworkConfig: The network settings from the config map.
        """
        return NetworkConfig.fromJson(self.getConfigMap().get("network", {}))
