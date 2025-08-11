# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import pathlib as pthl
import sys
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
from .setup_service import (SERVICE_NAME, isServiceSetup, restartService,
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
                f"Device with nickname `{deviceNickname} already exists! Please provide another one`"
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
        yaml.dump(
            baseFile,
            f,
        )


def _connectAndDeploy(
    hostname: str, ip: str, password: str, zip_paths: List[pthl.Path]
):
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

        with SCPClient(transport) as scp:
            for zip_path in zip_paths:
                remote_zip = f"/tmp/{zip_path.name}"
                print(f"Uploading {zip_path.name} to {remote_zip}")
                scp.put(str(zip_path), remote_zip)
                unzip_cmd = f"mkdir -p ~/Synapse && unzip -o {remote_zip} -d ~/Synapse"
                stdin, stdout, stderr = client.exec_command(unzip_cmd)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    print(f"Unzipped {zip_path.name} on {hostname}")
                else:
                    print(f"Error unzipping {zip_path.name}:\n{stderr.read().decode()}")
                    break
            else:
                if not isServiceSetup(client, SERVICE_NAME):
                    setupServiceOnConnectedClient(
                        client,
                        hostname,
                    )
                restartService(client, SERVICE_NAME)

        client.close()
        print(f"Deployment completed on {hostname}")

    except Exception as error:
        errString = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(f"Deployment to {hostname}@{ip} failed: {errString}")


def deploy(path: pthl.Path, cwd: pthl.Path, argv: Optional[List[str]]):
    data = {}
    with open(path, "r") as f:
        data: dict = yaml.full_load(f)

    if "deploy" not in data:
        addDeviceConfig(path)
        with open(path, "r") as f:
            data: dict = yaml.full_load(f) or {"deploy": {}}

    if argv is None:
        argv = sys.argv

    argc = len(argv)
    if argc < 2:
        ...  # Throw error

    for i in range(1, argc):
        currHostname = argv[i]
        if currHostname in data["deploy"]:
            data = data["deploy"][currHostname]
            project_zip = cwd / BUILD_DIR / "project.zip"
            package_zip = cwd / BUILD_DIR / "synapse.zip"
            _connectAndDeploy(
                data["hostname"],
                data["ip"],
                data["password"],
                [project_zip, package_zip],
            )
        else:
            fprint(
                MarkupColors.fail(
                    f"Device with hostname `{currHostname}` does not exist"
                )
            )


def loadDeviceData(deployConfigPath: pthl.Path):
    addDeviceConfig(deployConfigPath)


def setupAndRunDeploy(argv: Optional[List[str]] = None):
    cwd: pthl.Path = pthl.Path(os.getcwd())

    assert (cwd / SYNAPSE_PROJECT_FILE).exists(), NOT_IN_SYNAPSE_PROJECT_ERR

    def fileShouldDeploy(f: pthl.Path):
        return (
            str(f).endswith(".py")
            or f.is_relative_to(cwd / "deploy")
            or f.is_relative_to(cwd / "config")
        )

    deployConfigPath = cwd / SYNAPSE_PROJECT_FILE
    loadDeviceData(deployConfigPath)

    createPackageZIP(cwd / BUILD_DIR)
    createDirectoryZIP(
        pthl.Path(os.getcwd()),
        cwd / BUILD_DIR / "project.zip",
        fileShouldDeploy,
    )

    deploy(deployConfigPath, cwd, argv)
