# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import configparser
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

IMAGER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = IMAGER_DIR.parent
PLATFORMS = IMAGER_DIR / "platforms.py"
REGISTRY = IMAGER_DIR / "platforms.ini"


def shellScripts() -> list[Path]:
    scripts = sorted(IMAGER_DIR.rglob("*.sh"))
    exportImage = IMAGER_DIR / "raspberrypi/stage-synapse/EXPORT_IMAGE"
    if exportImage.exists():
        scripts.append(exportImage)
    return scripts


def runPlatforms(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PLATFORMS), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def registryTargets() -> set[str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = lambda optionstr: optionstr
    parser.read(REGISTRY)
    return {
        section[len("target.") :]
        for section in parser.sections()
        if section.startswith("target.")
    }


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
        IMAGER_DIR / "build.sh",
        IMAGER_DIR / "common/provision.sh",
        IMAGER_DIR / "raspberrypi/build.sh",
        IMAGER_DIR / "raspberrypi/setup.sh",
        IMAGER_DIR / "armbian/build.sh",
        IMAGER_DIR / "overlay/build.sh",
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
    output = result.stdout.lower()
    assert "usage" in output or "build" in output


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


def testPlatformRegistryIsValid() -> None:
    result = runPlatforms("validate")

    assert result.returncode == 0, result.stderr
    assert "Registry OK" in result.stdout


def testPlatformRegistryListsEveryTarget() -> None:
    result = runPlatforms("list")

    assert result.returncode == 0, result.stderr
    for target in registryTargets():
        assert target in result.stdout


def testPlatformMatrixIncludesEveryRegistryTarget() -> None:
    result = runPlatforms("matrix")

    assert result.returncode == 0, result.stderr
    matrix = json.loads(result.stdout)
    assert {entry["target"] for entry in matrix} == registryTargets()

    for entry in matrix:
        assert entry["name"]
        assert entry["runner"]
        assert entry["timeout"] > 0
        assert isinstance(entry["free_disk"], bool)
        assert entry["artifact"]
        assert isinstance(entry["setup"], str)


def testPlatformMatrixFiltersByPlatform() -> None:
    result = runPlatforms("matrix", "--targets", "armbian")

    assert result.returncode == 0, result.stderr
    matrix = json.loads(result.stdout)
    assert matrix
    assert {entry["platform"] for entry in matrix} == {"armbian"}


def testPlatformMatrixFiltersByTarget() -> None:
    result = runPlatforms("matrix", "--targets", "orangepi5-plus")

    assert result.returncode == 0, result.stderr
    matrix = json.loads(result.stdout)
    assert [entry["target"] for entry in matrix] == ["orangepi5-plus"]


def testPlatformMatrixRejectsUnknownSelection() -> None:
    result = runPlatforms("matrix", "--targets", "not-a-board")

    assert result.returncode != 0
    assert "Unknown platform or target" in result.stderr


def testPlatformBuildDryRunUsesRegistryDefaults() -> None:
    result = runPlatforms("build", "orangepi5", "--dry-run")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["platform"] == "armbian"
    assert plan["target"] == "orangepi5"
    assert plan["builder"] == "armbian/build.sh"
    assert plan["command"] == ["bash", "armbian/build.sh"]
    assert plan["env"]["BOARD"] == "orangepi5"
    assert plan["env"]["PREFER_DOCKER"] == "yes"
    assert plan["env"]["SYNAPSE_PLATFORM"] == "armbian"
    assert plan["env"]["SYNAPSE_TARGET"] == "orangepi5"


def testPlatformBuildDryRunSupportsX86_64Overlay() -> None:
    result = runPlatforms("build", "x86-64", "--dry-run")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["platform"] == "overlay"
    assert plan["target"] == "x86-64"
    assert plan["builder"] == "overlay/build.sh"
    assert plan["command"] == ["bash", "overlay/build.sh"]
    assert plan["env"]["SYNAPSE_TARGET"] == "x86-64"
    assert plan["env"]["OVERLAY_NAME"] == "x86_64"


def testPlatformEnvPrintsShellExports() -> None:
    result = runPlatforms("env", "raspberrypi")

    assert result.returncode == 0, result.stderr
    assert "export RELEASE=bookworm" in result.stdout
    assert "export SYNAPSE_PLATFORM=raspberrypi" in result.stdout
    assert "export SYNAPSE_TARGET=raspberrypi" in result.stdout


def testReleaseWorkflowStructure() -> None:
    workflowPath = REPO_ROOT / ".github/workflows/release_images.yml"
    workflow = yaml.safe_load(workflowPath.read_text())

    triggers = workflow.get("on") or workflow.get(True)
    assert isinstance(triggers, dict)
    assert "push" in triggers
    assert "v*" in triggers["push"]["tags"]
    assert "targets" in triggers["workflow_dispatch"]["inputs"]

    jobs = workflow["jobs"]
    for job in ("prepare", "wheel", "images", "release"):
        assert job in jobs, f"missing job {job}"

    assert "matrix" in jobs["prepare"]["outputs"]
    assert "matrix" in jobs["images"]["strategy"]
    assert (
        jobs["images"]["strategy"]["matrix"]["include"]
        == "${{ fromJSON(needs.prepare.outputs.matrix) }}"
    )
    assert jobs["release"]["if"] == "startsWith(github.ref, 'refs/tags/')"


def testReleaseWorkflowRegistersQemuForCrossArchBuilds() -> None:
    workflowPath = REPO_ROOT / ".github/workflows/release_images.yml"
    workflow = yaml.safe_load(workflowPath.read_text())

    steps = workflow["jobs"]["images"]["steps"]
    qemuSteps = [
        step
        for step in steps
        if step.get("uses", "").startswith("docker/setup-qemu-action@")
    ]

    assert len(qemuSteps) == 1
    assert qemuSteps[0]["if"] == "matrix.platform != 'overlay'"
