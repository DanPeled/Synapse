import time
from typing_extensions import Optional
from ntcore import NetworkTableInstance
from synapse.log import log


class NtClient:
    INSTANCE: Optional["NtClient"] = None
    TABLE: str = ""

    def setup(self, server_name: str, name: str, is_server: bool = False) -> bool:
        NtClient.INSTANCE = self
        NtClient.TABLE = name
        self.nt_inst = NetworkTableInstance.getDefault()

        if is_server:
            self.server = NetworkTableInstance.create()
            self.server.startServer(server_name)
            log(f"Server started with name {name}.")
        else:
            self.server = None
        # Client mode
        self.nt_inst.setServer(server_name)
        self.nt_inst.startClient4(name)
        # Attempt to connect with timeout
        timeout = 120  # seconds
        start_time = time.time()
        while not self.nt_inst.isConnected():
            curr = time.time() - start_time
            if curr > timeout:
                log(
                    f"Error: connection to server ({server_name}) from client ({name}) timed out after {curr} seconds"
                )
                return False
            log(f"Trying to connect to {server_name}...")
            time.sleep(1)
        return True
