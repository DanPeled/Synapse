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
