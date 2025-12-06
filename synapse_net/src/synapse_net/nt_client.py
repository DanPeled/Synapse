# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import lru_cache
from typing import Optional

from ntcore import ConnectionInfo, Event, EventFlags, NetworkTableInstance
from synapse.callback import Callback
from synapse.log import log

RemoteConnectionIP = str


@lru_cache
def teamNumberToIP(teamNumber: int, lastOctet: int = 1) -> str:
    te = str(teamNumber // 100)
    am = str(teamNumber % 100).zfill(2)
    return f"10.{te}.{am}.{lastOctet}"


class NtClient:
    NT_TABLE: str = "Synapse"
    TABLE: str = ""
    INSTANCE: Optional["NtClient"] = None

    onConnect: Callback[RemoteConnectionIP] = Callback()
    onDisconnect: Callback[RemoteConnectionIP] = Callback()

    def setup(self, teamNumber: int, name: str, isServer: bool, isSim: bool) -> bool:
        NtClient.INSTANCE = self
        NtClient.NT_TABLE = name

        self.nt_inst = NetworkTableInstance.getDefault()
        self.teamNumber = teamNumber

        if isServer:
            self.server = NetworkTableInstance.create()
            self.server.startServer("127.0.0.1")
            self.nt_inst.setServer("127.0.0.1")
        else:
            self.server = None
            if isSim:
                self.nt_inst.setServer("127.0.0.1")
            else:
                self.nt_inst.setServerTeam(teamNumber)

        self.nt_inst.startClient4(name)

        def connectionListener(event: Event):
            if event.is_(EventFlags.kConnected):
                assert isinstance(event.data, ConnectionInfo)

                if event.data.remote_ip == teamNumberToIP(self.teamNumber):
                    log(f"Connected to NetworkTables server ({event.data.remote_ip})")
                    NtClient.onConnect.call(event.data.remote_ip)

            elif event.is_(EventFlags.kDisconnected):
                assert isinstance(event.data, ConnectionInfo)

                if event.data.remote_ip == teamNumberToIP(self.teamNumber):
                    log(
                        f"Disconnected from NetworkTables server {event.data.remote_ip}"
                    )
                    NtClient.onDisconnect.call(event.data.remote_ip)

        self.nt_inst.addConnectionListener(True, connectionListener)

        if self.server is not None:
            self.server.addConnectionListener(True, connectionListener)

        # NOTE:
        # Removed blocking wait loop here.
        # Connection is now fully event-driven via listeners.

        return True

    def cleanup(self) -> None:
        self.nt_inst.stopClient()
        NetworkTableInstance.destroy(self.nt_inst)

        if self.server:
            self.server.stopServer()
            NetworkTableInstance.destroy(self.server)
            self.server = None
