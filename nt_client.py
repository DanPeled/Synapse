import time
from ntcore import NetworkTableInstance


class NtClient:
    def __init__(self, server_name: str, name: str, is_server: bool = False) -> None:
        self.nt_inst = NetworkTableInstance.getDefault()
        self.nt_inst.setServer(server_name)
        if not is_server:
            self.nt_inst.startClient4(name)

            while not (self.nt_inst.isConnected()):
                print(f"Trying to connect to {server_name}...")
                time.sleep(1)
        else:
            self.nt_inst.startServer(name)
