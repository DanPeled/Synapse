# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import ipaddress
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from synapse.log import err, info

CHECK_INTERVAL: int = 5


InterfaceName = str

# Interfaces that should never receive a user-facing static address. The list
# covers loopback, container bridges, virtual machines, VPNs, and similar.
VIRTUAL_INTERFACE_PREFIXES = (
    "lo",
    "docker",
    "veth",
    "br-",
    "virbr",
    "vmnet",
    "tun",
    "tap",
    "wg",
    "tailscale",
    "zt",
    "dummy",
    "can",
    "vcan",
    "bond",
    "team",
    "ppp",
)


class NetworkCommandError(RuntimeError):
    """Raised when a networking command fails."""


def isPhysicalInterface(name: str) -> bool:
    """Return True for interfaces that can carry a robot-network address."""
    return bool(name) and not name.startswith(VIRTUAL_INTERFACE_PREFIXES)


@dataclass(frozen=True)
class StaticAddress:
    """A secondary IPv4 address that is added while DHCP stays enabled."""

    interface: InterfaceName
    address: str
    prefixLength: int = 24

    @property
    def cidr(self) -> str:
        return f"{self.address}/{self.prefixLength}"

    @classmethod
    def parse(
        cls,
        interface: InterfaceName,
        address: str,
        prefixLength: int = 24,
    ) -> Optional["StaticAddress"]:
        interface = (interface or "").strip()
        address = (address or "").strip()

        if not isPhysicalInterface(interface):
            return None

        try:
            ip = ipaddress.IPv4Address(address)
            prefix = int(prefixLength)
        except (ipaddress.AddressValueError, TypeError, ValueError):
            return None

        if not 1 <= prefix <= 32:
            return None

        if (
            ip.is_loopback
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_link_local
            or ip.is_reserved
        ):
            return None

        network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
        if prefix <= 30 and ip in (network.network_address, network.broadcast_address):
            return None

        return cls(interface=interface, address=str(ip), prefixLength=prefix)


