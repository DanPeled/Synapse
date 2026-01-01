# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import time
from abc import abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Final, Optional

import psutil

# Referenced from  https://github.com/PhotonVision/photonvision/


class OSType(Enum):
    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "MacOS"
    UNKNOWN = "Unknown"


class Platform(Enum):
    WINDOWS_64 = ("Windows x64", "winx64", False, OSType.WINDOWS, True)
    LINUX_32 = ("Linux x86", "linuxx64", False, OSType.LINUX, True)
    LINUX_64 = ("Linux x64", "linuxx64", False, OSType.LINUX, True)
    LINUX_RASPBIAN32 = ("Linux Raspbian 32-bit", "linuxarm32", True, OSType.LINUX, True)
    LINUX_RASPBIAN64 = ("Linux Raspbian 64-bit", "linuxarm64", True, OSType.LINUX, True)
    LINUX_RK3588_64 = (
        "Linux AARCH 64-bit with RK3588",
        "linuxarm64",
        False,
        OSType.LINUX,
        True,
    )
    LINUX_AARCH64 = ("Linux AARCH64", "linuxarm64", False, OSType.LINUX, True)
    LINUX_ARM64 = ("Linux ARM64", "linuxarm64", False, OSType.LINUX, True)
    WINDOWS_32 = ("Windows x86", "windowsx64", False, OSType.WINDOWS, False)
    MACOS = ("Mac OS", "osxuniversal", False, OSType.MACOS, False)
    LINUX_ARM32 = ("Linux ARM32", "linuxarm32", False, OSType.LINUX, False)
    UNKNOWN = ("Unsupported Platform", "", False, OSType.UNKNOWN, False)

    def __init__(
        self,
        description: str,
        nativeLibFolder: str,
        isPi: bool,
        osType: OSType,
        isSupported: bool,
    ) -> None:
        self.__description: Final[str] = description
        self.__nativeLibraryFolderName: Final[str] = nativeLibFolder
        self.__isPi: Final[bool] = isPi
        self.__osType: Final[OSType] = osType
        self.__isSupported: Final[bool] = isSupported

    @classmethod
    def getOSType(cls) -> OSType:
        return Platform.getCurrentPlatform().__osType

    @classmethod
    def isWindows(cls) -> bool:
        return Platform.getCurrentPlatform().__osType == OSType.WINDOWS

    @classmethod
    def isMac(cls) -> bool:
        return Platform.getCurrentPlatform().__osType == OSType.MACOS

    @classmethod
    def isLinux(cls) -> bool:
        return Platform.getCurrentPlatform().__osType == OSType.LINUX

    @classmethod
    def isRaspberryPi(cls) -> bool:
        return Platform.getCurrentPlatform().__isPi

    @classmethod
    def isRK3588(cls) -> bool:
        return Platform.isOrangePi() or Platform.isCoolPi4b() or Platform.isRock5C()

    @classmethod
    def isArm(cls) -> bool:
        arch = (
            os.uname().machine
            if hasattr(os, "uname")
            else os.getenv("PROCESSOR_ARCHITECTURE", "Unknown")
        )
        return "arm" in arch or "aarch" in arch

    @classmethod
    def isOrangePi(cls) -> bool:
        return Platform.fileHasText("/proc/device-tree/model", "Orange Pi")

    @classmethod
    def isCoolPi4b(cls) -> bool:
        return Platform.fileHasText("/proc/device-tree/model", "Cool Pi 4B")

    @classmethod
    def isRock5C(cls) -> bool:
        return Platform.fileHasText("/proc/device-tree/model", "Rock 5C")

    @classmethod
    def getPlatformName(cls) -> str:
        current = Platform.getCurrentPlatform()
        return (
            current.__description
            if current != Platform.UNKNOWN
            else Platform.getUnknownPlatformString()
        )

    @classmethod
    def getNativeLibraryFolderName(cls) -> str:
        return Platform.getCurrentPlatform().__nativeLibraryFolderName

    @classmethod
    def isSupported(cls) -> bool:
        return Platform.getCurrentPlatform().__isSupported

    @classmethod
    def isAthena(cls) -> bool:
        return Path("/usr/local/frc/bin/frcRunRobot.sh").exists()

    @classmethod
    def getCurrentPlatform(cls) -> "Platform":
        os_name = os.uname().sysname if hasattr(os, "uname") else os.name
        os_arch = (
            os.uname().machine
            if hasattr(os, "uname")
            else os.getenv("PROCESSOR_ARCHITECTURE", "Unknown")
        )

        if os_name.startswith("Windows"):
            return Platform.WINDOWS_64 if "64" in os_arch else Platform.WINDOWS_32
        if os_name.startswith("Darwin"):
            return Platform.MACOS
        if os_name.startswith("Linux"):
            if Platform.isPiSbc():
                return (
                    Platform.LINUX_RASPBIAN64
                    if "64" in os_arch
                    else Platform.LINUX_RASPBIAN32
                )
            if Platform.isRK3588():
                return Platform.LINUX_RK3588_64
            if "arm" in os_arch or "aarch" in os_arch:
                return Platform.LINUX_AARCH64
            return Platform.LINUX_64 if "64" in os_arch else Platform.LINUX_32
        return Platform.UNKNOWN

    @classmethod
    def getUnknownPlatformString(cls) -> str:
        return f"Unknown Platform. OS: {os.uname().sysname}, Architecture: {os.uname().machine}"

    @classmethod
    def isPiSbc(cls) -> bool:
        return Platform.fileHasText("/proc/cpuinfo", "Raspberry Pi")

    @classmethod
    def fileHasText(cls, filename: str, text: str) -> bool:
        try:
            with open(filename, "r") as file:
                return any(text in line for line in file)
        except FileNotFoundError:
            return False


