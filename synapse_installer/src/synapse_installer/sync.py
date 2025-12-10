# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
import sys
import traceback
from typing import List, Optional

from rich import print as fprint
from synapse import log
from synapse_installer.deploy import addDeviceConfig
from synapse_installer.util import (
    NOT_IN_SYNAPSE_PROJECT_ERR,
    SYNAPSE_PROJECT_FILE,
    getDistRequirements,
    getUserRequirements,
)
import yaml

from .command_executor import CommandExecutor, LocalCommandExecutor, SSHCommandExecutor

PackageManager = str
CheckInstalledCmd = str
InstallCmd = str


def setupSudoers(executor: CommandExecutor, hostname: str) -> None:
    """Add sudoers entry for passwordless commands."""
    sudoersLine: str = (
        "root ALL=(ALL) NOPASSWD: "
        "/bin/hostname, /usr/bin/hostnamectl, /sbin/ip, "
        "/usr/bin/tee, /bin/cat, /bin/sh"
    )
    sudoersFile: str = "/etc/sudoers.d/root-custom-host-config"

    setupSudoersCmd: str = (
        f"echo '{sudoersLine}' | tee {sudoersFile} > /dev/null && "
        f"chmod 440 {sudoersFile}"
    )

    stdout, stderr, exitCode = executor.execCommand(setupSudoersCmd)
    if stderr.strip():
        fprint(f"[red]Failed to setup sudoers on {hostname}:\n{stderr}[/red]")
    else:
        fprint(f"[green]Sudoers rule added on {hostname}[/green]")


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


def installPipRequirements(
    executor: CommandExecutor,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    """Install Python pip requirements using venv Python."""
    stdout, stderr, exitCode = executor.execCommand("python -m pip freeze")
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
                f"[green][OK][/green] {pkgName} already installed "
                f"[{i}/{len(requirements)}]"
            )
            continue

        fprint(f"Installing {pkgName}... [{i}/{len(requirements)}]")

        cmd: str = f"python -m pip install {requirement} "
        if wplibYear:
            cmd += (
                f"--extra-index-url=https://wpilib.jfrog.io/artifactory/api/pypi/"
                f"wpilib-python-release-{wplibYear}/simple/ "
            )
        cmd += "--break-system-packages --upgrade-strategy only-if-needed"

        stdout, stderr, exitCode = executor.execCommand(cmd)
        if stderr.strip():
            fprint(f"[red]Install for {pkgName} failed!\n{stderr}[/red]")


def sync(argv: Optional[List[str]] = None) -> int:
    """
    Sync devices specified in argv (hostnames).
    Returns 0 if all succeeded, 1 if any failure occurred.
    """
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

    argc = len(argv)
    if argc < 2:
        fprint(log.MarkupColors.fail("No hostname to deploy to specified!"))
        return 1

    any_failure = False

    for i in range(1, argc):
        currHostname = argv[i]
        if currHostname in data["deploy"]:
            deviceData = data["deploy"][currHostname]
            try:
                requirements = getDistRequirements()
                userRequirements = getUserRequirements(Path.cwd() / "pyproject.toml")
                requirements.extend(userRequirements)

                executor = SSHCommandExecutor(
                    hostname=deviceData["ip"],
                    username="root",
                    password=deviceData["password"],
                )
                syncRequirements(
                    executor,
                    deviceData["hostname"],
                    requirements=requirements,
                )
                executor.close()
            except Exception as e:
                fprint(log.MarkupColors.fail(f"Failed to sync {currHostname}: {e}"))
                any_failure = True
        else:
            fprint(
                log.MarkupColors.fail(
                    f"No device named: `{currHostname}` found! skipping..."
                )
            )
            any_failure = True

    return 1 if any_failure else 0


def syncRequirements(
    executor: CommandExecutor,
    hostname: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    """Sync requirements using the provided executor."""
    try:
        setupSudoers(executor, hostname)
        installSystemPackage(executor, "libopencv-dev")
        installPipRequirements(executor, requirements, wplibYear)
        executor.close()
        print(f"Sync completed on {hostname}")
    except Exception as e:
        fprint(f"[red]{e}\n{traceback.format_exc()}[/red]")


def syncLocal(requirements: List[str], wplibYear: Optional[str] = None) -> None:
    """Sync requirements locally."""
    executor: CommandExecutor = LocalCommandExecutor()
    syncRequirements(executor, "localhost", requirements, wplibYear)


def syncRemote(
    hostname: str,
    ip: str,
    password: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    """Sync requirements on a remote machine via SSH."""
    print(f"Connecting to {hostname}@{ip}...")
    executor: CommandExecutor = SSHCommandExecutor(ip, "root", password)
    syncRequirements(executor, hostname, requirements, wplibYear)
