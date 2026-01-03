# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import yaml
from rich import print as fprint
from synapse import __version__ as synpaseVersion
from synapse import log
from synapse_installer.deploy import addDeviceConfig
from synapse_installer.util import (NOT_IN_SYNAPSE_PROJECT_ERR,
                                    SYNAPSE_PROJECT_FILE, getDistRequirements,
                                    getUserRequirements)

from .command_executor import (CommandExecutor, LocalCommandExecutor,
                               SSHCommandExecutor)
from .venv_setup import runAndGetWithExecutor

SERVICE_NAME = "synapse-runtime"


def findOrInstallPython(executor: CommandExecutor, minPython: str = "3.12") -> str:
    """
    Finds a Python interpreter >= minPython on the remote system.
    If not found, attempts to install Python from source.
    Returns the command to invoke the interpreter (e.g., "python3.12").
    """

    def runAndGet(cmd: str) -> str:
        stdout, stderr, exitCode = executor.execCommand(cmd)
        if exitCode != 0 and "command not found" not in stderr:
            raise RuntimeError(stderr)
        return stdout.strip()

    candidates = ["python3.12", "python3.13", "python3"]
    pythonCmd = None

    # 1) Try to find a suitable Python
    for cmd in candidates:
        try:
            version = runAndGet(f"{cmd} -c 'import sys; print(sys.version_info[:3])'")
            major, minor, _ = eval(version)
            minMajor, minMinor = map(int, minPython.split("."))
            if major > minMajor or (major == minMajor and minor >= minMinor):
                pythonCmd = cmd
                break
        except Exception:
            continue

    # 2) If not found, install Python
    if not pythonCmd:
        fprint(f"[yellow]Python >= {minPython} not found, installing...[/yellow]")

        # Install build dependencies
        deps = [
            "build-essential",
            "libssl-dev",
            "zlib1g-dev",
            "libncurses5-dev",
            "libncursesw5-dev",
            "libreadline-dev",
            "libsqlite3-dev",
            "libgdbm-dev",
            "libdb5.3-dev",
            "libbz2-dev",
            "libexpat1-dev",
            "liblzma-dev",
            "libffi-dev",
            "uuid-dev",
            "wget",
            "curl",
        ]
        for dep in deps:
            installSystemPackage(executor, dep)

        # Download and build Python from source
        cmds = [
            "cd /tmp",
            "wget -O Python-3.12.2.tgz https://www.python.org/ftp/python/3.12.2/Python-3.12.2.tgz",
            "tar xvf Python-3.12.2.tgz",
            "cd Python-3.12.2",
            "./configure --enable-optimizations",
            "make -j$(nproc)",
            "sudo make altinstall",
        ]
        fullCmd = " && ".join(cmds)
        stdout, stderr, exitCode = executor.execCommand(fullCmd)
        if exitCode != 0:
            raise RuntimeError(f"Failed to install Python 3.12:\n{stderr}")

        fprint("[green]Python 3.12 installed successfully[/green]")
        pythonCmd = "python3.12"

    return pythonCmd


def setupSudoers(
    executor: CommandExecutor, hostname: str, username: str, password: str
) -> None:
    """Add sudoers entry for passwordless commands via SSH."""
    sudoersLine = f"{username} ALL=(ALL) NOPASSWD:ALL"
    sudoersFile = f"/etc/sudoers.d/{username}-nopasswd"

    cmd = f"echo '{password}' | sudo -S bash -c \"echo '{sudoersLine}' > {sudoersFile} && chmod 440 {sudoersFile}\""
    stdout, stderr, exitCode = executor.execCommand(cmd)
    if exitCode != 0 or stderr.strip():
        fprint(f"[red]Failed to setup sudoers on {hostname}:\n{stderr}[/red]")
    else:
        fprint(f"[green]Passwordless sudo added for {hostname}[/green]")


def installSystemPackage(
    executor: CommandExecutor, package: str, useSudo: bool = True
) -> None:
    """Install a system package using the appropriate package manager."""
    sudo: str = "sudo " if useSudo else ""

    managers: List[tuple[str, str, str]] = [
        (
            "apt",
            f"dpkg -s {package} >/dev/null 2>&1",
            f"{sudo}apt install -y {package}",
        ),
        ("dnf", f"rpm -q {package} >/dev/null 2>&1", f"{sudo}dnf install -y {package}"),
        ("yum", f"rpm -q {package} >/dev/null 2>&1", f"{sudo}yum install -y {package}"),
        (
            "pacman",
            f"pacman -Qi {package} >/dev/null 2>&1",
            f"{sudo}pacman -Sy --noconfirm {package}",
        ),
        (
            "apk",
            f"apk info -e {package} >/dev/null 2>&1",
            f"{sudo}apk add --no-cache {package}",
        ),
    ]

    for mgr, checkCmd, installCmd in managers:
        stdout, stderr, exitCode = executor.execCommand(
            f"command -v {mgr} >/dev/null 2>&1"
        )
        if exitCode == 0:
            stdout, stderr, exitCode = executor.execCommand(checkCmd)
            if exitCode == 0:
                print(f"{package} is already installed.")
                return
            print(f"Installing {package} with {mgr}...")
            executor.execCommand(installCmd)
            return

    raise RuntimeError("No supported package manager found")


