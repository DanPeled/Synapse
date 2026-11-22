# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Device-side USB gadget support for direct coprocessor connections.

When the coprocessor is plugged into a computer with a USB cable, this module
turns the device-side USB port into a composite gadget:

* a USB Ethernet function (ECM/NCM/RNDIS) for SSH, deploy, and the dashboard
* a USB Mass Storage function that exposes a small FAT image with device
  information and a writable drop folder

The gadget uses IPv4 link-local addressing (169.254.0.0/16), which Windows,
macOS, and Linux all configure automatically. That means the computer needs no
manual network setup: plug in the cable, wait a few seconds, and the coprocessor
is reachable at a stable link-local address.

All board-specific details are discovered at runtime:

* the USB Device Controller (UDC) name comes from ``/sys/class/udc``
* available configfs functions are probed before use
* the network interface name is read back from configfs after activation

``Platform`` (in :mod:`synapse.hardware.metrics`) is used for the initial
capability check so unsupported hosts fail fast with a clear message.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from synapse.log import info

from .metrics import Platform

DEFAULT_CONFIGFS = Path("/sys/kernel/config/usb_gadget")
DEFAULT_STORAGE_DIR = Path("/var/lib/synapse/usb_gadget")
GADGET_NAME = "synapse"

USB_VENDOR_ID = "0x1d6b"  # Linux Foundation
USB_PRODUCT_ID = "0x0104"  # Multifunction Composite Gadget
USB_DEVICE_CLASS = "0xef"  # Miscellaneous
USB_DEVICE_SUBCLASS = "0x02"
USB_DEVICE_PROTOCOL = "0x01"
USB_MANUFACTURER = "Synapse"
USB_PRODUCT = "Synapse Coprocessor"

LINK_LOCAL_NETWORK = ipaddress.IPv4Network("169.254.0.0/16")
LINK_LOCAL_PREFIX = 16

# Ordered by preference. ECM is supported natively on Linux and macOS; RNDIS
# is the safest fallback for Windows hosts.
NETWORK_FUNCTIONS = ("ecm.usb0", "ncm.usb0", "rndis.0")

CommandRunner = Callable[[List[str]], "subprocess.CompletedProcess[str]"]


class UsbGadgetError(RuntimeError):
    """Raised when the USB gadget cannot be configured."""


def _runCommand(command: List[str]) -> "subprocess.CompletedProcess[str]":
    """Execute a privileged command, raising a clear error on failure."""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise UsbGadgetError(f"{command[0]} is not installed") from e
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or "").strip()
        raise UsbGadgetError(
            f"Command failed: {' '.join(command)}" + (f"\n{detail}" if detail else "")
        ) from e


class UsbGadgetMode(str, Enum):
    """Which USB Ethernet function the gadget uses."""

    ECM = "ecm.usb0"
    NCM = "ncm.usb0"
    RNDIS = "rndis.0"


@dataclass(frozen=True)
class UsbGadgetConfig:
    """Resolved settings for one gadget instance."""

    udc: str
    networkFunction: str
    interface: str
    deviceAddress: str
    hostAddress: str
    storageImage: Path
    serial: str
    prefixLength: int = LINK_LOCAL_PREFIX

    @property
    def deviceCidr(self) -> str:
        return f"{self.deviceAddress}/{self.prefixLength}"

    @property
    def advertisedAddress(self) -> str:
        return self.deviceAddress


