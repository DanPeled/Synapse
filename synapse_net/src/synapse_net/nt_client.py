import time
from functools import lru_cache
from typing import Optional

from ntcore import Event, EventFlags, NetworkTableInstance
from synapse.log import log, warn


@lru_cache
def teamNumberToIP(teamNumber: int, lastOctet: int) -> str:
    te = str(teamNumber // 100)
    am = str(teamNumber % 100).zfill(2)
    return f"10.{te}.{am}.{lastOctet}"


class NtClient:
    NT_TABLE: str = "Synapse"
    """
    A class that handles the connection and communication with a NetworkTables server.
    It can be configured as either a client or a server.

    Attributes:
        INSTANCE (Optional[NtClient]): A singleton instance of the NtClient class.
        nt_inst (NetworkTableInstance): The instance of NetworkTableInstance used for communication.
        server (Optional[NetworkTableInstance]): The server instance if the client is running as a server, otherwise None.
    """
    TABLE: str = ""
    INSTANCE: Optional["NtClient"] = None

    def setup(self, teamNumber: int, name: str, isServer: bool, isSim: bool) -> bool:
        """
        Sets up the NetworkTables client or server, and attempts to connect to the specified server.

        Args:
            server_name (str): The name of the NetworkTables server to connect to or host.
            name (str): The name of the client or server instance.
            is_server (bool): Flag indicating whether the instance should act as a server (default is False).

        Returns:
            bool: True if the connection or server start was successful, False if it timed out.
        """
        NtClient.INSTANCE = self
        NtClient.NT_TABLE = name
        # Initialize NetworkTables instance
        self.nt_inst = NetworkTableInstance.getDefault()

        # If acting as a server, create and start the server instance
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

        # Client mode: set the server and start the client
        self.nt_inst.startClient4(name)

        timeout = 10  # seconds
        start_time = time.time()

        def connectionListener(event: Event):
            if event.is_(EventFlags.kConnected):
                log(f"Connected to NetworkTables server ({event.data.remote_ip})")  # pyright: ignore
            if event.is_(EventFlags.kDisconnected):
                log(
                    f"Disconnected from NetworkTables server {event.data.remote_ip}"  # pyright: ignore
                )

        NetworkTableInstance.getDefault().addConnectionListener(
            True, connectionListener
        )

        while not self.nt_inst.isConnected():
            curr = time.time() - start_time
            if curr > timeout:
                warn(
                    f"connection to server ({'127.0.0.1' if isServer else teamNumber}) from client ({name}) timed out after {curr} seconds"
                )
                break
            if not isServer:
                log(f"Trying to connect to {teamNumberToIP(teamNumber, 4)}...")
            else:
                log("Trying to establish connection with server...")
            time.sleep(1)

        return True

    def cleanup(self) -> None:
        self.nt_inst.stopClient()
        NetworkTableInstance.destroy(self.nt_inst)
        if self.server:
            self.server.stopServer()
            NetworkTableInstance.destroy(self.server)
            self.server = None
