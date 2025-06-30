from setuptools import find_packages, setup

WPILIB_VERSION = "2025.2.1.1"


def wpilibDep(name: str) -> str:
    return f"{name}=={WPILIB_VERSION}"


def synapseNetDep(name: str) -> str:
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
        "PyYAML",
        "opencv_python",
        "opencv_contrib_python",
        "pathspec",
        "paramiko",
        "scp>=0.15.0",
        "numpy==1.23.3",
        "build",
        "psutil",
        synapseNetDep("protobuf"),
        synapseNetDep("betterproto==2.0.0b7"),
        synapseNetDep("websockets"),
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
        ]
    },
    include_package_data=True,
)
