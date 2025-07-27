import argparse
import builtins
import runpy
import subprocess
import sys
import types
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Set

import toml
from rich import print as fprint

RequirementsSet = Set[str]


@dataclass
class DependecyInstallInfo:
    platform: Optional[str]
    pythonVersion: str
    implementation: str
    abi: str
    onlyBinary = ":all:"
    dest: Path
    extraIndexUrl: Optional[str]


class DependencyFiles(Enum):
    kSetupPy = "setup.py"
    kPyprojectToml = "pyproject.toml"


def extractInstallRequires(setup_path: Path) -> RequirementsSet:
    setup_args = {}

    # Create a fake setuptools module with a fake setup function
    fake_setuptools = types.ModuleType("setuptools")
    fake_setuptools.setup = lambda **kwargs: setup_args.update(kwargs)  # pyright: ignore
    fake_setuptools.find_packages = lambda *args, **_: []  # pyright: ignore

    # Inject into builtins so any import of setuptools/setup works
    old_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "setuptools":
            return fake_setuptools
        return old_import(name, *args, **kwargs)

    builtins.__import__ = fake_import

    try:
        runpy.run_path(str(setup_path.resolve()))
    finally:
        builtins.__import__ = old_import  # restore original import

    return set(setup_args.get("install_requires", []))


def getProjectDeps(cwd: Path) -> RequirementsSet:
    pyprojectFilePath = cwd / DependencyFiles.kPyprojectToml.value
    setupPyFilePath = cwd / DependencyFiles.kSetupPy.value
    requirements: RequirementsSet = set()

    if pyprojectFilePath.exists():
        data = toml.load(pyprojectFilePath)
        project = data.get("project", {})
        deps = project.get("dependencies", [])

        # Include optional dependencies
        optional = project.get("optional-dependencies", {})
        for extra_deps in optional.values():
            deps.extend(extra_deps)

        requirements = requirements.union(deps)

    if setupPyFilePath.exists():
        deps = extractInstallRequires(setupPyFilePath)
        requirements = requirements.union(deps)
    else:
        raise FileNotFoundError(
            "No pyproject.toml or setup.py found in this directory."
        )

    return requirements


def installPackage(
    package: str, options: Optional[DependecyInstallInfo], verbose: bool
) -> bool:
    # Build the pip install command
    cmd = [sys.executable, "-m", "pip", "install", package]

    # If options provided, add relevant flags
    if options:
        # --platform
        if options.platform:
            cmd += ["--platform", options.platform]
        # --python-version
        if options.pythonVersion:
            cmd += ["--python-version", options.pythonVersion]
        # --implementation
        if options.implementation:
            cmd += ["--implementation", options.implementation]
        # --abi
        if options.abi:
            cmd += ["--abi", options.abi]
        # --only-binary=:all: (using the default from the dataclass)
        if options.onlyBinary:
            cmd += ["--only-binary", options.onlyBinary]
        # --target=dest (install to the destination directory)
        if options.dest:
            cmd += ["--target", str(options.dest)]
        # --extra-index-url if provided
        if options.extraIndexUrl:
            cmd += ["--extra-index-url", options.extraIndexUrl]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode == 0:
        if verbose:
            fprint(f"Package '{package}' installed successfully!")
        return True
    else:
        fprint(f"Failed to install package '{package}'. Error details:")
        fprint(result.stderr)
        return False


def installRequirements(
    requirements: RequirementsSet, options: DependecyInstallInfo, verbose: bool
):
    success = True
    for requirement in requirements:
        success &= installPackage(requirement, options, verbose)

    if success:
        print("Installed all packages successfully")


def main():
    parser = argparse.ArgumentParser(
        prog="Synapse Installer",
        description="Toolset for installing and deploying synpase code",
    )
    parser.add_argument("verbose")

    args = parser.parse_args()

    installRequirements(
        getProjectDeps(Path.cwd()),
        DependecyInstallInfo(
            platform=None,
            pythonVersion="3.10",
            implementation="cp",
            abi="cp310",
            dest=Path.cwd() / "build",
            extraIndexUrl="https://wpilib.jfrog.io/artifactory/api/pypi/wpilib-python-release-2025/simple/",
        ),
        args.verbose,
    )
