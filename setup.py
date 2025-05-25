from setuptools import find_packages, setup

setup(
    name="Synapse",
    version="0.1.0",
    packages=[
        *find_packages(where="synapse_core/src"),
        *find_packages(where="synapse_net/src"),
    ],
    package_dir={
        "": "synapse_core/src/",
        "synapse_net": "synapse_net/src/",
    },
    install_requires=[
        "robotpy_wpimath",
        "robotpy_apriltag",
        "robotpy_cscore",
        "wpilib",
        "pyntcore",
        "PyYAML",
        "opencv_python",
        "opencv_contrib_python",
        "typing_extensions",
        "pathspec",
        "paramiko",
        "scp>=0.15.0",
        "numpy==1.23.3",
        "pytest",
        "build",
    ],
)