@dataclass
class UsbGadgetManager:
    """Create and manage a composite USB gadget on a Linux coprocessor.

    Parameters allow tests to inject a fake configfs tree and command runner;
    production use relies on the defaults.
    """

    configfsRoot: Path = DEFAULT_CONFIGFS
    storageDir: Path = DEFAULT_STORAGE_DIR
    runCommand: CommandRunner = field(default_factory=lambda: _runCommand)
    commandExists: Callable[[str], bool] = field(
        default_factory=lambda: lambda name: shutil.which(name) is not None
    )
    platform: type[Platform] = Platform

    def isAvailable(self) -> bool:
        """Whether gadget mode can be started on this machine."""
        if not self.platform.isLinux() or not self.platform.supportsUsbGadget():
            return False
        return self.platform.getUsbGadgetUdc() is not None

    def detectUdc(self) -> str:
        """Discover the board's USB Device Controller."""
        udc = self.platform.getUsbGadgetUdc()
        if not udc:
            raise UsbGadgetError(
                "No USB Device Controller found. This board/port does not "
                "support USB gadget mode, or the dwc2/device-mode driver is "
                "not loaded."
            )
        return udc

    def detectNetworkFunction(self) -> str:
        """Pick the first USB Ethernet function available in configfs."""
        functions = self.configfsRoot / "functions"
        for function in NETWORK_FUNCTIONS:
            if (functions / function).exists():
                return function
        available = sorted(p.name for p in functions.iterdir()) if functions.exists() else []
        raise UsbGadgetError(
            "No USB Ethernet gadget function available. "
            f"Looked for {', '.join(NETWORK_FUNCTIONS)}; found: "
            f"{', '.join(available) or 'none'}."
        )

    def detectInterface(self, function: str) -> str:
        """Read the kernel-assigned network interface for a gadget function."""
        path = self.configfsRoot / "functions" / function / "ifname"
        try:
            name = path.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise UsbGadgetError(f"Could not read USB gadget interface name: {e}") from e
        if not name:
            raise UsbGadgetError("USB gadget reported an empty interface name")
        return name

    def resolveConfig(self, serial: Optional[str] = None) -> UsbGadgetConfig:
        """Discover the UDC, function, and link-local addresses for this device."""
        udc = self.detectUdc()
        function = self.detectNetworkFunction()
        deviceSerial = (serial or self._serialNumber()).strip() or udc
        deviceAddress, hostAddress = self._linkLocalPair(deviceSerial)
        return UsbGadgetConfig(
            udc=udc,
            networkFunction=function,
            interface=self.detectInterface(function),
            deviceAddress=deviceAddress,
            hostAddress=hostAddress,
            storageImage=self.storageDir / "synapse-storage.img",
            serial=deviceSerial,
        )

    def start(self, serial: Optional[str] = None) -> UsbGadgetConfig:
        """Enable the composite gadget and return its resolved configuration."""
        if not self.isAvailable():
            raise UsbGadgetError(
                "USB gadget mode is not supported on this platform. "
                f"Detected: {self.platform.getPlatformName()}"
            )

        config = self.resolveConfig(serial)
        gadget = self.configfsRoot / GADGET_NAME

        self._requireCommands(("ip", "dd", "mkfs.vfat"))

        try:
            gadget.mkdir(parents=True, exist_ok=True)
            self._write(gadget / "idVendor", USB_VENDOR_ID)
            self._write(gadget / "idProduct", USB_PRODUCT_ID)
            self._write(gadget / "bDeviceClass", USB_DEVICE_CLASS)
            self._write(gadget / "bDeviceSubClass", USB_DEVICE_SUBCLASS)
            self._write(gadget / "bDeviceProtocol", USB_DEVICE_PROTOCOL)

            strings = gadget / "strings" / "0x409"
            strings.mkdir(parents=True, exist_ok=True)
            self._write(strings / "manufacturer", USB_MANUFACTURER)
            self._write(strings / "product", USB_PRODUCT)
            self._write(strings / "serialnumber", config.serial)

            configDir = gadget / "configs" / "c.1"
            configStrings = configDir / "strings" / "0x409"
            configStrings.mkdir(parents=True, exist_ok=True)
            self._write(configStrings / "configuration", "Synapse direct connection")
            self._write(configDir / "MaxPower", "250")

            self._ensureStorageImage(config.storageImage)
            self._writeStorageInfo(config)
            self._link(configDir / "functions", gadget / "functions" / "mass_storage.0")
            self._write(
                gadget / "functions" / "mass_storage.0" / "lun.0" / "file",
                str(config.storageImage),
            )
            self._link(configDir / "functions", gadget / "functions" / config.networkFunction)

            self._write(gadget / "UDC", config.udc)
            self.runCommand(
                [
                    "ip",
                    "addr",
                    "replace",
                    config.deviceCidr,
                    "brd",
                    "+",
                    "dev",
                    config.interface,
                ]
            )
            self.runCommand(["ip", "link", "set", config.interface, "up"])
        except UsbGadgetError:
            raise
        except OSError as e:
            raise UsbGadgetError(f"Failed to configure USB gadget: {e}") from e

        info(
            f"[UsbGadget] {config.networkFunction} on {config.interface}: "
            f"{config.deviceCidr} (host {config.hostAddress})"
        )
        return config

    def stop(self) -> None:
        """Unbind the gadget so the port can return to host mode."""
        gadget = self.configfsRoot / GADGET_NAME
        try:
            if (gadget / "UDC").exists():
                self._write(gadget / "UDC", "")
        except OSError as e:
            raise UsbGadgetError(f"Failed to stop USB gadget: {e}") from e

    # ------------------------
    # Helpers
    # ------------------------

    @staticmethod
    def _write(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    @staticmethod
    def _link(linkDir: Path, target: Path) -> None:
        linkDir.mkdir(parents=True, exist_ok=True)
        link = linkDir / target.name
        if link.is_symlink() or link.exists():
            return
        link.symlink_to(target)

    @staticmethod
    def _serialNumber() -> str:
        """Return a stable serial from /proc/cpuinfo, the machine ID, or UDC."""
        for candidate in (Path("/proc/cpuinfo"), Path("/etc/machine-id")):
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                if line.lower().startswith(("serial", "machine-id")) or ":" in line:
                    value = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
                    if value:
                        return value
        return os.uname().nodename if hasattr(os, "uname") else "synapse"

    @staticmethod
    def _linkLocalPair(seed: str) -> tuple[str, str]:
        """Derive a stable device/host link-local address pair from a seed."""
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        # Reserve 169.254.1.0/24 for the host side, use the rest for devices.
        deviceHostPart = 0x0200 + int.from_bytes(digest[:2], "big") % 0xFD00
        device = ipaddress.IPv4Address(int(LINK_LOCAL_NETWORK.network_address) + deviceHostPart)
        host = ipaddress.IPv4Address(int(LINK_LOCAL_NETWORK.network_address) + 1)
        return str(device), str(host)

    def _requireCommands(self, commands: tuple[str, ...]) -> None:
        missing = [command for command in commands if not self.commandExists(command)]
        if missing:
            raise UsbGadgetError(
                "Missing required commands for USB gadget mode: " + ", ".join(missing)
            )

    def _ensureStorageImage(self, path: Path) -> None:
        """Create and format the mass-storage backing file if needed."""
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self.runCommand(
            ["dd", "if=/dev/zero", f"of={path}", "bs=1M", "count=64", "status=none"]
        )
        self.runCommand(["mkfs.vfat", "-F", "16", "-n", "SYNAPSE", str(path)])

    def _writeStorageInfo(self, config: UsbGadgetConfig) -> None:
        """Write connection details into the FAT image using mtools, if present."""
        if not self.commandExists("mcopy"):
            return
        infoPath = self.storageDir / "SYNAPSE.txt"
        infoPath.write_text(buildDeviceInfoText(config), encoding="utf-8")
        try:
            self.runCommand(
                ["mcopy", "-o", "-i", str(config.storageImage), str(infoPath), "::SYNAPSE.txt"]
            )
        except UsbGadgetError:
            # The image still works; the info file is a convenience, not a
            # requirement for connectivity.
            pass


def buildDeviceInfoText(config: UsbGadgetConfig) -> str:
    """Return the contents of the info file written to the storage image."""
    return (
        "Synapse Coprocessor\n"
        "===================\n\n"
        f"Device address: {config.advertisedAddress}\n"
        f"Host address:   {config.hostAddress}\n"
        f"USB network:    {config.interface}\n"
        f"Serial:         {config.serial}\n\n"
        "SSH: ssh pi@" + config.advertisedAddress + "\n"
        "Dashboard: http://" + config.advertisedAddress + ":3000\n\n"
        "Use 'python -m synapse_installer deploy' to update the project over USB.\n"
    )


def getUsbGadgetStatus() -> Dict[str, object]:
    """Return a small status dict suitable for the settings UI."""
    manager = UsbGadgetManager()
    return {
        "supported": manager.platform.supportsUsbGadget(),
        "available": manager.isAvailable(),
        "udc": manager.platform.getUsbGadgetUdc() or "",
    }
