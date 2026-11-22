# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import shlex
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from rich import print as fprint
from synapse import __version__ as synapseVersion
from synapse import log
from synapse_installer.deploy import addDeviceConfig
from synapse_installer.util import (
    NOT_IN_SYNAPSE_PROJECT_ERR,
    SYNAPSE_PROJECT_FILE,
    getDistRequirements,
    getUserRequirements,
)

from .command_executor import CommandExecutor, LocalCommandExecutor, SSHCommandExecutor

PackageManager = str
CheckInstalledCmd = str
InstallCmd = str


# ============================================================
# System utilities
# ============================================================


def setupSudoers(
    executor: CommandExecutor, hostname: str, username: str, password: str
) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        fprint(f"[red]Invalid username `{username}`; refusing to edit sudoers.[/red]")
        return False

    sudoers_line = f"{username} ALL=(ALL) NOPASSWD:ALL"
    sudoers_file = f"/etc/sudoers.d/{username}-nopasswd"
    script = (
        f"printf '%s\\n' {shlex.quote(sudoers_line)} > {shlex.quote(sudoers_file)} "
        f"&& chmod 440 {shlex.quote(sudoers_file)}"
    )
    cmd = f"sudo -S -p '' bash -c {shlex.quote(script)}"

    _, stderr, exitCode = executor.execCommand(cmd, stdinData=f"{password}\n")
    if exitCode != 0:
        fprint(f"[red]Failed to setup sudoers on {hostname}:\n{stderr}[/red]")
        return False

    fprint(f"[green]Passwordless sudo added for {hostname}[/green]")
    return True


