# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Final
from unittest.mock import mock_open, patch

from synapse.core.config import Config, NetworkConfig

# Sample configuration data
sample_yaml: str = """
network:
  team_number: 1234
  name: "TestTeam"
"""


def test_network_config_from_json() -> None:
    data: dict = {
        "team_number": 1234,
        "name": "TestTeam",
    }
    config = NetworkConfig.fromJson(data)

    assert config.teamNumber == 1234
    assert config.name == "TestTeam"


def test_config_load_and_get_instance() -> None:
    mock_path: Path = Path("fake_config.yaml")

    with patch("builtins.open", mock_open(read_data=sample_yaml)):
        config: Final[Config] = Config()
        config.load(mock_path)

        inst: Config = Config.getInstance()
        assert inst is config

        config_map: dict = inst.getConfigMap()
        assert "network" in config_map
        assert config_map["network"]["team_number"] == 1234


def test_config_network_property() -> None:
    mock_path = Path("fake_config.yaml")

    with patch("builtins.open", mock_open(read_data=sample_yaml)):
        config = Config()
        config.load(mock_path)

        network = config.network
        assert isinstance(network, NetworkConfig)
        assert network.teamNumber == 1234
        assert network.name == "TestTeam"
