# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover Synapse devices on the local network.

The runtime listens for a UDP discovery ping on port 45454 and replies with
its nickname, hostname, IP address, and runtime user. This lets the installer
offer devices to add instead of asking the user to type everything by hand.
"""

import json
import socket
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .util import IsValidIP

DISCOVERY_PORT = 45454
DISCOVERY_MESSAGE = b"PING_DISCOVERY"
DISCOVERY_TIMEOUT = 2.0


@dataclass(frozen=True)
class DiscoveredDevice:
    """A device that answered the Synapse discovery ping."""

    nickname: str
    hostname: str
    ip: str
    username: str
    version: str = ""
    teamNumber: int = 0


def _parseResponse(data: bytes, address: Tuple[str, int]) -> Optional[DiscoveredDevice]:
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    ip = str(payload.get("ip") or address[0]).strip()
    if not IsValidIP(ip):
        return None

    hostname = str(payload.get("hostname") or "").strip()
    nickname = str(payload.get("nickname") or hostname or ip).strip()
    username = str(payload.get("username") or "").strip()
    version = str(payload.get("version") or "").strip()

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
    )


def discoverDevices(
    timeout: float = DISCOVERY_TIMEOUT,
    port: int = DISCOVERY_PORT,
) -> List[DiscoveredDevice]:
    """Broadcast a discovery ping and return the devices that answer."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.2)

    found: Dict[str, DiscoveredDevice] = {}

    try:
        try:
            sock.sendto(DISCOVERY_MESSAGE, ("255.255.255.255", port))
        except OSError:
            return []

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, address = sock.recvfrom(4096)
            except socket.timeout:
                continue

            device = _parseResponse(data, address)
            if device is not None:
                found[device.ip] = device
    finally:
        sock.close()

    return list(found.values())
