# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for cross-platform direct-link detection."""

from types import SimpleNamespace
from unittest.mock import patch

import synapse_installer.direct_connect as direct_connect
from synapse_installer.direct_connect import (
    DirectLinkInterface,
    describeHostNetwork,
    findDirectLinkInterfaces,
    hasDirectLink,
    pickPreferredInterface,
)


def _address(family, address, netmask="255.255.0.0"):
    return SimpleNamespace(family=family, address=address, netmask=netmask)


class AF_INET:
    name = "AF_INET"


def test_find_direct_link_interfaces(monkeypatch):
    interfaces = {
        "eth0": [_address(AF_INET, "192.168.1.50", "255.255.255.0")],
        "usb0": [_address(AF_INET, "169.254.2.100")],
        "rndis0": [_address(AF_INET, "169.254.3.100")],
        "lo": [_address(AF_INET, "127.0.0.1", "255.0.0.0")],
    }
    monkeypatch.setattr(direct_connect.psutil, "net_if_addrs", lambda: interfaces)

    found = findDirectLinkInterfaces()
    names = {item.name for item in found}

    assert names == {"usb0", "rndis0"}
    assert all(item.isUsb for item in found)


def test_has_direct_link(monkeypatch):
    monkeypatch.setattr(
        direct_connect.psutil,
        "net_if_addrs",
        lambda: {"en7": [_address(AF_INET, "169.254.1.5")]},
    )
    assert hasDirectLink() is True


def test_no_direct_link(monkeypatch):
    monkeypatch.setattr(
        direct_connect.psutil,
        "net_if_addrs",
        lambda: {"eth0": [_address(AF_INET, "10.0.0.5")]},
    )
    assert hasDirectLink() is False


def test_pick_preferred_interface(monkeypatch):
    interfaces = [
        DirectLinkInterface("en0", "169.254.2.5", "255.255.0.0", False),
        DirectLinkInterface("usb0", "169.254.3.5", "255.255.0.0", True),
    ]
    monkeypatch.setattr(direct_connect, "findDirectLinkInterfaces", lambda: interfaces)
    assert pickPreferredInterface() == interfaces[1]


def test_describe_host_network(monkeypatch):
    monkeypatch.setattr(
        direct_connect.psutil,
        "net_if_addrs",
        lambda: {"usb0": [_address(AF_INET, "169.254.2.100")]},
    )
    with patch.object(direct_connect.Platform, "getOSType") as osType:
        osType.return_value.value = "Linux"
        text = describeHostNetwork()
    assert "usb0" in text
    assert "169.254.2.100" in text
