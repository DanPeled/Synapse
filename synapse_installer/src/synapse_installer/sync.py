# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import traceback
from importlib.metadata import distribution
from pathlib import Path
from typing import List, Optional

import paramiko
import synapse.log as log
import yaml

from .deploy import addDeviceConfig, fprint


def syncRequirements(
    hostname: str, password: str, ip: str, requirements: List[str]
) -> None:
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

        # Get installed packages on remote device
        stdin, stdout, stderr = client.exec_command("python3 -m pip freeze")
        installed_packages = {
            line.strip().split("==")[0].lower()
            for line in stdout.read().decode().splitlines()
            if "==" in line
        }

        for i, requirement in enumerate(requirements, start=1):
            pkg_name = str(requirement).split()[0].lower()
            if pkg_name in installed_packages:
                fprint(
                    f"✓ {pkg_name} already installed "
                    f"{log.MarkupColors.okgreen(f'[{i}/{len(requirements)}]')}"
                )
                continue

            fprint(
                f"Installing {pkg_name}... "
                f"{log.MarkupColors.okgreen(f'[{i}/{len(requirements)}]')}"
            )

            stdin, stdout, stderr = client.exec_command(
                f"python3 -m pip install {str(requirement)} "
                f"--extra-index-url=https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-2025/simple/ "
                f"--break-system-packages --upgrade-strategy only-if-needed"
            )

            err = stderr.read().decode()
            if err.strip():
                fprint(log.MarkupColors.fail(f"Install for {pkg_name} failed!\n{err}"))

        client.close()
        print(f"Sync completed on {hostname}")
    except Exception as e:
        log.err(f"{e}\n{traceback.format_exc()}")


def sync(argv: Optional[List[str]]) -> None:
    cwd: Path = Path(os.getcwd())

    assert (cwd / ".synapseproject").exists(), (
        "No .synpaseproject file found, are you sure you're inside of a Synapse project?"
    )

    data = {}
    deployConfigPath = cwd / ".synapseproject"
    with open(deployConfigPath, "r") as f:
        data: dict = yaml.full_load(f)

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
            dist = distribution("synapsefrc")
            requirements = dist.requires or []
            deviceData = data["deploy"][currHostname]
            syncRequirements(
                deviceData["hostname"],
                deviceData["password"],
                deviceData["ip"],
                requirements,
            )
        else:
            fprint(
                log.MarkupColors.fail(
                    f"No device named: `{currHostname}` found! skipping..."
                )
            )
