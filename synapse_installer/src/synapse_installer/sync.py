# SPDX-FileCopyrightText: 2025 Dan Peled
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

PackageManager = str
CheckInstalledCmd = str
InstallCmd = str


def setupSudoers(
    executor: CommandExecutor, hostname: str, username: str, password: str
) -> None:
    """Add sudoers entry for passwordless commands via SSH."""
    sudoersLine = f"{username} ALL=(ALL) NOPASSWD:ALL"
    sudoersFile = f"/etc/sudoers.d/{username}-nopasswd"

    # Use sudo -S to provide password automatically
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

    managers: List[tuple[PackageManager, CheckInstalledCmd, InstallCmd]] = [
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


def ensurePython310(executor: CommandExecutor) -> str:
    """Ensure Python 3.10 is installed. Return the python3.10 path."""
    # Check if python3.10 exists
    stdout, stderr, exitCode = executor.execCommand("command -v python3.10")
    if exitCode == 0:
        return "python3.10"

    fprint("[yellow]Python 3.10 not found, installing...[/yellow]")

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

    # Download and compile Python 3.10 from source
    cmds = [
        "cd /tmp",
        "wget -O Python-3.10.12.tgz https://www.python.org/ftp/python/3.10.12/Python-3.10.12.tgz",
        "tar xvf Python-3.10.12.tgz",
        "cd Python-3.10.12",
        "./configure --enable-optimizations",
        "make -j$(nproc)",
        "sudo make altinstall",
    ]
    fullCmd = " && ".join(cmds)
    print("running thingamajig")
    stdout, stderr, exitCode = executor.execCommand(fullCmd)
    if exitCode != 0:
        raise RuntimeError(f"Failed to install Python 3.10:\n{stderr}")

    fprint("[green]Python 3.10 installed successfully[/green]")
    return "python3.10"


def installPipRequirements(
    executor: CommandExecutor,
    requirements: List[str],
    python_cmd: str,
    wplibYear: Optional[str] = None,
) -> None:
    """Install Python pip requirements using the given python command."""
    stdout, stderr, exitCode = executor.execCommand(f"{python_cmd} -m pip freeze")
    installedPackages: dict[str, str] = {}
    for line in stdout.splitlines():
        if "==" in line:
            name, ver = line.strip().split("==", 1)
            installedPackages[name.lower()] = ver

    for i, requirement in enumerate(requirements, start=1):
        if "==" in requirement:
            pkgName, reqVer = requirement.split("==", 1)
        else:
            pkgName, reqVer = requirement, None

        pkgName = pkgName.lower()
        installedVer: Optional[str] = installedPackages.get(pkgName)

        if installedVer is not None and (reqVer is None or installedVer == reqVer):
            fprint(
                f"[green][OK][/green] {pkgName} already installed [{i}/{len(requirements)}]"
            )
            continue

        fprint(f"Installing {pkgName}... [{i}/{len(requirements)}]")

        cmd: str = f"{python_cmd} -m pip install {requirement} "
        if wplibYear:
            cmd += f"--extra-index-url=https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-{wplibYear}/simple/"
        cmd += " --break-system-packages --upgrade-strategy only-if-needed"

        stdout, stderr, exitCode = executor.execCommand(cmd)
        if stderr.strip():
            fprint(f"[red]Install for {pkgName} failed!\n{stderr}[/red]")


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
        installSystemPackage(executor, "libopencv-dev")
        installSystemPackage(executor, "unzip")
        installSystemPackage(executor, "isc-dhcp-client")
        python_cmd = ensurePython310(executor)
        # Upgrade pip
        executor.execCommand(f"{python_cmd} -m ensurepip --upgrade")
        executor.execCommand(
            f"{python_cmd} -m pip install --upgrade pip setuptools wheel"
        )
        installPipRequirements(executor, requirements, python_cmd, wplibYear)
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
    python_cmd = sys.executable
    installPipRequirements(executor, requirements, python_cmd, wplibYear)


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
    syncRequirements(executor, hostname, "root", password, requirements, wplibYear)
