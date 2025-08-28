# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import toml
from synapse_installer.util import getUserRequirements


def write_pyproject(tmp_path: Path, content: dict) -> Path:
    """Helper to write a pyproject.toml from a dict."""
    path = tmp_path / "pyproject.toml"
    with open(path, "w") as f:
        toml.dump(content, f)
    return path


def test_requires_present(tmp_path):
    content = {"tool": {"synapse": {"requires": ["numpy", "scipy>=1.7"]}}}
    pyproject = write_pyproject(tmp_path, content)
    assert getUserRequirements(pyproject) == ["numpy", "scipy>=1.7"]


def test_requires_missing_returns_empty(tmp_path):
    content = {"tool": {"synapse": {}}}
    pyproject = write_pyproject(tmp_path, content)
    assert getUserRequirements(pyproject) == []


def test_synapse_missing_returns_empty(tmp_path):
    content = {"tool": {}}
    pyproject = write_pyproject(tmp_path, content)
    assert getUserRequirements(pyproject) == []


def test_tool_missing_returns_empty(tmp_path):
    content = {}
    pyproject = write_pyproject(tmp_path, content)
    assert getUserRequirements(pyproject) == []
