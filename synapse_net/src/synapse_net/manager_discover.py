# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""UDP discovery responder with support for direct USB/Ethernet links.

The responder answers the installer's ``PING_DISCOVERY`` broadcast on port
45454. For direct connections, the device may not have a default route, so
``getIP()`` can report the wrong address. This responder therefore:

1. includes all local IPv4 addresses in the response, and
2. prefers an address on the same subnet as the packet sender.
"""

import ipaddress
import json
import platform
import socket
from typing import Any, Dict, List, Tuple

import psutil
import synapse.log as log
from synapse.hardware.metrics import Platform
from synapse.util import getIP


def _localIPv4Addresses() -> List[str]:
    """Return all local IPv4 addresses, using the cross-platform psutil API."""
    addresses: List[str] = []
    for _name, additions in psutil.net_if_addrs().items():
        for item in additions:
            if getattr(item.family, "name", str(item.family)) == "AF_INET":
                address = str(item.address)
                if address not in addresses:
                    addresses.append(address)
    return addresses


def _sameNetwork(address: str, peer: str) -> bool:
    try:
        local = int(ipaddress.IPv4Address(address))
        remote = int(ipaddress.IPv4Address(peer))
        return (local >> 16) == (remote >> 16)
    except ipaddress.AddressValueError:
        return False


def chooseReplyAddress(sender: str, addresses: List[str]) -> str:
    """Choose the local address best suited for reaching the sender."""
    if sender and sender not in ("0.0.0.0", "127.0.0.1"):
        # Prefer a link-local address on a direct connection.
        for address in addresses:
            try:
                if ipaddress.IPv4Address(address).is_link_local and _sameNetwork(
                    address, sender
                ):
                    return address
            except ipaddress.AddressValueError:
                continue
        for address in addresses:
            if _sameNetwork(address, sender):
                return address
    return getIP()


class UDPDeviceResponder:
    def __init__(
        self,
        nickname: str,
        user: str,
        team_number: int,
        version: str,
        ping_message: str = "PING_DISCOVERY",
        port: int = 45454,
    ):
        self.port = port
        self.nickname = nickname
        self.user = user
        self.team_number = team_number
        self.version = version
        self.ping_message = ping_message

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("0.0.0.0", self.port))

        log.info(f"[UDPDeviceResponder] Listening on port {self.port}")

    def buildResponse(self, sender: str = "") -> Dict[str, Any]:
        addresses = _localIPv4Addresses()
        response: Dict[str, Any] = {
            "ip": chooseReplyAddress(sender, addresses),
            "addresses": addresses,
            "hostname": platform.node(),
            "nickname": self.nickname,
            "team_number": self.team_number,
            "version": self.version,
            "username": self.user,
            "directLink": Platform.supportsUsbGadget(),
        }
        return response

    def handlePacket(self, data: bytes, addr: Tuple[str, int]):
        msg = data.decode(errors="ignore")

        if msg != self.ping_message:
            return

        response = self.buildResponse(addr[0])
        payload = json.dumps(response).encode()

        self.sock.sendto(payload, addr)

    def run(self):
        try:
            while True:
                data, addr = self.sock.recvfrom(2048)
                self.handlePacket(data, addr)

        except KeyboardInterrupt:
            log.info("[UDPDeviceResponder] Shutting down")
        finally:
            self.sock.close()
