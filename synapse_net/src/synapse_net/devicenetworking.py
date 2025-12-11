# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
import subprocess
import threading
import time
from typing import Callable, Dict, List

from synapse.log import err, log, warn

virtualLabel = "static"
checkInterval = 5

InterfaceName = str


class NetworkingManager:
    def __init__(self):
        self.staticIpThreads: Dict[InterfaceName, threading.Thread] = {}
        self.threadsStatus: Dict[InterfaceName, bool] = {}

    @staticmethod
    def __runCommand(command: List[str]):
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,  # Hide stdout
                stderr=subprocess.PIPE,  # Capture stderr
                text=True,
            )
        except subprocess.CalledProcessError as e:
            err(f"Command failed: {e}\n{e.stderr.strip()}")

    @staticmethod
    def __interfaceIsUp(interface: InterfaceName):
        try:
            with open(f"/sys/class/net/{interface}/operstate") as f:
                return f.read().strip() == "up"
        except Exception:
            return False

    @staticmethod
    def __ipIsConfigured(interface: InterfaceName, staticIp):
        try:
            output = subprocess.check_output(["ip", "addr", "show", interface])
            return staticIp.split("/")[0].encode() in output
        except Exception:
            return False

    @staticmethod
    def __setStaticIp(interface: InterfaceName, staticIp):
        if not NetworkingManager.__ipIsConfigured(interface, staticIp):
            NetworkingManager.__runCommand(
                ["sudo", "ip", "addr", "add", f"{staticIp}/24", "dev", interface]
            )

    @staticmethod
    def __startDhcp(interface: InterfaceName):
        NetworkingManager.__runCommand(["sudo", "dhclient", "-v", interface])

    @staticmethod
    def __networkThreadLoop(
        interface: InterfaceName, staticIp: str, run: Callable[[], bool]
    ) -> None:
        while run():
            if NetworkingManager.__interfaceIsUp(interface):
                try:
                    NetworkingManager.__setStaticIp(interface, staticIp)
                    NetworkingManager.__startDhcp(interface)
                except subprocess.CalledProcessError as e:
                    err(f"Command failed: {e}")
            else:
                warn(f"{interface} is down. Waiting...")

            time.sleep(checkInterval)

    def configureStaticIP(self, ip: str, interface: InterfaceName) -> None:
        if interface in self.staticIpThreads:
            self.threadsStatus[interface] = False
            self.staticIpThreads[interface].join()
        self.threadsStatus[interface] = True
        self.staticIpThreads[interface] = threading.Thread(
            target=lambda: NetworkingManager.__networkThreadLoop(
                interface, ip, lambda: self.threadsStatus[interface]
            )
        )
        self.staticIpThreads[interface].start()

    def removeStaticIPDecl(self, interface: InterfaceName) -> None:
        if interface in self.staticIpThreads:
            thread = self.staticIpThreads[interface]
            self.threadsStatus[interface] = False
            thread.join()

    def close(self):
        for interface, thread in self.staticIpThreads.items():
            self.threadsStatus[interface] = False
            thread.join()


def setHostname(hostname: str) -> None:
    try:
        # Set temporary hostname
        subprocess.run(["sudo", "hostname", hostname], check=True)

        # Persistently set hostname
        if shutil.which("hostnamectl"):
            subprocess.run(
                ["sudo", "hostnamectl", "set-hostname", hostname], check=True
            )
        else:
            subprocess.run(
                ["sudo", "sh", "-c", f"echo '{hostname}' > /etc/hostname"], check=True
            )

        updateHostsFile(hostname)

        log(f"Hostname successfully set to '{hostname}'")
    except Exception as e:
        err(f"Failed to set hostname: {e}")


def updateHostsFile(new_hostname: str):
    try:
        # Read /etc/hosts using sudo
        result = subprocess.run(
            ["sudo", "cat", "/etc/hosts"], check=True, capture_output=True, text=True
        )
        lines = result.stdout.splitlines()

        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith("127.0.1.1"):
                new_lines.append(f"127.0.1.1\t{new_hostname}")
                replaced = True
            else:
                new_lines.append(line)

        if not replaced:
            new_lines.append(f"127.0.1.1\t{new_hostname}")

        # Write back using tee and sudo
        content = "\n".join(new_lines) + "\n"
        subprocess.run(
            ["sudo", "tee", "/etc/hosts"], input=content, text=True, check=True
        )

    except Exception as e:
        err(f"Failed to update /etc/hosts: {e}")
