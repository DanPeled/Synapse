# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import find_packages, setup

version_vars = {}
with open("synapse_core/src/synapse/__version__.py") as f:
    exec(f.read(), version_vars)

SYNAPSE_VERSION = version_vars["SYNAPSE_VERSION"]
WPILIB_VERSION = version_vars["WPILIB_VERSION"]


modules = {
    "synapse_net": "synapse_net/src",
    "synapse_installer": "synapse_installer/src",
    "": "synapse_core/src",
    "synapse_ui": "synapse_ui/out",
}


def wpilibDep(name: str, version: str = WPILIB_VERSION) -> str:
    return f"{name}=={version}"


def synapseInstallerDep(name: str) -> str:
    return name


def synapseNetDep(name: str) -> str:
    return name


def hardwareManagementDep(name: str) -> str:
    return name


def deviceAccessDep(name: str) -> str:
    return name


def visionProcessingDep(name: str) -> str:
    return name


allModules = []
moduleDirs = {}

for name, path in modules.items():
    allModules += find_packages(where=path)
    if name:  # not root
        moduleDirs[name] = f"{path}/{name}"
    else:
        moduleDirs[""] = path

setup(
    name="synapsefrc",
    version=SYNAPSE_VERSION,
    packages=allModules,
    package_dir=moduleDirs,
    python_requires=">=3.9, <3.12",
    install_requires=[
        "rich",
        "numpy==1.23.3",
        wpilibDep("robotpy_wpimath"),
        wpilibDep("robotpy_apriltag"),
        wpilibDep("robotpy_cscore"),
        wpilibDep("robotpy_wpiutil"),
        wpilibDep("wpilib"),
        wpilibDep("pyntcore"),
        visionProcessingDep("opencv_python"),
        visionProcessingDep("opencv_contrib_python"),
        deviceAccessDep("PyYAML"),
        deviceAccessDep("pathspec"),
        synapseInstallerDep("paramiko"),
        synapseInstallerDep("scp>=0.15.0"),
        synapseInstallerDep("questionary"),
        synapseInstallerDep("tqdm"),
        synapseInstallerDep("toml"),
        hardwareManagementDep("psutil"),
        synapseNetDep("protobuf"),
        synapseNetDep("betterproto==2.0.0b7"),
        synapseNetDep("websockets"),
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "ruff",
            "isort",
            "pyright",
            "build",
            "reuse",
        ]
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "synapse_installer=synapse_installer.__main__:main",
        ],
    },
)
