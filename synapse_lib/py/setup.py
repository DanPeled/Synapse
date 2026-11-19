# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Final

from setuptools import find_packages, setup

SOURCE_DIR: Final[str] = "src"

versions = {}
for line in (Path(__file__).resolve().parents[2] / "versions.properties").read_text(
    encoding="utf-8"
).splitlines():
    line = line.strip()
    if not line or line.startswith(("#", "!")):
        continue
    key, separator, value = line.partition("=")
    if separator:
        versions[key.strip()] = value.strip()

WPILIB_VERSION: Final[str] = versions["wpilibPythonVersion"]

setup(
    name="synapsefrclib",
    version=versions["synapsePythonVersion"],
    packages=find_packages(where=SOURCE_DIR),
    package_dir={"": SOURCE_DIR},
    python_requires=">=3.11, <=3.14",
    install_requires=[
        f"pyntcore=={WPILIB_VERSION}",
        "msgpack",
        f"robotpy_wpimath=={WPILIB_VERSION}",
    ],
    extras_require={"dev": []},
    include_package_data=True,
)
