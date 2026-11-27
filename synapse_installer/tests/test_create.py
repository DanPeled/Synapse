# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from importlib.resources import files
from pathlib import Path
from unittest import mock

import pytest
from synapse_installer.create import baseMainPy, createProject
from synapse_installer.util import SYNAPSE_PROJECT_FILE


@pytest.fixture
def fake_cwd(tmp_path, monkeypatch):
    # Use a temporary directory as the fake working directory
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    return tmp_path


@mock.patch("questionary.text")
@mock.patch("questionary.confirm")
@mock.patch("synapse_installer.create.loadDeviceData")
def test_create_project_basic(mock_load, mock_confirm, mock_text, fake_cwd):
    # Setup mocks
    mock_text().ask.return_value = "TestProject"
    mock_confirm().ask.return_value = False

    # Run function
    createProject()

    project_dir = fake_cwd / "TestProject"

    assert project_dir.exists()
    assert (project_dir / SYNAPSE_PROJECT_FILE).exists() is True
    assert (project_dir / "main.py").exists() is True
    assert (project_dir / "pipelines").is_dir()
    assert (project_dir / "deploy").is_dir()
    assert (
        (project_dir / "deploy" / "readme.md")
        .read_text()
        .startswith("# TestProject Deploy")
    )

    fieldMap = json.loads((project_dir / "deploy" / "fmap.json").read_text())
    assert len(fieldMap["tags"]) == 32
    assert fieldMap["field"]["length"] == 16.541

    main_py_content = (project_dir / "main.py").read_text()
    assert main_py_content == baseMainPy

    # Ensure device config was not triggered
    mock_load.assert_not_called()


def test_bundled_field_map_matches_example_project():
    repoRoot = Path(__file__).resolve().parents[2]
    example = repoRoot / "examples" / "synapseproject" / "deploy" / "fmap.json"
    bundled = (
        files("synapse_installer").joinpath("assets").joinpath("fmap.json").read_bytes()
    )

    assert bundled == example.read_bytes()


@mock.patch("questionary.text")
def test_create_project_cancelled(mock_text, fake_cwd):
    mock_text().ask.return_value = None

    createProject()
    assert not any(fake_cwd.iterdir())