class CmdBase:
    def __init__(self):
        # CPU
        self.cpuMemoryCommand: str = ""
        self.cpuTemperatureCommand: str = ""
        self.cpuUtilizationCommand: str = ""
        self.cpuThrottleReasonCmd: str = ""
        self.cpuUptimeCommand: str = ""
        # GPU
        self.gpuMemoryCommand: str = ""
        self.gpuMemUsageCommand: str = ""
        # NPU
        self.npuUsageCommand: str = ""
        # RAM
        self.ramUsageCommand: str = ""
        # Disk
        self.diskUsageCommand: str = ""

    @abstractmethod
    def initCmds(self, config: Any) -> None: ...


class LinuxCmds(CmdBase):
    def initCmds(self, config: Any) -> None:
        self.cpuMemoryCommand = "free -m | awk 'FNR == 2 {print $2}'"
        self.cpuUtilizationCommand = 'top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1}\''
        self.cpuUptimeCommand = "cat /proc/uptime | awk '{print $1}'"
        self.diskUsageCommand = "df ./ --output=pcent | tail -n +2 | tr -d '%'"


class PiCmds(LinuxCmds):
    def initCmds(self, config: Any) -> None:
        super().initCmds(config)
        self.cpuTemperatureCommand = (
            "cat /sys/class/thermal/thermal_zone0/temp | awk '{print $1/1000}'"
        )
        self.cpuThrottleReasonCmd = (
            "if   ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x01 )) != 0x00 )); then echo 1; "
            + " elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x08 )) != 0x00 )); then echo 1; "
            + " elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x10000 )) != 0x00 )); then echo 1; "
            + " elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x80000 )) != 0x00 )); then echo 1; "
            + " else echo 0; fi"
        )
        self.gpuMemoryCommand = "vcgencmd get_mem gpu | grep -Eo '[0-9]+'"
        self.gpuMemUsageCommand = "vcgencmd get_mem malloc | grep -Eo '[0-9]+'"


class RK3588Cmds(LinuxCmds):
    def initCmds(self, config: Any) -> None:
        super().initCmds(config)
        self.cpuTemperatureCommand = "cat /sys/class/thermal/thermal_zone1/temp | awk '{printf \"%.1f\", $1/1000}'"
        self.npuUsageCommand = (
            "cat /sys/kernel/debug/rknpu/load | sed 's/NPU load://; s/^ *//; s/ *$//'"
        )


class ShellExec:
    def __init__(self, capture_output: bool = True, shell: bool = True):
        self.capture_output = capture_output
        self.shell = shell
        self.output: str = ""
        self.error: str = ""
        self.exit_code: int = 0

    def executeBashCommand(self, command: str, timeout: int = 5) -> None:
        try:
            result = subprocess.run(
                command,
                shell=self.shell,
                capture_output=self.capture_output,
                text=True,
                timeout=timeout,  # <-- add timeout here
            )
            self.output = result.stdout.strip()
            self.error = result.stderr.strip()
            self.exit_code = result.returncode
        except subprocess.TimeoutExpired:
            self.error = f"Command timed out after {timeout} seconds"
            self.exit_code = -1
        except KeyboardInterrupt:
            # Optional: clean up or log before re-raising
            print("KeyboardInterrupt: terminating command execution")
            raise
        except Exception as e:
            self.error = str(e)
            self.exit_code = -1

    def getOutput(self) -> str:
        return self.output

    def getError(self) -> str:
        return self.error

    def isOutputCompleted(self) -> bool:
        return bool(self.output)

    def isErrorCompleted(self) -> bool:
        return bool(self.error)

    def getExitCode(self) -> int:
        return self.exit_code


class MetricsManager:
    def __init__(self):
        self.cpuMemSave: Optional[int] = None
        self.gpuMemSave: Optional[int] = None

    def getMemory(self) -> int:
        if self.cpuMemSave is None:
            self.cpuMemSave = psutil.virtual_memory().total // (1024 * 1024)
        return self.cpuMemSave

    def getUsedRam(self) -> int:
        return psutil.virtual_memory().used // (1024 * 1024)

    def getCpuUtilization(self) -> float:
        return psutil.cpu_percent(interval=0.5)

    def getUptime(self) -> float:
        return time.time() - psutil.boot_time()

    def getUsedDiskPct(self) -> float:
        return psutil.disk_usage(".").percent

    def getCpuTemp(self) -> float:
        if not Platform.isLinux():
            return 0.0

        try:
            temps = psutil.sensors_temperatures()
            for label in ("cpu-thermal", "thermal_zone0", "coretemp"):
                if label in temps and temps[label]:
                    return float(temps[label][0].current)
        except Exception:
            pass

        # Fallback for Pi/RK platforms
        if Platform.isRaspberryPi():
            return self._read_temp_sys("/sys/class/thermal/thermal_zone0/temp")
        if Platform.isRK3588():
            return self._read_temp_sys("/sys/class/thermal/thermal_zone1/temp")

        return 0.0

    def getNpuUsage(self) -> float:
        if Platform.isRK3588():
            path = "/sys/kernel/debug/rknpu/load"
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        value = f.read().strip().replace("NPU load:", "").strip()
                        return float(value)
                except Exception:
                    return -1.0
        return 0.0

    def getGPUMemorySplit(self) -> int:
        if Platform.isRaspberryPi():
            config = "/boot/config.txt"
            if os.path.exists(config):
                try:
                    with open(config) as f:
                        for line in f:
                            if line.startswith("gpu_mem"):
                                return int(line.split("=")[1].strip())
                except Exception:
                    return -1
        return 0

    def _read_temp_sys(self, path: str) -> float:
        try:
            with open(path) as f:
                return int(f.read().strip()) / 1000.0
        except Exception:
            return 0.0
