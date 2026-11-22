# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover Synapse devices on the local network or a direct USB link.

The runtime listens for a UDP discovery ping on port 45454 and replies with its
nickname, hostname, IP addresses, and runtime user. This lets the installer
offer devices to add instead of asking the user to type everything by hand.

For direct USB/Ethernet links, the responder includes all local addresses and
the source address of the reply is preferred. That avoids a wrong address when
the coprocessor has no default route (common in gadget mode).
"""

import ipaddress
import json
import socket
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .direct_connect import findDirectLinkInterfaces
from .util import IsValidIP

DISCOVERY_PORT = 45454
DISCOVERY_MESSAGE = b"PING_DISCOVERY"
DISCOVERY_TIMEOUT = 2.0
LINK_LOCAL_NETWORK = ipaddress.IPv4Network("169.254.0.0/16")


@dataclass(frozen=True)
class DiscoveredDevice:
    """A device that answered the Synapse discovery ping."""

    nickname: str
    hostname: str
    ip: str
    username: str
    version: str = ""
    teamNumber: int = 0
    addresses: List[str] = field(default_factory=list)
    directLink: bool = False

    @property
    def isDirectLink(self) -> bool:
        return self.directLink or _isLinkLocal(self.ip)


def _isLinkLocal(address: str) -> bool:
    try:
        return ipaddress.IPv4Address(address) in LINK_LOCAL_NETWORK
    except ipaddress.AddressValueError:
        return False


def _sameNetwork(a: str, b: str) -> bool:
    try:
        return (int(ipaddress.IPv4Address(a)) >> 16) == (int(ipaddress.IPv4Address(b)) >> 16)
    except ipaddress.AddressValueError:
        return False


def _parseResponse(data: bytes, address: Tuple[str, int]) -> Optional[DiscoveredDevice]:
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    sourceIp = str(address[0]).strip()
    rawAddresses = payload.get("addresses") or []
    addresses = [str(item).strip() for item in rawAddresses if IsValidIP(str(item))]

    # Prefer the source address for link-local direct links; otherwise use the
    # address the device advertised that is on the same subnet as the source.
    ip = ""
    if _isLinkLocal(sourceIp):
        ip = sourceIp
    else:
        for candidate in addresses:
            if _sameNetwork(candidate, sourceIp):
                ip = candidate
                break
    if not ip:
        ip = str(payload.get("ip") or sourceIp).strip()
    if not IsValidIP(ip):
        return None

    hostname = str(payload.get("hostname") or "").strip()
    nickname = str(payload.get("nickname") or hostname or ip).strip()
    username = str(payload.get("username") or "").strip()
    version = str(payload.get("version") or "").strip()
    directLink = bool(payload.get("directLink", False))

    try:
        teamNumber = int(payload.get("team_number", 0))
    except (TypeError, ValueError):
        teamNumber = 0

    return DiscoveredDevice(
        nickname=nickname,
        hostname=hostname,
        ip=ip,
        username=username,
        version=version,
        teamNumber=teamNumber,
        addresses=addresses,
        directLink=directLink,
    )


def _broadcastTargets(port: int) -> List[Tuple[Optional[str], str, int]]:
    """Build (bind address, broadcast target, port) entries for all interfaces."""
    targets: List[Tuple[Optional[str], str, int]] = [(None, "255.255.255.255", port)]
    for interface in findDirectLinkInterfaces():
        try:
            network = ipaddress.IPv4Network(
                f"{interface.address}/{interface.netmask}", strict=False
            )
            targets.append((interface.address, str(network.broadcast_address), port))
        except ipaddress.AddressValueError:
            continue
    return targets


def _makeSocket(bindAddress: Optional[str]) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if bindAddress:
        # Binding to the interface address forces the ping out that interface.
        # This is what makes discovery work over a USB gadget without a route.
        sock.bind((bindAddress, 0))
    sock.settimeout(0.2)
    return sock


def discoverDevices(
    timeout: float = DISCOVERY_TIMEOUT,
    port: int = DISCOVERY_PORT,
) -> List[DiscoveredDevice]:
    """Broadcast a discovery ping on all interfaces and return the devices."""
    sockets: List[socket.socket] = []
    found: Dict[str, DiscoveredDevice] = {}

    try:
        for bindAddress, target, targetPort in _broadcastTargets(port):
            sock = _makeSocket(bindAddress)
            sockets.append(sock)
            try:
                sock.sendto(DISCOVERY_MESSAGE, (target, targetPort))
            except OSError:
                continue

        if not sockets:
            return []

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            responded = False
            for sock in sockets:
                try:
                    data, address = sock.recvfrom(4096)
                    responded = True
                except socket.timeout:
                    continue
                device = _parseResponse(data, address)
                if device is not None:
                    found[device.ip] = device
            if not responded:
                continue
    finally:
        for sock in sockets:
            sock.close()

    return list(found.values())
