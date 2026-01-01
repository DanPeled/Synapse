# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import ipaddress
from dataclasses import dataclass
from functools import cache
from importlib.metadata import distribution
from pathlib import Path
from typing import Final, List

import toml

SYNAPSE_PROJECT_FILE: Final[str] = ".synapseproject"
NOT_IN_SYNAPSE_PROJECT_ERR: Final[str] = (
    f"No {SYNAPSE_PROJECT_FILE} file found, are you sure you're inside of a Synapse project?"
)


@dataclass()
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


@cache
def getDistRequirements() -> List[str]:
    dist = distribution("synapsefrc")
    requirements = dist.requires or []
    return requirements


def getUserRequirements(pyprojectPath: Path) -> List[str]:
    if pyprojectPath.exists():
        data = toml.load(pyprojectPath)
        requires = data.get("tool", {}).get("synapse", {}).get("requires", [])
        return requires
    return []


def getWPILibVersion() -> str:
    import synapse.__version__

    return synapse.__version__.WPILIB_VERSION


@cache
def getWPILibYear() -> str:
    version = getWPILibVersion()
    splitVersion = version.split(".")
    assert len(splitVersion) > 0, f"Invalid WPILib version {version}"
    return splitVersion[0]
