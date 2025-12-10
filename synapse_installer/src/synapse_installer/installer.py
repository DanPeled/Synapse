# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import builtins
import os
import runpy
import subprocess
import types
import venv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Set

import toml
from rich import print as fprint
from synapse import __version__ as synpaseVersion


RequirementsSet = Set[str]
PROJECT_ROOT = Path.cwd()
VENV_DIR = PROJECT_ROOT / ".venv"


@dataclass(frozen=True)
class DependencyInstallInfo:
    platform: Optional[str]
    pythonVersion: Optional[str]
    implementation: Optional[str]
    abi: Optional[str]
    onlyBinary: str = ":all:"
    extraIndexUrl: Optional[str] = None


class DependencyFiles(Enum):
    SETUP_PY = "setup.py"
    PYPROJECT = "pyproject.toml"


def ensure_venv(venv_dir: Path) -> Path:
    """Ensure virtualenv exists and return path to its python."""
    if not venv_dir.exists():
        fprint("[cyan]Creating virtual environment...[/cyan]")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    python = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )

    if not python.exists():
        raise RuntimeError("Virtualenv python not found")

    return python


# -----------------------------
# Dependency discovery
# -----------------------------


def extract_install_requires(setup_path: Path) -> RequirementsSet:
    """Safely extract install_requires from setup.py."""
    setup_args = {}

    fake_setuptools = types.ModuleType("setuptools")
    fake_setuptools.setup = lambda **kwargs: setup_args.update(kwargs)  # type: ignore
    fake_setuptools.find_packages = lambda *_, **__: []  # pyright: ignore

    old_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "setuptools":
            return fake_setuptools
        return old_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        runpy.run_path(str(setup_path.resolve()))
    finally:
        builtins.__import__ = old_import

    return set(setup_args.get("install_requires", []))


def get_project_dependencies(cwd: Path) -> RequirementsSet:
    requirements: RequirementsSet = set()

    pyproject = cwd / DependencyFiles.PYPROJECT.value
    setup_py = cwd / DependencyFiles.SETUP_PY.value

    if pyproject.exists():
        data = toml.load(pyproject)
        project = data.get("project", {})
        requirements.update(project.get("dependencies", []))

        for extras in project.get("optional-dependencies", {}).values():
            requirements.update(extras)

    if setup_py.exists():
        requirements.update(extract_install_requires(setup_py))

    if not requirements:
        raise FileNotFoundError(
            "No dependencies found (missing pyproject.toml and setup.py)"
        )

    return requirements


# -----------------------------
# Installation logic
# -----------------------------


def install_package(
    python: Path,
    package: str,
    options: DependencyInstallInfo,
    verbose: bool,
) -> None:
    cmd = [str(python), "-m", "pip", "install", package]

    if options.platform:
        cmd += ["--platform", options.platform]
    if options.pythonVersion:
        cmd += ["--python-version", options.pythonVersion]
    if options.implementation:
        cmd += ["--implementation", options.implementation]
    if options.abi:
        cmd += ["--abi", options.abi]
    if options.onlyBinary:
        cmd += ["--only-binary", options.onlyBinary]
    if options.extraIndexUrl:
        cmd += ["--extra-index-url", options.extraIndexUrl]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install dependency: {package}")

    if verbose:
        fprint(f"[green]Installed[/green] {package}")


def install_requirements(
    python: Path,
    requirements: RequirementsSet,
    options: DependencyInstallInfo,
    verbose: bool,
) -> None:
    for req in sorted(requirements):
        install_package(python, req, options, verbose)

    fprint("[bold green]All dependencies installed successfully[/bold green]")


# -----------------------------
# Entrypoint
# -----------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="synapse-installer",
        description="Install Synapse project dependencies in a virtual environment",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    python = ensure_venv(VENV_DIR)
    deps = get_project_dependencies(PROJECT_ROOT)

    install_requirements(
        python,
        deps,
        DependencyInstallInfo(
            platform=None,
            pythonVersion="3.10",
            implementation="cp",
            abi="cp310",
            extraIndexUrl=(
                "https://wpilib.jfrog.io/artifactory/api/pypi/"
                f"wpilib-python-release-{synpaseVersion.WPILIB_YEAR}/simple/"
            ),
        ),
        args.verbose,
    )


if __name__ == "__main__":
    main()
