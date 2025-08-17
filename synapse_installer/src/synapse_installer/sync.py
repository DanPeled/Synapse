# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

import paramiko
import synapse.log as log
import yaml
from rich import print as fprint

from .deploy import addDeviceConfig
from .util import (NOT_IN_SYNAPSE_PROJECT_ERR, SYNAPSE_PROJECT_FILE,
                   getDistRequirements, getWPILibYear)

PackageManager = str
CheckInstalledCmd = str
InstallCmd = str


def syncRequirements(hostname: str, password: str, ip: str) -> None:
    try:
        print(f"Connecting to {hostname}@{ip}...")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ip,
            username="root",
            password=password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=5,
        )
        transport = client.get_transport()
        assert transport is not None

        setupSudoers(client, hostname)
        installSystemPackage(client, "libopencv-dev")
        installSystemPackage(client, "npm")
        installNpmPackage(client, "serve", True)
        installPipRequirements(client)

        client.close()
        print(f"Sync completed on {hostname}")
    except Exception as e:
        fprint(log.MarkupColors.fail(f"{e}\n{traceback.format_exc()}"))


def sync(argv: Optional[List[str]]) -> None:
    cwd: Path = Path(os.getcwd())

    assert (cwd / SYNAPSE_PROJECT_FILE).exists(), NOT_IN_SYNAPSE_PROJECT_ERR

    data = {}
    deployConfigPath = cwd / SYNAPSE_PROJECT_FILE
    with open(deployConfigPath, "r") as f:
        data: dict = yaml.full_load(f)

    if data is None:
        data = {}

    if "deploy" not in data:
        addDeviceConfig(deployConfigPath)
        with open(deployConfigPath, "r") as f:
            data: dict = yaml.full_load(f) or {"deploy": {}}

    if argv is None:
        argv = sys.argv

    argc = len(argv)
    if argc < 2:
        fprint(log.MarkupColors.fail("No hostname to deploy to specified!"))
        return

    for i in range(1, argc):
        currHostname = argv[i]
        if currHostname in data["deploy"]:
            deviceData = data["deploy"][currHostname]
            syncRequirements(
                deviceData["hostname"],
                deviceData["password"],
                deviceData["ip"],
            )
        else:
            fprint(
                log.MarkupColors.fail(
                    f"No device named: `{currHostname}` found! skipping..."
                )
            )


def setupSudoers(client: paramiko.SSHClient, hostname: str) -> None:
    # Add sudoers entry before doing anything else
    sudoers_line = (
        "root ALL=(ALL) NOPASSWD: "
        "/bin/hostname, /usr/bin/hostnamectl, /sbin/ip, "
        "/usr/bin/tee, /bin/cat, /bin/sh"
    )
    sudoers_file = "/etc/sudoers.d/root-custom-host-config"

    setup_sudoers_cmd = (
        f"echo '{sudoers_line}' | tee {sudoers_file} > /dev/null && "
        f"chmod 440 {sudoers_file}"
    )

    stdin, stdout, stderr = client.exec_command(setup_sudoers_cmd)
    err_out = stderr.read().decode()
    if err_out.strip():
        fprint(
            log.MarkupColors.fail(f"Failed to setup sudoers on {hostname}:\n{err_out}")
        )
    else:
        fprint(log.MarkupColors.okgreen(f"Sudoers rule added on {hostname}"))


def installSystemPackage(client, package: str, use_sudo: bool = True) -> None:
    sudo = "sudo " if use_sudo else ""

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

    for mgr, check_cmd, install_cmd in managers:
        stdin, stdout, stderr = client.exec_command(f"command -v {mgr} >/dev/null 2>&1")
        if stdout.channel.recv_exit_status() == 0:
            stdin, stdout, stderr = client.exec_command(check_cmd)
            if stdout.channel.recv_exit_status() == 0:
                print(f"{package} is already installed.")
                return
            print(f"Installing {package} with {mgr}...")
            client.exec_command(install_cmd)
            return

    raise RuntimeError("No supported package manager found")


def installNpmPackage(
    client: paramiko.SSHClient, package: str, global_install: bool = True
) -> None:
    """Install an npm package globally on the remote device if not already installed."""
    check_cmd = f"npm list -g {package} >/dev/null 2>&1"
    install_cmd = f"npm install {'-g ' if global_install else ''}{package}"

    stdin, stdout, stderr = client.exec_command(check_cmd)
    if stdout.channel.recv_exit_status() == 0:
        print(f"npm package '{package}' is already installed.")
        return

    print(f"Installing npm package '{package}'...")
    stdin, stdout, stderr = client.exec_command(install_cmd)
    err = stderr.read().decode()
    if err.strip():
        fprint(log.MarkupColors.fail(f"npm install failed for {package}:\n{err}"))
    else:
        fprint(
            log.MarkupColors.okgreen(f"npm package '{package}' installed successfully.")
        )


def installPipRequirements(client: paramiko.SSHClient) -> None:
    requirements = getDistRequirements()
    # Get installed packages on remote device
    stdin, stdout, stderr = client.exec_command("python3 -m pip freeze")
    installed_packages = {}
    for line in stdout.read().decode().splitlines():
        if "==" in line:
            name, ver = line.strip().split("==", 1)
            installed_packages[name.lower()] = ver

    for i, requirement in enumerate(requirements, start=1):
        if "==" in requirement:
            pkg_name, req_ver = requirement.split("==", 1)
        else:
            pkg_name, req_ver = requirement, None

        pkg_name = pkg_name.lower()
        installed_ver = installed_packages.get(pkg_name)

        if installed_ver is not None and (req_ver is None or installed_ver == req_ver):
            fprint(
                f"[OK] {pkg_name} already installed "
                f"{log.MarkupColors.okgreen(f'[{i}/{len(requirements)}]')}"
            )
            continue

        fprint(
            f"Installing {pkg_name}... "
            f"{log.MarkupColors.okgreen(f'[{i}/{len(requirements)}]')}"
        )

        cmd = f"python3 -m pip install {requirement} "
        if getWPILibYear():
            cmd += (
                f"--extra-index-url=https://wpilib.jfrog.io/artifactory/api/pypi/"
                f"wpilib-python-release-{getWPILibYear()}/simple/ "
            )
        cmd += "--break-system-packages --upgrade-strategy only-if-needed"

        stdin, stdout, stderr = client.exec_command(cmd)
        err = stderr.read().decode()
        if err.strip():
            fprint(log.MarkupColors.fail(f"Install for {pkg_name} failed!\n{err}"))
