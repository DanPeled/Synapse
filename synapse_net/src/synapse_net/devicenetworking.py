# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
import subprocess
import threading
from typing import Optional

from synapse.log import err, log, warn

CHECK_INTERVAL: int = 5


InterfaceName = str


class NetworkingManager:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------
    # Internal helpers
    # ------------------------

    @staticmethod
    def _runCommand(command: list[str]) -> None:
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            err(f"Command failed: {e}\n{e.stderr.strip()}")

    @staticmethod
    def _interfaceIsUp(interface: InterfaceName) -> bool:
        try:
            with open(f"/sys/class/net/{interface}/operstate", "r") as f:
                return f.read().strip() == "up"
        except Exception:
            return False

    @staticmethod
    def _ipIsConfigured(interface: InterfaceName, staticIp: str) -> bool:
        """Check if *exact* static IP (with mask) is present."""
        try:
            output = subprocess.check_output(["ip", "addr", "show", interface])
            return staticIp.encode() in output
        except Exception:
            return False

    @staticmethod
    def _setStaticIp(interface: InterfaceName, staticIp: str) -> None:
        if not NetworkingManager._ipIsConfigured(interface, staticIp):
            NetworkingManager._runCommand(
                ["sudo", "ip", "addr", "add", staticIp, "dev", interface]
            )
            log(f"Static IP {staticIp} applied on {interface}")

    @staticmethod
    def _startDhcp(interface: InterfaceName) -> None:
        # dhclient can block → fire and forget
        subprocess.Popen(
            ["dhclient", "-v", interface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"DHCP started on {interface}")

    # ------------------------
    # Thread worker
    # ------------------------

    def _networkLoop(self, interface: InterfaceName, staticIp: str) -> None:
        staticAssigned = False
        dhcpStarted = False

        while not self._stop_event.is_set():
            try:
                if self._interfaceIsUp(interface):
                    if not staticAssigned:
                        self._setStaticIp(interface, staticIp)
                        staticAssigned = True

                    if not dhcpStarted:
                        self._startDhcp(interface)
                        dhcpStarted = True
                else:
                    warn(f"{interface} is down, waiting...")
                    staticAssigned = False
                    dhcpStarted = False

            except Exception as e:
                err(f"Networking thread error: {e}")

            self._stop_event.wait(CHECK_INTERVAL)

    # ------------------------
    # Public API
    # ------------------------

    def configureStaticIp(self, staticIp: str, interface: InterfaceName) -> None:
        """Start (or restart) the background worker."""
        with self._lock:
            self._stopWorkerLocked()

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._networkLoop,
                args=(interface, staticIp),
                daemon=True,
            )
            self._thread.start()

        log(f"Started static IP manager for {interface}")

    def removeStaticIp(self) -> None:
        """Stop the background worker."""
        with self._lock:
            self._stopWorkerLocked()
        log("Stopped static IP manager")

    def close(self) -> None:
        """Shutdown the manager cleanly."""
        with self._lock:
            self._stopWorkerLocked()
        log("NetworkingManager shut down")

    # ------------------------
    # Internal lifecycle
    # ------------------------

    def _stopWorkerLocked(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5)
        self._thread = None


# ------------------------
# Hostname helpers
# ------------------------


def setHostname(hostname: str) -> None:
    try:
        subprocess.run(["sudo", "hostname", hostname], check=True)

        if shutil.which("hostnamectl"):
            subprocess.run(
                ["sudo", "hostnamectl", "set-hostname", hostname], check=True
            )
        else:
            subprocess.run(
                ["sudo", "sh", "-c", f"echo '{hostname}' > /etc/hostname"],
                check=True,
            )

        updateHostsFile(hostname)
        log(f"Hostname set to '{hostname}'")

    except Exception as e:
        err(f"Failed to set hostname: {e}")


def updateHostsFile(newHostname: str) -> None:
    try:
        result = subprocess.run(
            ["sudo", "cat", "/etc/hosts"],
            check=True,
            capture_output=True,
            text=True,
        )

        lines = result.stdout.splitlines()

        updatedLines: list[str] = []
        replaced = False

        for line in lines:
            if line.startswith("127.0.1.1"):
                updatedLines.append(f"127.0.1.1\t{newHostname}")
                replaced = True
            else:
                updatedLines.append(line)

        if not replaced:
            updatedLines.append(f"127.0.1.1\t{newHostname}")

        content = "\n".join(updatedLines) + "\n"

        subprocess.run(
            ["sudo", "tee", "/etc/hosts"],
            input=content,
            text=True,
            stdout=subprocess.DEVNULL,
            check=True,
        )

    except Exception as e:
        err(f"Failed to update /etc/hosts: {e}")