class NetworkingManager:
    """Add a static IPv4 address without taking DHCP away from the interface.

    Keeping DHCP enabled is what lets the coprocessor reach the internet when it
    is plugged into an internet-connected router. The static address is added as
    a secondary address so the robot network can still reach the device at a
    predictable address.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current: Optional[StaticAddress] = None
        self._backend: Optional[str] = None

    # ------------------------
    # Command helpers
    # ------------------------

    @staticmethod
    def _runCommand(command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            raise NetworkCommandError(f"{command[0]} is not installed") from e
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            message = f"Command failed: {' '.join(command)}"
            if detail:
                message = f"{message}\n{detail}"
            raise NetworkCommandError(message) from e

    @staticmethod
    def _sudo(command: list[str]) -> list[str]:
        return ["sudo", "-n", *command]

    @staticmethod
    def _interfaceIsUp(interface: InterfaceName) -> bool:
        try:
            with open(f"/sys/class/net/{interface}/operstate", "r") as f:
                return f.read().strip() == "up"
        except Exception:
            return False

    # ------------------------
    # Backend detection
    # ------------------------

    @staticmethod
    def _networkManagerIsRunning() -> bool:
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "RUNNING", "general"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

        return result.stdout.strip().endswith("running")

    @classmethod
    def _detectBackend(cls) -> str:
        if shutil.which("nmcli") and cls._networkManagerIsRunning():
            return "networkmanager"
        if shutil.which("netplan") and Path("/etc/netplan").is_dir():
            return "netplan"
        return "ip"

    # ------------------------
    # NetworkManager backend
    # ------------------------

    @staticmethod
    def _nmcliOutput(args: list[str]) -> Optional[str]:
        """Run a read-only nmcli query and return its stdout, or None."""
        try:
            result = subprocess.run(
                ["nmcli", *args],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return None

        if result.returncode != 0:
            return None

        return result.stdout

    @classmethod
    def _networkManagerConnection(cls, interface: InterfaceName) -> Optional[str]:
        output = cls._nmcliOutput(
            ["-t", "-f", "GENERAL.CONNECTION", "device", "show", interface]
        )
        if output:
            for line in output.splitlines():
                if line.startswith("GENERAL.CONNECTION:"):
                    name = line.split(":", 1)[1].strip()
                    if name and name != "--":
                        return name

        # The device may be down, in which case the active lookup returns
        # nothing. Look for any saved profile bound to this interface so we
        # modify it instead of creating a duplicate profile.
        output = cls._nmcliOutput(["-t", "-f", "NAME", "connection", "show"])
        if output:
            for name in output.splitlines():
                name = name.strip()
                if not name:
                    continue
                profileInterface = cls._nmcliOutput(
                    ["-g", "connection.interface-name", "connection", "show", name]
                )
                if profileInterface and profileInterface.strip() == interface:
                    return name

        return None

    @classmethod
    def _createNetworkManagerConnection(cls, interface: InterfaceName) -> str:
        name = f"synapse-{interface}"
        cls._runCommand(
            cls._sudo(
                [
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "ethernet",
                    "ifname",
                    interface,
                    "con-name",
                    name,
                    "ipv4.method",
                    "auto",
                ]
            )
        )
        return name

    @classmethod
    def _applyNetworkManager(cls, address: StaticAddress) -> None:
        name = cls._networkManagerConnection(address.interface)
        if name is None:
            name = cls._createNetworkManagerConnection(address.interface)

        cls._runCommand(
            cls._sudo(
                [
                    "nmcli",
                    "connection",
                    "modify",
                    name,
                    "ipv4.method",
                    "auto",
                    "ipv4.addresses",
                    address.cidr,
                ]
            )
        )
        cls._runCommand(cls._sudo(["nmcli", "connection", "up", name]))

    @classmethod
    def _clearNetworkManager(cls, address: StaticAddress) -> None:
        name = cls._networkManagerConnection(address.interface)
        if name is None:
            return

        cls._runCommand(
            cls._sudo(
                [
                    "nmcli",
                    "connection",
                    "modify",
                    name,
                    "ipv4.addresses",
                    "",
                ]
            )
        )
        cls._runCommand(cls._sudo(["nmcli", "connection", "up", name]))

    # ------------------------
    # netplan backend
    # ------------------------

    @classmethod
    def _applyNetplan(cls, address: StaticAddress) -> None:
        prefix = f"ethernets.{address.interface}"
        cls._runCommand(
            cls._sudo(
                [
                    "netplan",
                    "set",
                    "--origin-hint",
                    "synapse-static",
                    f"{prefix}.dhcp4=true",
                ]
            )
        )
        cls._runCommand(
            cls._sudo(
                [
                    "netplan",
                    "set",
                    "--origin-hint",
                    "synapse-static",
                    f"{prefix}.addresses=[{address.cidr}]",
                ]
            )
        )
        cls._runCommand(cls._sudo(["netplan", "apply"]))

    @classmethod
    def _clearNetplan(cls, address: StaticAddress) -> None:
        prefix = f"ethernets.{address.interface}"
        cls._runCommand(
            cls._sudo(
                [
                    "netplan",
                    "set",
                    "--origin-hint",
                    "synapse-static",
                    f"{prefix}.addresses=NULL",
                ]
            )
        )
        cls._runCommand(cls._sudo(["netplan", "apply"]))

    # ------------------------
    # Generic ip fallback
    # ------------------------

    @staticmethod
    def _ipAddressIsConfigured(address: StaticAddress) -> bool:
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "dev", address.interface],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return False

        return result.returncode == 0 and address.cidr in result.stdout

    @classmethod
    def _applyIpAddress(cls, address: StaticAddress) -> None:
        if cls._ipAddressIsConfigured(address):
            return

        cls._runCommand(
            cls._sudo(["ip", "addr", "add", address.cidr, "dev", address.interface])
        )
        cls._runCommand(cls._sudo(["ip", "link", "set", address.interface, "up"]))

    @classmethod
    def _removeIpAddress(cls, address: StaticAddress) -> None:
        if not cls._ipAddressIsConfigured(address):
            return

        cls._runCommand(
            cls._sudo(["ip", "addr", "del", address.cidr, "dev", address.interface])
        )

    # ------------------------
    # Fallback worker
    # ------------------------

    def _networkLoop(self, address: StaticAddress) -> None:
        while not self._stop_event.wait(CHECK_INTERVAL):
            if not self._interfaceIsUp(address.interface):
                continue

            try:
                self._applyIpAddress(address)
            except NetworkCommandError as e:
                err(f"Networking thread error: {e}")

    def _startWorkerLocked(self, address: StaticAddress) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._networkLoop,
            args=(address,),
            daemon=True,
        )
        self._thread.start()

    def _stopWorkerLocked(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5)
        self._thread = None

    # ------------------------
    # Public API
    # ------------------------

    def setStaticAddress(self, address: StaticAddress) -> bool:
        """Add or replace the static address while keeping DHCP enabled."""
        with self._lock:
            self._stopWorkerLocked()
            backend = self._detectBackend()

            # NetworkManager and netplan replace the address they manage, but
            # `ip addr add` would fail with "File exists" when only the prefix
            # changed, so remove the old address first on that path.
            previous = self._current
            if previous is not None and previous != address and self._backend == "ip":
                try:
                    self._removeIpAddress(previous)
                except NetworkCommandError as e:
                    err(f"Failed to remove previous static IP {previous.cidr}: {e}")

            self._current = None
            self._backend = None

            try:
                if backend == "networkmanager":
                    self._applyNetworkManager(address)
                elif backend == "netplan":
                    self._applyNetplan(address)
                else:
                    self._applyIpAddress(address)
                    self._startWorkerLocked(address)
            except NetworkCommandError as e:
                err(
                    f"Failed to configure static IP {address.cidr} "
                    f"on {address.interface}: {e}"
                )
                return False

            self._backend = backend
            self._current = address
            info(
                f"Static IP {address.cidr} added on {address.interface}; "
                "DHCP remains enabled"
            )
            return True

    def removeStaticAddress(self) -> bool:
        """Remove the managed static address without touching DHCP."""
        with self._lock:
            self._stopWorkerLocked()

            current = self._current
            backend = self._backend
            if current is None:
                return True

            try:
                if backend == "networkmanager":
                    self._clearNetworkManager(current)
                elif backend == "netplan":
                    self._clearNetplan(current)
                else:
                    self._removeIpAddress(current)
            except NetworkCommandError as e:
                err(f"Failed to remove static IP {current.cidr}: {e}")
                return False

            self._current = None
            self._backend = None
            info(f"Static IP {current.cidr} removed from {current.interface}")
            return True

    def close(self) -> None:
        """Shutdown the manager cleanly."""
        with self._lock:
            self._stopWorkerLocked()
        info("NetworkingManager shut down")


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
        info(f"Hostname set to '{hostname}'")

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
