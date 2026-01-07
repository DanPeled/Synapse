# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import pathlib as pthl
import traceback
from enum import Enum
from typing import List, Optional

import paramiko
import questionary
import yaml
from rich import print as fprint
from scp import SCPClient
from synapse.bcolors import MarkupColors

from .lockfile import createDirectoryZIP, createPackageZIP
from .setup_service import (SERVICE_NAME, restartService,
                            setupServiceOnConnectedClient)
from .util import (NOT_IN_SYNAPSE_PROJECT_ERR, SYNAPSE_PROJECT_FILE,
                   DeployDeviceConfig, IsValidIP)

BUILD_DIR = "build"


class SetupOptions(Enum):
    kManual = "Manual (Provide hostname & password)"
    kAutomatic = "Automatic (Find available devices)"


def addDeviceConfig(path: pthl.Path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    baseFile = {}
    if path.exists():
        with open(path, "r") as f:
            baseFile = yaml.full_load(f) or {}
    answer = questionary.select(
        "Choose setup mode:",
        choices=[
            SetupOptions.kManual.value,
            SetupOptions.kAutomatic.value,
        ],
    ).ask()

    if answer == SetupOptions.kManual.value:
        hostname = questionary.text("What's your device's hostname?").ask()
        if hostname is None:
            return

        deviceNickname = questionary.text(
            f"Device Nickname (Leave blank for `{hostname}`)", default=hostname
        ).ask()

        while deviceNickname in baseFile.get("deploy", {}):
            print(
                f"Device with nickname `{deviceNickname}` already exists! Please provide another one"
            )
            deviceNickname = questionary.text(
                f"Device Nickname (Leave blank for `{hostname}`)", default=hostname
            ).ask()

        ip: Optional[str] = None
        while True:
            ip = questionary.text("What's your device's IP address?").ask()
            if ip is None:
                return
            if IsValidIP(ip):
                break
            else:
                print("Invalid IP address. Please enter a valid IPv4 or IPv6 address.")

        password = questionary.password("What's the password to your device?").ask()

        if "deploy" not in baseFile:
            baseFile["deploy"] = {}

        baseFile["deploy"][deviceNickname] = DeployDeviceConfig(
            hostname=hostname, ip=ip, password=password
        ).__dict__

    with open(path, "w") as f:
        yaml.dump(baseFile, f)


def _connectAndDeploy(
    hostname: str, ip: str, password: str, zip_paths: List[pthl.Path]
):
    try:
        print(f"Connecting to {hostname}@{ip}...")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ip,
            username=hostname,
            password=password,
            look_for_keys=False,
            allow_agent=False,
        )
        transport = client.get_transport()

        assert transport is not None

        with SCPClient(transport) as scp:
            for zip_path in zip_paths:
                remote_zip = f"/tmp/{zip_path.name}"
                print(f"Uploading {zip_path.name} to {remote_zip}")
                scp.put(str(zip_path), remote_zip)

                # Unzip while ignoring warnings about "../" paths
                unzip_cmd = f"mkdir -p ~/Synapse && unzip -o {remote_zip} -d ~/Synapse 2>/dev/null"
                stdin, stdout, stderr = client.exec_command(unzip_cmd)
                exit_status = stdout.channel.recv_exit_status()
                out = stdout.read().decode()
                err = stderr.read().decode()

                if exit_status == 0:
                    print(f"Unzipped {zip_path.name} on {hostname}")
                    if out.strip():  # Optional: print stdout messages if any
                        print(out.strip())
                else:
                    print(f"Error unzipping {zip_path.name} (exit {exit_status}):")
                    if out.strip():
                        print("STDOUT:", out.strip())
                    if err.strip():
                        print("STDERR:", err.strip())
                    break
            # Only run if all zip files were successfully unzipped
            setupServiceOnConnectedClient(client, hostname)
            restartService(client, SERVICE_NAME)

        client.close()
        print(f"Deployment completed on {hostname}")

    except Exception as error:
        errString = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(f"Deployment to {hostname}@{ip} failed: {errString}")


def deploy(path: pthl.Path, cwd: pthl.Path, argv: Optional[List[str]]):
    deploys = loadDeviceData(path, argv)

    project_zip = cwd / BUILD_DIR / "project.zip"
    package_zip = cwd / BUILD_DIR / "synapse.zip"

    for deviceNickname, deviceData in deploys.items():
        _connectAndDeploy(
            deviceData["hostname"],
            deviceData["ip"],
            deviceData["password"],
            [project_zip, package_zip],
        )


def loadDeviceData(
    deployConfigPath: pthl.Path, argv: Optional[List[str]] = None
) -> dict:
    """
    Load device deploy data from the YAML config.
    If devices are missing, prompts to add them.

    Args:
        deployConfigPath: Path to the YAML deploy config file.
        argv: Optional list of hostnames to filter deploys.

    Returns:
        Dictionary of deploy device configs, filtered if argv is provided.
    """
    if not deployConfigPath.exists():
        addDeviceConfig(deployConfigPath)

    with open(deployConfigPath, "r") as f:
        data: dict = yaml.full_load(f) or {}

    if "deploy" not in data or not data["deploy"]:
        addDeviceConfig(deployConfigPath)
        with open(deployConfigPath, "r") as f:
            data = yaml.full_load(f) or {}

    deploys = data.get("deploy", {})

    if argv:
        filtered = {name: cfg for name, cfg in deploys.items() if name in argv}
        missing = [name for name in argv if name not in deploys]
        for name in missing:
            fprint(MarkupColors.fail(f"Device `{name}` not found in config."))
        return filtered

    return deploys


def setupAndRunDeploy(argv: Optional[List[str]] = None):
    cwd: pthl.Path = pthl.Path(os.getcwd())

    assert (cwd / SYNAPSE_PROJECT_FILE).exists(), NOT_IN_SYNAPSE_PROJECT_ERR

    def fileShouldDeploy(f: pthl.Path):
        return str(f).endswith(".py") or f.is_relative_to(cwd / "deploy")

    deployConfigPath = cwd / SYNAPSE_PROJECT_FILE
    loadDeviceData(deployConfigPath, argv)

    createPackageZIP(cwd / BUILD_DIR)
    createDirectoryZIP(
        pthl.Path(os.getcwd()),
        cwd / BUILD_DIR / "project.zip",
        fileShouldDeploy,
    )

    deploy(deployConfigPath, cwd, argv)
