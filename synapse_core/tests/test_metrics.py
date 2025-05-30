import unittest
from unittest.mock import mock_open, patch

from synapse.hardware.metrics import (LinuxCmds, PiCmds, Platform, RK3588Cmds,
                                      ShellExec)


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


if __name__ == "__main__":
    unittest.main()
