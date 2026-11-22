# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for device-side USB gadget configuration."""

import ipaddress
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from synapse.hardware.metrics import Platform
from synapse.hardware.usb_gadget import (
    GADGET_NAME,
    UsbGadgetConfig,
    UsbGadgetError,
    UsbGadgetManager,
    buildDeviceInfoText,
)


def _completed() -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestUsbGadgetManager(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.configfs = self.root / "config"
        self.storage = self.root / "storage"

        # Pre-create the function directories a real kernel would provide.
        for function in ("ecm.usb0", "mass_storage.0"):
            path = self.configfs / "functions" / function
            path.mkdir(parents=True)
        (self.configfs / "functions" / "ecm.usb0" / "ifname").write_text("usb0\n")

        # Patch the real Platform enum methods, which the manager calls as a
        # class. Platform is an enum and cannot be subclassed.
        self.stack.enter_context(
            patch.object(Platform, "isLinux", staticmethod(lambda: True))
        )
        self.stack.enter_context(
            patch.object(Platform, "supportsUsbGadget", staticmethod(lambda: True))
        )
        self.stack.enter_context(
            patch.object(Platform, "getUsbGadgetUdc", staticmethod(lambda: "fe980000.usb"))
        )

        self.commands = []
        self.manager = UsbGadgetManager(
            configfsRoot=self.configfs,
            storageDir=self.storage,
            platform=Platform,
            runCommand=lambda command: self.commands.append(list(command)) or _completed(),
            commandExists=lambda _name: True,
        )

    def test_detect_udc(self):
        self.assertEqual(self.manager.detectUdc(), "fe980000.usb")

    def test_detect_network_function_prefers_ecm(self):
        self.assertEqual(self.manager.detectNetworkFunction(), "ecm.usb0")

    def test_detect_network_function_falls_back_to_rndis(self):
        import shutil

        shutil.rmtree(self.configfs / "functions" / "ecm.usb0")
        (self.configfs / "functions" / "rndis.0").mkdir()
        self.assertEqual(self.manager.detectNetworkFunction(), "rndis.0")

    def test_detect_network_function_none_available(self):
        import shutil

        shutil.rmtree(self.configfs / "functions")
        with self.assertRaises(UsbGadgetError):
            self.manager.detectNetworkFunction()

    def test_detect_interface(self):
        self.assertEqual(self.manager.detectInterface("ecm.usb0"), "usb0")

    def test_detect_interface_empty(self):
        (self.configfs / "functions" / "ecm.usb0" / "ifname").write_text("")
        with self.assertRaises(UsbGadgetError):
            self.manager.detectInterface("ecm.usb0")

    def test_link_local_pair_is_stable_and_valid(self):
        first = UsbGadgetManager._linkLocalPair("serial-123")
        second = UsbGadgetManager._linkLocalPair("serial-123")
        other = UsbGadgetManager._linkLocalPair("serial-456")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        device = ipaddress.IPv4Address(first[0])
        host = ipaddress.IPv4Address(first[1])
        self.assertTrue(device.is_link_local)
        self.assertTrue(host.is_link_local)
        self.assertNotEqual(device, host)

    def test_start_creates_composite_gadget(self):
        config = self.manager.start(serial="test-serial")

        gadget = self.configfs / GADGET_NAME
        self.assertTrue((gadget / "UDC").read_text() == "fe980000.usb")
        self.assertEqual((gadget / "idVendor").read_text(), "0x1d6b")
        self.assertEqual((gadget / "strings" / "0x409" / "serialnumber").read_text(), "test-serial")

        configDir = gadget / "configs" / "c.1"
        self.assertTrue((configDir / "functions" / "ecm.usb0").is_symlink())
        self.assertTrue((configDir / "functions" / "mass_storage.0").is_symlink())
        self.assertEqual(
            (gadget / "functions" / "mass_storage.0" / "lun.0" / "file").read_text(),
            str(self.storage / "synapse-storage.img"),
        )

        self.assertEqual(config.interface, "usb0")
        self.assertEqual(config.udc, "fe980000.usb")
        self.assertTrue(config.networkFunction.startswith("ecm"))

    def test_start_configures_link_local_address(self):
        config = self.manager.start(serial="test-serial")
        addressCommands = [command for command in self.commands if command[:3] == ["ip", "addr", "replace"]]
        self.assertEqual(len(addressCommands), 1)
        self.assertEqual(addressCommands[0][3], config.deviceCidr)
        self.assertIn("usb0", addressCommands[0])
        self.assertIn(["ip", "link", "set", "usb0", "up"], self.commands)

    def test_start_fails_on_unsupported_platform(self):
        with patch.object(Platform, "isLinux", staticmethod(lambda: False)):
            with self.assertRaises(UsbGadgetError):
                self.manager.start()

    def test_start_fails_without_udc(self):
        with patch.object(Platform, "getUsbGadgetUdc", staticmethod(lambda: None)):
            with self.assertRaises(UsbGadgetError):
                self.manager.start()

    def test_stop_unbinds_gadget(self):
        gadget = self.configfs / GADGET_NAME
        (gadget / "UDC").parent.mkdir(parents=True, exist_ok=True)
        (gadget / "UDC").write_text("fe980000.usb")
        self.manager.stop()
        self.assertEqual((gadget / "UDC").read_text(), "")


class TestUsbGadgetHelpers(unittest.TestCase):
    def test_build_device_info_text(self):
        config = UsbGadgetConfig(
            udc="udc",
            networkFunction="ecm.usb0",
            interface="usb0",
            deviceAddress="169.254.2.10",
            hostAddress="169.254.1.1",
            storageImage=Path("/tmp/image.img"),
            serial="abc",
        )
        text = buildDeviceInfoText(config)
        self.assertIn("169.254.2.10", text)
        self.assertIn("ssh pi@169.254.2.10", text)
        self.assertIn("http://169.254.2.10:3000", text)
