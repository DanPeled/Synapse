from setuptools import find_packages, setup

setup(
    name="synapse",
    version="0.0.1",
    author="Ionic Bond #9738",
    description="",
    packages=find_packages(),
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
    ],
    python_requires=">=3.8",
)
