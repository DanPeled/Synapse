# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import patch

import pytest
from synapse_net.devicenetworking import (
    NetworkCommandError,
    NetworkingManager,
    StaticAddress,
    isPhysicalInterface,
)


@pytest.mark.parametrize(
    ("interface", "address", "prefix"),
    [
        ("eth0", "10.12.34.11", 24),
        ("enp3s0", "192.168.1.50", 16),
        ("wlan0", "10.0.0.2", 32),
    ],
)
def test_static_address_parses_valid_values(
    interface: str, address: str, prefix: int
) -> None:
    parsed = StaticAddress.parse(interface, address, prefix)

    assert parsed is not None
    assert parsed.interface == interface
    assert parsed.address == address
    assert parsed.prefixLength == prefix
    assert parsed.cidr == f"{address}/{prefix}"


@pytest.mark.parametrize(
    ("interface", "address", "prefix"),
    [
        ("lo", "10.12.34.11", 24),
        ("docker0", "10.12.34.11", 24),
        ("eth0", "not-an-ip", 24),
        ("eth0", "10.12.34.11", 0),
        ("eth0", "10.12.34.11", 33),
        ("eth0", "127.0.0.1", 8),
        ("eth0", "169.254.1.2", 16),
        ("eth0", "10.12.34.0", 24),
        ("eth0", "10.12.34.255", 24),
    ],
)
def test_static_address_rejects_invalid_values(
    interface: str, address: str, prefix: int
) -> None:
    assert StaticAddress.parse(interface, address, prefix) is None


def test_physical_interface_filter() -> None:
    assert isPhysicalInterface("eth0")
    assert isPhysicalInterface("enp3s0")
    assert isPhysicalInterface("wlan0")
    assert not isPhysicalInterface("lo")
    assert not isPhysicalInterface("docker0")
    assert not isPhysicalInterface("veth1234")
    assert not isPhysicalInterface("tailscale0")
    assert not isPhysicalInterface("")


def test_set_static_address_uses_network_manager() -> None:
    manager = NetworkingManager()
    address = StaticAddress("eth0", "10.12.34.11", 24)

    with (
        patch.object(
            NetworkingManager, "_detectBackend", return_value="networkmanager"
        ),
        patch.object(
            NetworkingManager,
            "_networkManagerConnection",
            return_value="Wired connection 1",
        ),
        patch.object(NetworkingManager, "_runCommand") as run,
    ):
        assert manager.setStaticAddress(address)

    commands = [call.args[0] for call in run.call_args_list]
    assert [
        "sudo",
        "-n",
        "nmcli",
        "connection",
        "modify",
        "Wired connection 1",
        "ipv4.method",
        "auto",
        "ipv4.addresses",
        "10.12.34.11/24",
    ] in commands
    assert [
        "sudo",
        "-n",
        "nmcli",
        "connection",
        "up",
        "Wired connection 1",
    ] in commands
    assert manager._current == address


def test_set_static_address_creates_missing_network_manager_connection() -> None:
    manager = NetworkingManager()
    address = StaticAddress("eth0", "10.12.34.11", 24)

    with (
        patch.object(
            NetworkingManager, "_detectBackend", return_value="networkmanager"
        ),
        patch.object(NetworkingManager, "_networkManagerConnection", return_value=None),
        patch.object(
            NetworkingManager,
            "_createNetworkManagerConnection",
            return_value="synapse-eth0",
        ) as create,
        patch.object(NetworkingManager, "_runCommand") as run,
    ):
        assert manager.setStaticAddress(address)

    create.assert_called_once_with("eth0")
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[0][4:7] == ["modify", "synapse-eth0", "ipv4.method"]


def test_remove_static_address_clears_network_manager() -> None:
    manager = NetworkingManager()
    address = StaticAddress("eth0", "10.12.34.11", 24)
    manager._current = address
    manager._backend = "networkmanager"

    with (
        patch.object(
            NetworkingManager,
            "_networkManagerConnection",
            return_value="Wired connection 1",
        ),
        patch.object(NetworkingManager, "_runCommand") as run,
    ):
        assert manager.removeStaticAddress()

    commands = [call.args[0] for call in run.call_args_list]
    assert [
        "sudo",
        "-n",
        "nmcli",
        "connection",
        "modify",
        "Wired connection 1",
        "ipv4.addresses",
        "",
    ] in commands
    assert manager._current is None


def test_set_static_address_uses_netplan() -> None:
    manager = NetworkingManager()
    address = StaticAddress("enp3s0", "10.12.34.11", 24)

    with (
        patch.object(NetworkingManager, "_detectBackend", return_value="netplan"),
        patch.object(NetworkingManager, "_runCommand") as run,
    ):
        assert manager.setStaticAddress(address)

    commands = [call.args[0] for call in run.call_args_list]
    assert [
        "sudo",
        "-n",
        "netplan",
        "set",
        "--origin-hint",
        "synapse-static",
        "ethernets.enp3s0.dhcp4=true",
    ] in commands
    assert [
        "sudo",
        "-n",
        "netplan",
        "set",
        "--origin-hint",
        "synapse-static",
        "ethernets.enp3s0.addresses=[10.12.34.11/24]",
    ] in commands
    assert ["sudo", "-n", "netplan", "apply"] in commands


def test_set_static_address_falls_back_to_ip_commands() -> None:
    manager = NetworkingManager()
    address = StaticAddress("eth0", "10.12.34.11", 24)

    with (
        patch.object(NetworkingManager, "_detectBackend", return_value="ip"),
        patch.object(NetworkingManager, "_applyIpAddress") as apply,
        patch.object(NetworkingManager, "_startWorkerLocked") as worker,
    ):
        assert manager.setStaticAddress(address)

    apply.assert_called_once_with(address)
    worker.assert_called_once_with(address)


def test_set_static_address_reports_command_failure() -> None:
    manager = NetworkingManager()
    address = StaticAddress("eth0", "10.12.34.11", 24)

    with (
        patch.object(
            NetworkingManager, "_detectBackend", return_value="networkmanager"
        ),
        patch.object(
            NetworkingManager,
            "_networkManagerConnection",
            return_value="Wired connection 1",
        ),
        patch.object(
            NetworkingManager,
            "_runCommand",
            side_effect=NetworkCommandError("boom"),
        ),
    ):
        assert not manager.setStaticAddress(address)

    assert manager._current is None


def test_remove_static_address_is_noop_when_unset() -> None:
    manager = NetworkingManager()

    with patch.object(NetworkingManager, "_runCommand") as run:
        assert manager.removeStaticAddress()

    run.assert_not_called()
