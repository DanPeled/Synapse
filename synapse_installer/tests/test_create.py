from pathlib import Path
from unittest import mock

import pytest
from synapse_installer.create import createProject, baseMainPy


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
    assert (project_dir / ".synapseproject").exists() is True
    assert (project_dir / "main.py").exists() is True
    assert (project_dir / "pipelines").is_dir()
    assert (project_dir / "deploy").is_dir()
    assert (
        (project_dir / "deploy" / "readme.md")
        .read_text()
        .startswith("# TestProject Deploy")
    )

    main_py_content = (project_dir / "main.py").read_text()
    assert main_py_content == baseMainPy

    # Ensure device config was not triggered
    mock_load.assert_not_called()


@mock.patch("questionary.text")
@mock.patch("questionary.confirm")
@mock.patch("synapse_installer.create.loadDeviceData")
def test_create_project_with_device_config(
    mock_load, mock_confirm, mock_text, fake_cwd
):
    mock_text().ask.return_value = "DeviceProject"
    mock_confirm().ask.return_value = True

    createProject()

    project_dir = fake_cwd / "DeviceProject"
    assert project_dir.exists()
    assert (project_dir / ".deployconfig").exists() is False

    mock_load.assert_called_once_with(project_dir / ".deployconfig")


@mock.patch("questionary.text")
def test_create_project_cancelled(mock_text, fake_cwd):
    mock_text().ask.return_value = None

    createProject()
    assert not any(fake_cwd.iterdir())
