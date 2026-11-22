# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock, call, mock_open, patch

from synapse.hardware.metrics import (
    LinuxCmds,
    MetricsManager,
    PiCmds,
    Platform,
    RK3588Cmds,
    ShellExec,
)


class TestPlatformDetection(unittest.TestCase):
    @patch("os.uname")
    def test_get_current_platform_linux_arm64(self, mock_uname):
        mock_uname.return_value = type(
            "uname", (), {"sysname": "Linux", "machine": "aarch64"}
        )
        with (
            patch.object(Platform, "isPiSbc", return_value=False),
            patch.object(Platform, "isRK3588", return_value=False),
        ):
            platform = Platform.getCurrentPlatform()
            self.assertEqual(platform, Platform.LINUX_AARCH64)

    @patch("os.uname")
    def test_get_current_platform_raspberry_pi(self, mock_uname):
        mock_uname.return_value = type(
            "uname", (), {"sysname": "Linux", "machine": "armv7l"}
        )
        with patch.object(Platform, "isPiSbc", return_value=True):
            platform = Platform.getCurrentPlatform()
            self.assertEqual(platform, Platform.LINUX_RASPBIAN32)

    def test_file_has_text_found(self):
        mocked_content = "This is a Raspberry Pi\n"
        with patch("builtins.open", mock_open(read_data=mocked_content)):
            self.assertTrue(Platform.fileHasText("/proc/cpuinfo", "Raspberry Pi"))

    def test_file_has_text_not_found(self):
        mocked_content = "Something else\n"
        with patch("builtins.open", mock_open(read_data=mocked_content)):
            self.assertFalse(Platform.fileHasText("/proc/cpuinfo", "Raspberry Pi"))

    def test_file_has_text_file_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertFalse(Platform.fileHasText("/not/found", "text"))

    def test_supports_usb_gadget(self):
        with patch.object(Platform, "getCurrentPlatform", return_value=Platform.LINUX_RASPBIAN64):
            self.assertTrue(Platform.supportsUsbGadget())
        with patch.object(Platform, "getCurrentPlatform", return_value=Platform.WINDOWS_64):
            self.assertFalse(Platform.supportsUsbGadget())

    def test_get_usb_gadget_udc(self):
        with patch("synapse.hardware.metrics.Path") as pathCls:
            pathCls.return_value.iterdir.return_value = [
                MagicMock(name="fe980000.usb"),
            ]
            for entry in pathCls.return_value.iterdir.return_value:
                entry.is_dir.return_value = True
                entry.name = "fe980000.usb"
            self.assertEqual(Platform.getUsbGadgetUdc(), "fe980000.usb")


class TestShellExec(unittest.TestCase):
    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        mock_run.return_value = type(
            "Result", (), {"stdout": "output\n", "stderr": "", "returncode": 0}
        )()
        exec = ShellExec()
        exec.executeBashCommand("echo Hello")
        self.assertEqual(exec.getOutput(), "output")
        self.assertEqual(exec.getError(), "")
        self.assertEqual(exec.getExitCode(), 0)

    @patch("subprocess.run", side_effect=Exception("fail"))
    def test_execute_failure(self, mock_run):
        exec = ShellExec()
        exec.executeBashCommand("bad command")
        self.assertEqual(exec.getError(), "fail")
        self.assertEqual(exec.getExitCode(), -1)


class TestCmds(unittest.TestCase):
    def test_linux_cmds(self):
        cmds = LinuxCmds()
        cmds.initCmds(None)
        self.assertIn("free -m", cmds.cpuMemoryCommand)
        self.assertIn("df ./", cmds.diskUsageCommand)

    def test_pi_cmds(self):
        cmds = PiCmds()
        cmds.initCmds(None)
        self.assertIn("vcgencmd get_mem gpu", cmds.gpuMemoryCommand)
        self.assertIn("thermal_zone0", cmds.cpuTemperatureCommand)

    def test_rk3588_cmds(self):
        cmds = RK3588Cmds()
        cmds.initCmds(None)
        self.assertIn("thermal_zone1", cmds.cpuTemperatureCommand)
        self.assertIn("rknpu/load", cmds.npuUsageCommand)


