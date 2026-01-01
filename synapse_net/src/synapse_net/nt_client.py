# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import time
from functools import lru_cache
from typing import Optional

from ntcore import ConnectionInfo, Event, EventFlags, NetworkTableInstance
from synapse.callback import Callback
from synapse.log import log, warn

RemoteConnectionIP = str


@lru_cache
def teamNumberToIP(teamNumber: int, lastOctet: int = 1) -> str:
    """Convert FRC team number to the default 10.TE.AM.X IP format."""
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
        """
        Sets up a NetworkTables client or server.

        Args:
            teamNumber: FRC team number (for default server IP resolution).
            name: Name of this client/server.
            isServer: Whether to run as a local server.
            isSim: Whether running in simulation (connects to localhost).

        Returns:
            True if setup completed (connection may still be in progress).
        """
        NtClient.INSTANCE = self
        NtClient.NT_TABLE = name
        self.nt_inst = NetworkTableInstance.getDefault()
        self.teamNumber = teamNumber

        # Server setup
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

        # Start client
        self.nt_inst.startClient4(name)

        timeout = 10
        start_time = time.time()

        # Connection listener accepts any IP
        def connectionListener(event: Event):
            if isinstance(event.data, ConnectionInfo):
                ip = event.data.remote_ip
                if event.is_(EventFlags.kConnected):
                    log(f"Connected to NetworkTables server ({ip})")
                    NtClient.onConnect.call(ip)
                elif event.is_(EventFlags.kDisconnected):
                    log(f"Disconnected from NetworkTables server ({ip})")
                    NtClient.onDisconnect.call(ip)

        self.nt_inst.addConnectionListener(True, connectionListener)
        if self.server:
            self.server.addConnectionListener(True, connectionListener)

        # Low-latency wait loop (non-blocking, short sleeps)
        while not self.nt_inst.isConnected():
            elapsed = time.time() - start_time
            if elapsed > timeout:
                warn(
                    f"Connection timed out after {elapsed:.2f}s (server: {'127.0.0.1' if isServer else teamNumber}, client: {name})"
                )
                break
            time.sleep(0.02)  # 20ms interval for faster reaction

        return True

    def cleanup(self) -> None:
        """Stops the client and destroys NetworkTables instances."""
        self.nt_inst.disconnect()
        self.nt_inst.stopClient()
        NetworkTableInstance.destroy(self.nt_inst)
        if self.server:
            self.server.stopServer()
            NetworkTableInstance.destroy(self.server)
            self.server = None
