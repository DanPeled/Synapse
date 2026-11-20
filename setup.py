# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import find_packages, setup

version_vars = {}
with open("versions.properties", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, separator, value = line.partition("=")
        if separator:
            version_vars[key.strip()] = value.strip()

SYNAPSE_VERSION = version_vars["synapsePythonVersion"]
WPILIB_VERSION = version_vars["wpilibPythonVersion"]


modules = {
    "synapse_net": "synapse_net/src",
    "synapse_installer": "synapse_installer/src",
    "synapse_sim": "synapse_sim/src",
    "synapse": "synapse_core/src",
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
    description="Dynamic vision processing system for FRC coprocessors",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=allModules,
    package_dir=moduleDirs,
    python_requires=">=3.11, <=3.14",
    install_requires=[
        "rich",
        "numpy==1.26.4",
        "msgpack",
        wpilibDep("robotpy_wpimath"),
        wpilibDep("robotpy_apriltag"),
        wpilibDep("robotpy_cscore"),
        wpilibDep("robotpy_wpiutil"),
        wpilibDep("wpilib"),
        wpilibDep("pyntcore"),
        visionProcessingDep("opencv_python==4.8.0.74"),
        visionProcessingDep("opencv_contrib_python==4.8.0.74"),
        visionProcessingDep("napa-vision==0.5.1"),
        deviceAccessDep("PyYAML"),
        deviceAccessDep("pathspec"),
        synapseInstallerDep("paramiko"),
        synapseInstallerDep("scp>=0.15.0"),
        synapseInstallerDep("questionary"),
        synapseInstallerDep("tqdm"),
        synapseInstallerDep("toml"),
        hardwareManagementDep("psutil"),
        synapseNetDep("protobuf"),
        synapseNetDep("betterproto[compiler]==2.0.0b7"),
        synapseNetDep("websockets"),
    ],
    extras_require={
        "yolo": [
            "torch>=2.1",
            "ultralytics>=8.0.200",
        ],
        "dev": [
            "wheel",
            "setuptools",
            "pytest",
            "pytest-asyncio",
            "pytest-mock",
            "ruff==0.15.20",
            "isort",
            "pyright",
            "build",
            "reuse",
            "requests",
        ],
    },
    include_package_data=True,
    package_data={
        "synapse_sim": [
            "assets/*.glb",
            "assets/*.json",
            "assets/*.js",
            "assets/*.html",
            "assets/apriltags/*.png",
        ],
    },
    entry_points={
        "console_scripts": [
            "synapse_installer=synapse_installer.__main__:main",
        ],
    },
)
