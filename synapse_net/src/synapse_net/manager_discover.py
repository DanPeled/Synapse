# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import platform
import socket
from typing import Tuple

import synapse.log as log
from synapse.util import getIP


class UDPDeviceResponder:
    def __init__(
        self,
        nickname: str,
        team_number: int,
        version: str,
        ping_message: str = "PING_DISCOVERY",
        port: int = 45454,
    ):
        self.port = port
        self.nickname = nickname
        self.team_number = team_number
        self.version = version
        self.ping_message = ping_message

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.port))

        log.log(f"[UDPDeviceResponder] Listening on port {self.port}")

    def buildResponse(self) -> dict:
        return {
            "ip": getIP(),
            "hostname": platform.node(),
            "nickname": self.nickname,
            "team_number": self.team_number,
            "version": self.version,
        }

    def handlePacket(self, data: bytes, addr: Tuple[str, int]):
        msg = data.decode(errors="ignore")

        if msg != self.ping_message:
            return

        response = self.buildResponse()
        payload = json.dumps(response).encode()

        self.sock.sendto(payload, addr)

    def run(self):
        try:
            while True:
                data, addr = self.sock.recvfrom(2048)
                self.handlePacket(data, addr)

        except KeyboardInterrupt:
            log.log("[UDPDeviceResponder] Shutting down")
        finally:
            self.sock.close()
