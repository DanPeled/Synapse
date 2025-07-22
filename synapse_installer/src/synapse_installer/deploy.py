import ipaddress
import os
import pathlib as pthl
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .lockfile import createSynapseZIP
import questionary
import yaml
from rich import print as fprint
from synapse.bcolors import MarkupColors


class SetupOptions(Enum):
    kManual = "Manual (Provide hostname & password)"
    kAutomatic = "Automatic (Find available devices)"


@dataclass
class DeployDeviceConfig:
    hostname: str
    ip: str
    password: str


def IsValidIP(ip_str):
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def setupConfigFile(path: pthl.Path):
    print("Deploy config doesn't exist, creating...")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    baseFile = {}
    if path.exists():
        with open(path, "r") as f:
            baseFile = yaml.full_load(f) or {}
    with open(path, "w") as f:
        answer = questionary.select(
            "Choose setup mode:",
            choices=[
                SetupOptions.kManual.value,
                SetupOptions.kAutomatic.value,
            ],
        ).ask()

        if answer == SetupOptions.kManual.value:
            hostname = questionary.text("What's your device's hostname?").ask()
            deviceNickname = (
                questionary.text(f"Device Nickname (Leave blank for `{hostname}`").ask()
                or hostname
            )

            ip: Optional[str] = None
            while True:
                ip = questionary.text("What's your device's IP address?").ask()
                if ip is None:
                    return
                if IsValidIP(ip):
                    break
                else:
                    print(
                        "Invalid IP address. Please enter a valid IPv4 or IPv6 address."
                    )
            password = questionary.password("What's the password to your device?").ask()

            baseFile["deploy"] = {
                deviceNickname: DeployDeviceConfig(
                    hostname=hostname, ip=ip, password=password
                ).__dict__
            }

            yaml.dump(
                baseFile,
                f,
            )


def deploy(path: pthl.Path):
    data = {}
    with open(path, "r") as f:
        data: dict = yaml.full_load(f)

    if "deploy" not in data:
        setupConfigFile(path)
        with open(path, "r") as f:
            data: dict = yaml.full_load(f) or {"deploy": {}}

    argc = len(sys.argv)
    if argc < 2:
        ...  # Throw error
    argv = sys.argv
    for i in range(1, argc):
        currHostname = argv[i]
        if currHostname in data["deploy"]:
            print(f"Attempting deploy to `{currHostname}`...")
            ...  # Deploy to device
        else:
            fprint(
                MarkupColors.fail(
                    f"Device with hostname `{currHostname}` does not exist"
                )
            )


def loadDeviceData(deployConfigPath: pthl.Path):
    if not deployConfigPath.exists():
        setupConfigFile(deployConfigPath)
    elif os.path.getsize(deployConfigPath) == 0:
        setupConfigFile(deployConfigPath)


def setupAndRunDeploy():
    cwd: pthl.Path = pthl.Path(os.getcwd())
    assert (cwd / ".synapseproject").exists(), (
        "No .synpaseproject file found, are you sure you're inside of a Synapse project?"
    )

    deployConfigPath = cwd / ".synapseproject"
    loadDeviceData(deployConfigPath)
    createSynapseZIP(cwd / "build")
    deploy(deployConfigPath)