def ensureVenvWithPython(
    executor: CommandExecutor,
    workingDir: Path,
    requirements: Optional[List[str]] = None,
    minPython: str = "3.12",
    wplibYear: Optional[str] = None,
) -> str:
    """
    Ensure a venv exists at <workingDir>/.venv using Python >= minPython.
    Installs all pip requirements inside it.
    Returns the venv python path.
    """

    venvDir = workingDir / ".venv"
    venvPython = venvDir / "bin" / "python"

    def runAndGet(cmd: str) -> str:
        stdout, stderr, exitCode = executor.execCommand(cmd)
        if exitCode != 0 and "command not found" not in stderr:
            raise RuntimeError(stderr)
        return stdout.strip()

    # 1) Check if venv already exists
    try:
        out = runAndGet(
            f"""
            if [ -x "{venvPython}" ]; then
                "{venvPython}" -c "import sys; print(sys.executable)"
            fi
            """
        )
        venvPythonPath = out if out else None
    except RuntimeError:
        venvPythonPath = None

    # 2) Find or install Python if venv is missing
    if not venvPythonPath:
        pythonCmd = findOrInstallPython(executor, minPython)

        # Create the venv
        print(f"Creating venv with {pythonCmd}...")
        runAndGet(f"cd {workingDir} && {pythonCmd} -m venv .venv")
        runAndGet(f"{venvPython} -m pip install --upgrade pip")
        venvPythonPath = str(venvPython)

    # 3) Install pip requirements inside the venv
    if requirements:
        stdout = runAndGet(f"{venvPythonPath} -m pip freeze")
        installedPackages = {}
        for line in stdout.splitlines():
            if "==" in line:
                name, ver = line.strip().split("==", 1)
                installedPackages[name.lower()] = ver

        for req in requirements:
            if "==" in req:
                pkgName, reqVer = req.split("==", 1)
            else:
                pkgName, reqVer = req, None
            pkgName = pkgName.lower()
            installedVer = installedPackages.get(pkgName)
            if installedVer is not None and (reqVer is None or installedVer == reqVer):
                continue  # already installed

            cmd = f"{venvPythonPath} -m pip install {req}"
            if wplibYear:
                cmd += (
                    f" --extra-index-url="
                    f"https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-{wplibYear}/simple/"
                )
            cmd += " --upgrade-strategy only-if-needed --break-system-packages"
            runAndGet(cmd)

    return venvPythonPath


def syncRequirements(
    executor: CommandExecutor,
    hostname: str,
    username: str,
    password: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    """Sync requirements using the provided executor."""

    try:
        setupSudoers(executor, hostname, username, password)

        # Install system deps
        installSystemPackage(executor, "libopencv-dev")
        installSystemPackage(executor, "unzip")
        installSystemPackage(executor, "isc-dhcp-client")

        # Setup venv and pip packages
        homeDir = runAndGetWithExecutor("echo $HOME", executor)
        workingDir = Path(homeDir) / "Synapse"
        ensureVenvWithPython(
            executor,
            workingDir,
            requirements=requirements,
            wplibYear=wplibYear,
        )

        executor.close()
        fprint(f"[green]Sync completed on {hostname}[/green]")

    except Exception as e:
        fprint(f"[red]{e}\n{traceback.format_exc()}[/red]")


def sync(argv: Optional[List[str]] = None) -> int:
    """Sync devices specified in argv (hostnames)."""
    cwd: Path = Path(os.getcwd())
    if not (cwd / SYNAPSE_PROJECT_FILE).exists():
        fprint(log.MarkupColors.fail(NOT_IN_SYNAPSE_PROJECT_ERR))
        return 0

    deployConfigPath = cwd / SYNAPSE_PROJECT_FILE
    with open(deployConfigPath, "r") as f:
        data: dict = yaml.full_load(f) or {}

    if "deploy" not in data:
        addDeviceConfig(deployConfigPath)
        with open(deployConfigPath, "r") as f:
            data = yaml.full_load(f) or {"deploy": {}}

    if argv is None:
        argv = sys.argv

    any_failure = False

    for currHostname in argv:
        if currHostname in data["deploy"]:
            deviceData = data["deploy"][currHostname]
            try:
                fprint(f"Attempting to sync: {currHostname}@{deviceData['ip']}")
                requirements = getDistRequirements()
                userRequirements = getUserRequirements(Path.cwd() / "pyproject.toml")
                requirements.extend(userRequirements)

                executor = SSHCommandExecutor(
                    hostname=deviceData["ip"],
                    username=deviceData["hostname"],
                    password=deviceData["password"],
                )
                syncRequirements(
                    executor,
                    currHostname,
                    deviceData["hostname"],
                    deviceData["password"],
                    requirements=requirements,
                    wplibYear=synpaseVersion.WPILIB_YEAR,
                )
                executor.close()
            except Exception as e:
                fprint(log.MarkupColors.fail(f"Failed to sync {currHostname}: {e}"))
                any_failure = True
        else:
            fprint(
                log.MarkupColors.fail(
                    f"No device named `{currHostname}` found! skipping..."
                )
            )
            any_failure = True

    return 1 if any_failure else 0


def syncLocal(requirements: List[str], wplibYear: Optional[str] = None) -> None:
    """Sync requirements locally."""
    executor: CommandExecutor = LocalCommandExecutor()
    # python_cmd = sys.executable
    ensureVenvWithPython(executor, Path.cwd(), requirements, wplibYear=wplibYear)


def syncRemote(
    hostname: str,
    ip: str,
    password: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    """Sync requirements on a remote machine via SSH."""
    fprint(f"Connecting to {hostname}@{ip}...")
    executor: CommandExecutor = SSHCommandExecutor(ip, "root", password)
    homeDir = runAndGetWithExecutor("echo $HOME", executor)
    workingDir = Path(homeDir) / "Synapse"
    ensureVenvWithPython(
        executor, workingDir, requirements=requirements, wplibYear=wplibYear
    )
