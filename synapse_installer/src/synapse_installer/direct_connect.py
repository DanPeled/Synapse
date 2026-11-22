# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-platform detection of direct USB/Ethernet links to a coprocessor.

This is the computer-side counterpart of
:mod:`synapse.hardware.usb_gadget`. It enumerates network interfaces with
``psutil`` (which supports Windows, macOS, and Linux) and reports interfaces
that already have an IPv4 link-local address. The coprocessor's USB gadget uses
link-local addressing, so no host-side network configuration is ever needed:
the operating system assigns the address automatically when the cable is
plugged in.

The ``Platform`` class from ``synapse_core`` is used to make platform decisions
instead of ad-hoc ``os.name`` checks.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import psutil
from synapse.hardware.metrics import Platform

LINK_LOCAL_NETWORK = ipaddress.IPv4Network("169.254.0.0/16")

# Interface name hints used only for labeling/diagnostics. Detection is based
# on the actual link-local address, not on the name.
USB_INTERFACE_HINTS = (
    "usb",
    "rndis",
    "ecm",
    "ncm",
    "enx",  # Linux USB Ethernet (MAC-based names)
    "ethernet",
)


@dataclass(frozen=True)
class DirectLinkInterface:
    """A host network interface that can reach a direct-connected device."""

    name: str
    address: str
    netmask: str
    isUsb: bool

    @property
    def network(self) -> ipaddress.IPv4Network:
        return ipaddress.IPv4Network(f"{self.address}/{self.netmask}", strict=False)


def _isLinkLocal(address: str) -> bool:
    try:
        return ipaddress.IPv4Address(address) in LINK_LOCAL_NETWORK
    except ipaddress.AddressValueError:
        return False


def _isUsbInterface(name: str, platform: type[Platform]) -> bool:
    """Best-effort classification, refined by OS-specific naming conventions."""
    lower = name.lower()
    if platform.isWindows():
        # Windows names USB adapters "Ethernet 2", "Local Area Connection", etc.
        return any(hint in lower for hint in ("ethernet", "usb", "rndis"))
    if platform.isMac():
        # macOS uses enX for all Ethernet; USB adapters also report as enX.
        return lower.startswith("en")
    return any(hint in lower for hint in USB_INTERFACE_HINTS)


def _iterAddresses() -> Iterable[tuple[str, str, str]]:
    """Yield (interface name, IPv4 address, netmask) from psutil."""
    for name, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            # psutil uses a platform-specific constant for AF_INET; comparing
            # by name avoids importing socket constants that differ per OS.
            if getattr(address.family, "name", str(address.family)) == "AF_INET":
                netmask = address.netmask or "255.255.0.0"
                yield name, str(address.address), str(netmask)


def findDirectLinkInterfaces() -> List[DirectLinkInterface]:
    """Return host interfaces with link-local addresses ready for direct links."""
    results: Dict[str, DirectLinkInterface] = {}
    for name, address, netmask in _iterAddresses():
        if not _isLinkLocal(address):
            continue
        results[name] = DirectLinkInterface(
            name=name,
            address=address,
            netmask=netmask,
            isUsb=_isUsbInterface(name, Platform),
        )
    return list(results.values())


def hasDirectLink() -> bool:
    """Whether any host interface is configured for direct-link networking."""
    return bool(findDirectLinkInterfaces())


def describeHostNetwork() -> str:
    """Return a short human-readable summary for diagnostics."""
    interfaces = findDirectLinkInterfaces()
    osName = Platform.getOSType().value
    if not interfaces:
        return f"{osName}: no link-local interfaces detected"
    parts = [
        f"{item.name} ({item.address}, {'USB' if item.isUsb else 'Ethernet'})"
        for item in interfaces
    ]
    return f"{osName}: " + ", ".join(parts)


def pickPreferredInterface(
    interfaces: Optional[List[DirectLinkInterface]] = None,
) -> Optional[DirectLinkInterface]:
    """Prefer a USB interface, then any link-local interface."""
    candidates = interfaces if interfaces is not None else findDirectLinkInterfaces()
    for interface in candidates:
        if interface.isUsb:
            return interface
    return candidates[0] if candidates else None
