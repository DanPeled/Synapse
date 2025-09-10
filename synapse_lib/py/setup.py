# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Final

from setuptools import find_packages, setup

SOURCE_DIR: Final[str] = "src"

setup(
    name="synapsefrclib",
    version="2025.0.0a2",
    packages=find_packages(where=SOURCE_DIR),
    package_dir={"": SOURCE_DIR},
    python_requires=">=3.9, <3.12",
    install_requires=["typing", "pyntcore"],
    extras_require={"dev": []},
    include_package_data=True,
)
