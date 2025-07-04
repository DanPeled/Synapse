from setuptools import find_packages, setup

WPILIB_VERSION = "2025.2.1.1"


def wpilibDep(name: str, version: str = WPILIB_VERSION) -> str:
    return f"{name}=={version}"


def deployProcessDep(name: str) -> str:
    return name


def synapseNetDep(name: str) -> str:
    return name


def hardwareManagementDep(name: str) -> str:
    return name


def deviceAccessDep(name: str) -> str:
    return name


setup(
    name="Synapse",
    version="0.1.0",
    packages=find_packages(where="synapse_net/src/")
    + find_packages(where="synapse_core/src"),
    package_dir={
        "synapse_net": "synapse_net/src/synapse_net",
        "": "synapse_core/src/",
    },
    install_requires=[
        wpilibDep("robotpy_wpimath"),
        wpilibDep("robotpy_apriltag"),
        wpilibDep("robotpy_cscore"),
        wpilibDep("wpilib"),
        wpilibDep("pyntcore"),
        "rich",
        "numpy==1.23.3",
        "opencv_python",
        "opencv_contrib_python",
        deviceAccessDep("PyYAML"),
        deviceAccessDep("pathspec"),
        deployProcessDep("paramiko"),
        deployProcessDep("scp>=0.15.0"),
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
        ]
    },
    include_package_data=True,
)