def installSystemPackage(
    executor: CommandExecutor, package: str, useSudo: bool = True
) -> None:
    sudo = "sudo " if useSudo else ""

    managers: List[Tuple[PackageManager, CheckInstalledCmd, InstallCmd]] = [
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
        _, _, exitCode = executor.execCommand(f"command -v {mgr} >/dev/null 2>&1")
        if exitCode == 0:
            _, _, installed = executor.execCommand(checkCmd)
            if installed == 0:
                return

            _, stderr, exitCode = executor.execCommand(installCmd)
            if exitCode != 0:
                raise RuntimeError(
                    f"Failed to install system package `{package}`:\n{stderr}"
                )
            return

    raise RuntimeError("No supported package manager found")


# ============================================================
# Python + venv handling
# ============================================================


def ensurePythonInRange(
    executor: CommandExecutor,
    min_ver=(3, 11),
    max_ver=(3, 14),
) -> str:
    for minor in range(max_ver[1], min_ver[1] - 1, -1):
        py = f"python3.{minor}"
        _, _, exitCode = executor.execCommand(f"{py} --version")
        if exitCode == 0:
            return py

    fprint("[yellow]No compatible Python found, building from source...[/yellow]")

    build_minor = max(min_ver[1], 12)
    py_version = f"3.{build_minor}.2"

    deps = [
        "build-essential",
        "libssl-dev",
        "zlib1g-dev",
        "libncurses5-dev",
        "libncursesw5-dev",
        "libreadline-dev",
        "libsqlite3-dev",
        "libgdbm-dev",
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

    cmds = [
        "cd /tmp",
        f"wget -O Python-{py_version}.tgz https://www.python.org/ftp/python/{py_version}/Python-{py_version}.tgz",
        f"tar xvf Python-{py_version}.tgz",
        f"cd Python-{py_version}",
        "./configure --enable-optimizations",
        "make -j$(nproc)",
        "sudo make altinstall",
    ]

    _, stderr, exitCode = executor.execCommand(" && ".join(cmds))
    if exitCode != 0:
        raise RuntimeError(f"Failed to install Python {py_version}:\n{stderr}")

    return f"python3.{build_minor}"


def ensureVenv(
    executor: CommandExecutor,
    python_cmd: str,
    venv_path: str = ".venv",
) -> str:
    venv_python = f"{venv_path}/bin/pip"

    _, _, exitCode = executor.execCommand(f"[ -x {venv_python} ]")
    if exitCode == 0:
        return venv_python

    fprint(f"[yellow]Creating venv at {venv_path}[/yellow]")
    _, stderr, exitCode = executor.execCommand(f"{python_cmd} -m venv {venv_path}")
    if exitCode != 0:
        raise RuntimeError(f"Failed to create venv:\n{stderr}")

    executor.execCommand(f"{venv_python} install --upgrade pip setuptools wheel")
    return venv_python


# ============================================================
# Pip install
# ============================================================


def installPipRequirements(
    executor: CommandExecutor,
    requirements: List[str],
    python_cmd: str,
    wplibYear: Optional[str] = None,
) -> None:
    stdout, _, _ = executor.execCommand(f"{python_cmd}  freeze")
    installed = {
        name.lower(): ver
        for name, ver in (
            line.split("==", 1) for line in stdout.splitlines() if "==" in line
        )
    }

    failures: List[str] = []

    for i, req in enumerate(requirements, 1):
        pkg, _, ver = req.partition("==")
        pkg_l = pkg.lower()

        if pkg_l in installed and (not ver or installed[pkg_l] == ver):
            fprint(f"[green][OK][/green] {pkg} [{i}/{len(requirements)}]")
            continue

        cmd = f"{python_cmd} install {req}"
        if wplibYear:
            cmd += (
                " --extra-index-url="
                f"https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-{wplibYear}/simple/"
            )
        cmd += " --upgrade-strategy only-if-needed"

        _, stderr, exitCode = executor.execCommand(cmd)
        if exitCode != 0:
            failures.append(f"{pkg}: {stderr.strip()}")
            fprint(f"[red]Install failed for {pkg}:\n{stderr}[/red]")

    if failures:
        raise RuntimeError(
            "Some Python requirements could not be installed:\n" + "\n".join(failures)
        )


# ============================================================
# Sync logic
# ============================================================


def syncRequirements(
    executor: CommandExecutor,
    hostname: str,
    username: str,
    password: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> bool:
    try:
        _, _, canSudo = executor.execCommand("sudo -n true")
        if canSudo != 0 and not setupSudoers(executor, hostname, username, password):
            return False

        for pkg in ("libopencv-dev", "unzip", "isc-dhcp-client"):
            installSystemPackage(executor, pkg)

        system_python = ensurePythonInRange(executor)
        venv_python = ensureVenv(executor, system_python)

        requirements = [r for r in requirements if "extra" not in r]
        installPipRequirements(executor, requirements, venv_python, wplibYear)

        fprint(f"[green]Sync completed on {hostname}[/green]")
        return True
    except Exception as e:
        fprint(f"[red]{e}\n{traceback.format_exc()}[/red]")
        return False
    finally:
        executor.close()


# ============================================================
# CLI entrypoints
# ============================================================


def sync(argv: Optional[List[str]] = None) -> int:
    cwd = Path.cwd()
    if not (cwd / SYNAPSE_PROJECT_FILE).exists():
        fprint(log.MarkupColors.fail(NOT_IN_SYNAPSE_PROJECT_ERR))
        return 1

    with open(cwd / SYNAPSE_PROJECT_FILE, "r") as f:
        data = yaml.full_load(f) or {}

    if not isinstance(data, dict):
        fprint(log.MarkupColors.fail("The project config must be a YAML mapping."))
        return 1

    deploys = data.get("deploy") or {}
    if not isinstance(deploys, dict) or not deploys:
        addDeviceConfig(cwd / SYNAPSE_PROJECT_FILE)
        with open(cwd / SYNAPSE_PROJECT_FILE, "r") as f:
            data = yaml.full_load(f) or {}
        deploys = data.get("deploy") or {}

    if not isinstance(deploys, dict) or not deploys:
        fprint(log.MarkupColors.fail("No devices are configured. Run `device add`."))
        return 1

    requested = [arg for arg in (argv or []) if not arg.startswith("-")]
    targets = requested or list(deploys)

    missing = [host for host in targets if host not in deploys]
    for host in missing:
        fprint(log.MarkupColors.fail(f"No device named `{host}` found"))
    if missing:
        return 1

    any_failure = False

    for host in targets:
        dev = deploys[host]
        try:
            fprint(f"Syncing {host}@{dev['ip']}")
            reqs = list(getDistRequirements())
            reqs.extend(getUserRequirements(cwd / "pyproject.toml"))

            executor = SSHCommandExecutor(
                hostname=dev["ip"],
                username=dev["hostname"],
                password=dev["password"],
            )

            if not syncRequirements(
                executor,
                host,
                dev["hostname"],
                dev["password"],
                reqs,
                synapseVersion.WPILIB_YEAR,
            ):
                any_failure = True
        except Exception as e:
            fprint(log.MarkupColors.fail(f"Failed to sync {host}: {e}"))
            any_failure = True

    return 1 if any_failure else 0


def syncLocal(requirements: List[str], wplibYear: Optional[str] = None) -> None:
    executor = LocalCommandExecutor()
    python_cmd = sys.executable
    installPipRequirements(executor, requirements, python_cmd, wplibYear)


def syncRemote(
    hostname: str,
    ip: str,
    password: str,
    requirements: List[str],
    wplibYear: Optional[str] = None,
) -> None:
    fprint(f"Connecting to {hostname}@{ip}")
    executor = SSHCommandExecutor(ip, "root", password)
    syncRequirements(executor, hostname, hostname, password, requirements, wplibYear)
