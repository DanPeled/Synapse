# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from pathlib import Path

import pytest
import yaml

IMAGER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = IMAGER_DIR.parent


def shellScripts() -> list[Path]:
    scripts = sorted(IMAGER_DIR.rglob("*.sh"))
    exportImage = IMAGER_DIR / "raspberrypi/stage-synapse/EXPORT_IMAGE"
    if exportImage.exists():
        scripts.append(exportImage)
    return scripts


@pytest.mark.parametrize("script", shellScripts(), ids=lambda path: str(path.name))
def testShellScriptsParse(script: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{script} is not valid bash:\n{result.stderr}"


@pytest.mark.parametrize(
    "script",
    [
        IMAGER_DIR / "common/provision.sh",
        IMAGER_DIR / "raspberrypi/build.sh",
        IMAGER_DIR / "orangepi/build.sh",
        IMAGER_DIR / "jetson/build.sh",
    ],
    ids=lambda path: str(path.name),
)
def testBuildScriptsHaveHelp(script: Path) -> None:
    result = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout or "Build" in result.stdout


def testSampleProjectIsSelfContained() -> None:
    sample = IMAGER_DIR / "sample_project"

    for relative in (
        ".synapseproject",
        "main.py",
        "config/settings.yml",
        "pyproject.toml",
        "deploy/README.md",
        "pipelines/.gitkeep",
    ):
        assert (sample / relative).is_file(), f"missing {relative}"

    settings = yaml.safe_load((sample / "config/settings.yml").read_text())
    assert settings["network"]["team_number"] == 0
    assert settings["global"]["cameras"] == []

    project = yaml.safe_load((sample / ".synapseproject").read_text())
    assert project["name"] == "synapse-sample"
    assert "deploy" not in project


def testSampleProjectHasNoCredentials() -> None:
    sample = IMAGER_DIR / "sample_project"

    for path in sample.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore").lower()
        assert "password:" not in text, f"{path} contains a password"
        assert "10.72." not in text, f"{path} contains a team IP address"


def testProvisionScriptInstallsRuntimeAndService() -> None:
    text = (IMAGER_DIR / "common/provision.sh").read_text()

    assert "NOPASSWD:ALL" in text
    assert "synapse-runtime" in text
    assert "/etc/systemd/system" in text
    assert "-m venv" in text
    assert "pip install" in text
    assert "3, 11" in text


def testRaspberryPiStageUsesSharedProvisioner() -> None:
    text = (
        IMAGER_DIR / "raspberrypi/stage-synapse/00-synapse/01-run.sh"
    ).read_text()

    assert "provision.sh" in text
    assert "--cleanup" in text
    assert "--user" in text


def testReleaseWorkflowStructure() -> None:
    workflowPath = REPO_ROOT / ".github/workflows/release_images.yml"
    workflow = yaml.safe_load(workflowPath.read_text())

    triggers = workflow.get("on") or workflow.get(True)
    assert isinstance(triggers, dict)
    assert "push" in triggers
    assert "v*" in triggers["push"]["tags"]

    jobs = workflow["jobs"]
    for job in ("prepare", "wheel", "raspberrypi", "orangepi", "jetson", "release"):
        assert job in jobs, f"missing job {job}"

    assert jobs["release"]["if"] == "startsWith(github.ref, 'refs/tags/')"