class TestMetricsManager(unittest.TestCase):
    def setUp(self):
        self.metrics = MetricsManager()

    @patch("psutil.virtual_memory")
    def test_getMemory(self, mock_virtual_memory):
        mock_virtual_memory.return_value = MagicMock(total=8 * 1024**3)  # 8GB
        mem = self.metrics.getMemory()
        self.assertEqual(mem, 8192)  # 8GB in MB

    @patch("psutil.virtual_memory")
    def test_getUsedRam(self, mock_virtual_memory):
        mock_virtual_memory.return_value = MagicMock(used=2 * 1024**3)  # 2GB
        used_ram = self.metrics.getUsedRam()
        self.assertEqual(used_ram, 2048)

    @patch("psutil.cpu_percent")
    def test_getUtilization_is_non_blocking_and_primed(self, mock_cpu_percent):
        mock_cpu_percent.return_value = 45.5

        # The first non-blocking sample only establishes a psutil baseline.
        self.assertEqual(self.metrics.getCpuUtilization(), 0.0)
        mock_cpu_percent.assert_called_once_with(interval=None)

    @patch("psutil.cpu_percent")
    def test_sample_uses_explicit_timestamps_and_throttles(self, mock_cpu_percent):
        mock_cpu_percent.side_effect = [0.0, 45.5, 90.0]
        metrics = MetricsManager(cpuSampleInterval=1.0)

        self.assertEqual(metrics.sampleCpuUtilization(now=100.0), 0.0)
        self.assertEqual(metrics.sampleCpuUtilization(now=100.5), 0.0)
        # A sample too soon after the previous one reuses the cached value.
        mock_cpu_percent.assert_called_once_with(interval=None)

        self.assertEqual(metrics.sampleCpuUtilization(now=101.0), 45.5)
        self.assertEqual(metrics.sampleCpuUtilization(now=101.5), 45.5)
        self.assertEqual(metrics.sampleCpuUtilization(now=102.0), 90.0)
        self.assertEqual(mock_cpu_percent.call_args_list, [call(interval=None)] * 3)

    @patch("psutil.cpu_percent", side_effect=[0.0, 55.5])
    @patch("synapse.hardware.metrics.time.monotonic", side_effect=[10.0, 11.0])
    def test_getUtilization_uses_default_monotonic_clock(
        self, mock_monotonic, mock_cpu_percent
    ):
        metrics = MetricsManager()

        self.assertEqual(metrics.getCpuUtilization(), 0.0)
        self.assertEqual(metrics.getCpuUtilization(), 55.5)
        self.assertEqual(mock_monotonic.call_count, 2)

    @patch("time.time", return_value=10000)
    @patch("psutil.boot_time", return_value=9000)
    def test_getUptime(self, mock_boot_time, mock_time):
        uptime = self.metrics.getUptime()
        self.assertEqual(uptime, 1000)

    @patch("psutil.disk_usage")
    def test_getUsedDiskPct(self, mock_disk_usage):
        mock_disk_usage.return_value = MagicMock(percent=75.3)
        usage = self.metrics.getUsedDiskPct()
        self.assertEqual(usage, 75.3)

    @patch("psutil.sensors_temperatures")
    def test_getTemp_with_psutil(self, mock_sensors):
        mock_sensors.return_value = {"cpu-thermal": [MagicMock(current=55.5)]}
        temp = self.metrics.getCpuTemp()
        self.assertEqual(temp, 55.5)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="NPU load: 33.7")
    def test_getNpuUsage(self, mock_file, mock_exists):
        # Patch Platform.isRK3588 to True for this test
        with patch("synapse.hardware.metrics.Platform.isRK3588", return_value=True):
            npu = self.metrics.getNpuUsage()
            self.assertAlmostEqual(npu, 33.7)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="gpu_mem=128")
    def test_getGPUMemorySplit(self, mock_file, mock_exists):
        with patch(
            "synapse.hardware.metrics.Platform.isRaspberryPi", return_value=True
        ):
            gpu_mem = self.metrics.getGPUMemorySplit()
            self.assertEqual(gpu_mem, 128)


if __name__ == "__main__":
    unittest.main()
