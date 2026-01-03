# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, List, Tuple

import pytest
# import the module under test
import synapse_installer.sync as sync_mod


class FakeExecutor(sync_mod.CommandExecutor):
    """
    Deterministic fake executor.
    You register command -> (stdout, stderr, exitCode)
    """

    def __init__(self, responses: Dict[str, Tuple[str, str, int]]):
        self.responses = responses
        self.commands: List[str] = []
        self.closed = False

    def execCommand(self, command: str):
        self.commands.append(command.strip())
        for key, result in self.responses.items():
            if key in command:
                return result
        return ("", "command not found", 127)

    def close(self):
        self.closed = True


# ------------------------------------------------------------
# findOrInstallPython
# ------------------------------------------------------------


def test_find_python_existing_version():
    executor = FakeExecutor(
        {
            "python3.12 -c": ("(3, 12, 1)", "", 0),
        }
    )

    python = sync_mod.findOrInstallPython(executor, minPython="3.12")

    assert python == "python3.12"
    assert any("python3.12 -c" in c for c in executor.commands)


def test_find_python_fallback_to_python3():
    executor = FakeExecutor(
        {
            "python3.12 -c": ("", "command not found", 127),
            "python3.13 -c": ("", "command not found", 127),
            "python3 -c": ("(3, 12, 0)", "", 0),
        }
    )

    python = sync_mod.findOrInstallPython(executor, minPython="3.12")
    assert python == "python3"


def test_find_python_install_when_missing(monkeypatch):
    executor = FakeExecutor(
        {
            "python3.12 -c": ("", "command not found", 127),
            "python3.13 -c": ("", "command not found", 127),
            "python3 -c": ("(3, 9, 0)", "", 0),
            "wget -O Python-3.12.2.tgz": ("", "", 0),
        }
    )

    installed = []

    def fake_install(executor, pkg, useSudo=True):
        installed.append(pkg)

    monkeypatch.setattr(sync_mod, "installSystemPackage", fake_install)

    python = sync_mod.findOrInstallPython(executor)

    assert python == "python3.12"
    assert "build-essential" in installed


# ------------------------------------------------------------
# installSystemPackage
# ------------------------------------------------------------


def test_install_system_package_already_installed():
    executor = FakeExecutor(
        {
            "command -v apt": ("", "", 0),
            "dpkg -s curl": ("", "", 0),
        }
    )

    sync_mod.installSystemPackage(executor, "curl")

    assert any("dpkg -s curl" in c for c in executor.commands)
    assert not any("apt install" in c for c in executor.commands)


def test_install_system_package_installs():
    executor = FakeExecutor(
        {
            "command -v apt": ("", "", 0),
            "dpkg -s curl": ("", "", 1),
            "apt install -y curl": ("", "", 0),
        }
    )

    sync_mod.installSystemPackage(executor, "curl")

    assert any("apt install -y curl" in c for c in executor.commands)


def test_install_system_package_no_manager():
    executor = FakeExecutor({})

    with pytest.raises(RuntimeError):
        sync_mod.installSystemPackage(executor, "curl")


# ------------------------------------------------------------
# ensureVenvWithPython
# ------------------------------------------------------------


def test_ensure_venv_existing(monkeypatch, tmp_path):
    venv_python = tmp_path / ".venv/bin/python"

    executor = FakeExecutor(
        {
            "import sys; print(sys.executable)": (str(venv_python), "", 0),
            "pip freeze": ("requests==2.31.0", "", 0),
        }
    )

    path = sync_mod.ensureVenvWithPython(
        executor,
        tmp_path,
        requirements=["requests==2.31.0"],
    )

    assert path == str(venv_python)
    assert not any("-m venv" in c for c in executor.commands)


def test_ensure_venv_created(monkeypatch, tmp_path):
    executor = FakeExecutor(
        {
            "pip freeze": ("", "", 0),
        }
    )

    monkeypatch.setattr(
        sync_mod,
        "findOrInstallPython",
        lambda executor, minPython: "python3.12",
    )

    path = sync_mod.ensureVenvWithPython(
        executor,
        tmp_path,
        requirements=[],
    )

    assert path.endswith(".venv/bin/python")
    assert any("-m venv .venv" in c for c in executor.commands)


def test_ensure_venv_installs_missing_package(monkeypatch, tmp_path):
    executor = FakeExecutor(
        {
            "pip freeze": ("numpy==1.24.4", "", 0),
        }
    )

    monkeypatch.setattr(
        sync_mod,
        "findOrInstallPython",
        lambda executor, minPython: "python3.12",
    )

    sync_mod.ensureVenvWithPython(
        executor,
        tmp_path,
        requirements=["numpy==1.24.4", "requests==2.31.0"],
    )

    assert any("pip install requests==2.31.0" in c for c in executor.commands)


# ------------------------------------------------------------
# syncRequirements
# ------------------------------------------------------------


def test_sync_requirements_happy_path(monkeypatch):
    executor = FakeExecutor(
        {
            "echo $HOME": ("/home/test", "", 0),
        }
    )

    monkeypatch.setattr(sync_mod, "setupSudoers", lambda *a, **k: None)
    monkeypatch.setattr(sync_mod, "installSystemPackage", lambda *a, **k: None)
    monkeypatch.setattr(sync_mod, "ensureVenvWithPython", lambda *a, **k: None)
    monkeypatch.setattr(sync_mod, "runAndGetWithExecutor", lambda *a, **k: "/home/test")

    sync_mod.syncRequirements(
        executor,
        hostname="robot",
        username="root",
        password="pw",
        requirements=["requests"],
    )

    assert executor.closed is True


# ------------------------------------------------------------
# syncLocal
# ------------------------------------------------------------


def test_sync_local(monkeypatch):
    called = {}

    def fake_ensure(executor, path, requirements, wplibYear=None):
        called["ok"] = True

    monkeypatch.setattr(sync_mod, "ensureVenvWithPython", fake_ensure)

    sync_mod.syncLocal(["requests"])

    assert called["ok"] is True
