import os
import sys
import traceback
from pathlib import Path
from typing import List

import paramiko
import pkg_resources
import synapse.log as log
import yaml
from scp import Optional
from synapse_installer.deploy import fprint

from .deploy import setupConfigFile


def syncRequirements(hostname: str, password: str, ip: str, requirements) -> None:
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

        for requirement, i in enumerate(requirements):
            fprint(
                f"Installing {str(requirement)}... {log.MarkupColors.okgreen(f'[{i}/{len(requirements)}]')}"
            )
            *_, stderr = client.exec_command(
                f"python3 -m pip install {str(requirement)} --extra-index-url=https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-2025/simple/ --break-system-packages"
            )

            fprint(
                log.MarkupColors.fail(
                    f"Install for {str(requirement)} failed!\n{stderr.read().decode()}"
                )
            )

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
        setupConfigFile(deployConfigPath)
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
            dist = pkg_resources.get_distribution("synapsefrc")
            requirements = dist.requires()
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
