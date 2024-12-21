import time
from typing_extensions import Optional
from ntcore import NetworkTableInstance
from synapse.log import err, log


class NtClient:
    """
    A class that handles the connection and communication with a NetworkTables server.
    It can be configured as a client or a server.

    Attributes:
        INSTANCE (Optional[NtClient]): A singleton instance of the NtClient class.
        nt_inst (NetworkTableInstance): The instance of NetworkTableInstance used for communication.
        server (Optional[NetworkTableInstance]): The server instance if the client is running as a server, otherwise None.
    """

    INSTANCE: Optional["NtClient"] = None

    def setup(self, server_name: str, name: str, is_server: bool = False) -> bool:
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

        # Initialize NetworkTables instance
        self.nt_inst = NetworkTableInstance.getDefault()

        # If acting as a server, create and start the server instance
        if is_server:
            self.server = NetworkTableInstance.create()
            self.server.startServer(server_name)
            log(f"Server started with name {name}.")
        else:
            self.server = None

        # Client mode: set the server and start the client
        self.nt_inst.setServer(server_name)
        self.nt_inst.startClient4(name)

        # Attempt to connect to the server with a timeout of 120 seconds
        timeout = 120  # seconds
        start_time = time.time()

        while not self.nt_inst.isConnected():
            curr = time.time() - start_time
            if curr > timeout:
                err(
                    f"connection to server ({server_name}) from client ({name}) timed out after {curr} seconds"
                )
                return False
            log(f"Trying to connect to {server_name}...")
            time.sleep(1)

        return True
