import os
import subprocess
from abc import abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Final, List, Optional

from synapse.log import err
from synapse.networking import NtClient

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
        self.cpuUptimeCommand = "uptime -p | cut -c 4-"
        self.diskUsageCommand = "df ./ --output=pcent | tail -n +2"


class PiCmds(LinuxCmds):
    def initCmds(self, config: Any) -> None:
        super().initCmds(config)
        self.cpuTemperatureCommand = (
            "sed 's/.\\{3\\}$/.&/' /sys/class/thermal/thermal_zone0/temp"
        )
        self.cpuThrottleReasonCmd = (
            'if   ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x01 )) != 0x00 )); then echo "LOW VOLTAGE"; '
            + ' elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x08 )) != 0x00 )); then echo "HIGH TEMP"; '
            + ' elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x10000 )) != 0x00 )); then echo "Prev. Low Voltage"; '
            + ' elif ((  $(( $(vcgencmd get_throttled | grep -Eo 0x[0-9a-fA-F]*) & 0x80000 )) != 0x00 )); then echo "Prev. High Temp"; '
            + ' else echo "None"; fi'
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

    def executeBashCommand(self, command: str) -> None:
        try:
            result = subprocess.run(
                command, shell=self.shell, capture_output=self.capture_output, text=True
            )
            self.output = result.stdout.strip()
            self.error = result.stderr.strip()
            self.exit_code = result.returncode
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
        self.cmds: Optional[CmdBase] = None
        self.runCommand = ShellExec()

        self.cpuMemSave: Optional[str] = None
        self.gpuMemSave: Optional[str] = None

    def setConfig(self, config) -> None:
        if Platform.isRaspberryPi():
            self.cmds = PiCmds()
        elif Platform.isRK3588():
            self.cmds = RK3588Cmds()
        elif Platform.isLinux():
            self.cmds = LinuxCmds()
        else:
            self.cmds = CmdBase()

        self.cmds.initCmds(config)

    def safeExecute(self, command: str) -> str:
        if not command:
            return ""
        try:
            return self.execute(command)
        except Exception:
            return "****"

    def getMemory(self) -> str:
        if not self.cmds or not self.cmds.cpuMemoryCommand:
            return "0.0"
        if self.cpuMemSave is None:
            self.cpuMemSave = self.execute(self.cmds.cpuMemoryCommand)
        return self.cpuMemSave

    def getTemp(self) -> str:
        return self.safeExecute(self.cmds.cpuTemperatureCommand) if self.cmds else "0.0"

    def getUtilization(self) -> str:
        return self.safeExecute(self.cmds.cpuUtilizationCommand) if self.cmds else "0.0"

    def getUptime(self) -> str:
        return self.safeExecute(self.cmds.cpuUptimeCommand) if self.cmds else "0.0"

    def getThrottleReason(self) -> str:
        return self.safeExecute(self.cmds.cpuThrottleReasonCmd) if self.cmds else "0.0"

    def getNpuUsage(self) -> str:
        return self.safeExecute(self.cmds.npuUsageCommand) if self.cmds else "0.0"

    def getGPUMemorySplit(self) -> str:
        if self.gpuMemSave is None and self.cmds:
            self.gpuMemSave = self.safeExecute(self.cmds.gpuMemoryCommand)
        return self.gpuMemSave or "0.0"

    def getMallocedMemory(self) -> str:
        return self.safeExecute(self.cmds.gpuMemUsageCommand) if self.cmds else "0.0"

    def getUsedDiskPct(self) -> str:
        if self.cmds:
            return (
                self.safeExecute(self.cmds.diskUsageCommand)[:-1]
                if self.safeExecute(self.cmds.diskUsageCommand).endswith("%")
                else self.safeExecute(self.cmds.diskUsageCommand)
            )
        else:
            return "0.0"

    def getUsedRam(self) -> str:
        return self.safeExecute(self.cmds.ramUsageCommand) if self.cmds else "0.0"

    def publishMetrics(self) -> None:
        metrics: List[str] = [
            self.getTemp(),
            self.getUtilization(),
            self.getMemory(),
            self.getThrottleReason(),
            self.getUptime(),
            self.getGPUMemorySplit(),
            self.getUsedRam(),
            self.getMallocedMemory(),
            self.getUsedDiskPct(),
            self.getNpuUsage(),
        ]

        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.nt_inst.getEntry("Synapse/metrics").setStringArray(
                metrics
            )

    def execute(self, command: str) -> str:
        try:
            self.runCommand.executeBashCommand(command)
            return self.runCommand.getOutput()
        except Exception as e:
            err(
                f'Command: "{command}" returned an error!\n'
                f"Output Received: {self.runCommand.getOutput()}\n"
                f"Standard Error: {self.runCommand.getError()}\n"
                f"Command completed: {self.runCommand.isOutputCompleted()}\n"
                f"Error completed: {self.runCommand.isErrorCompleted()}\n"
                f"Exit code: {self.runCommand.getExitCode()}\n"
                f"Exception: {e}"
            )
            return ""
