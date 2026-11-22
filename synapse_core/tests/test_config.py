# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
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
    assert config.prefixLength == 24
    assert config.ip is None
    assert config.networkInterface is None


def test_network_config_loads_static_address() -> None:
    data: dict = {
        "team_number": 1234,
        "name": "TestTeam",
        "hostname": "coprocessor",
        "ip": "10.12.34.11",
        "interface": "eth0",
        "prefix_length": 16,
    }
    config = NetworkConfig.fromJson(data)

    assert config.hostname == "coprocessor"
    assert config.ip == "10.12.34.11"
    assert config.networkInterface == "eth0"
    assert config.prefixLength == 16


def test_network_config_reads_legacy_interface_typo() -> None:
    data: dict = {
        "ip": "10.12.34.11",
        "interfrace": "eth0",
    }
    config = NetworkConfig.fromJson(data)

    assert config.networkInterface == "eth0"


def test_network_config_round_trips_through_json() -> None:
    config = NetworkConfig(
        teamNumber=1234,
        name="TestTeam",
        hostname="coprocessor",
        ip="10.12.34.11",
        networkInterface="eth0",
        prefixLength=24,
    )

    restored = NetworkConfig.fromJson(config.toJson())

    assert restored == config


def test_network_config_proto_includes_prefix() -> None:
    config = NetworkConfig(
        teamNumber=1234,
        name="TestTeam",
        hostname="coprocessor",
        ip="10.12.34.11",
        networkInterface="eth0",
        prefixLength=16,
    )

    proto = config.toProto()

    assert proto.ip == "10.12.34.11"
    assert proto.network_interface == "eth0"
    assert proto.prefix_length == 16


def test_network_config_proto_uses_empty_strings_for_unset_values() -> None:
    config = NetworkConfig(
        teamNumber=1234,
        name="TestTeam",
        hostname="coprocessor",
        ip=None,
        networkInterface=None,
        prefixLength=24,
    )

    proto = config.toProto()

    assert proto.ip == ""
    assert proto.network_interface == ""


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
