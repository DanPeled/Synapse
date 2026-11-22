# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, List, Optional, Tuple
from unittest import mock

import pytest

# import the module under test
import synapse_installer.sync as sync_mod
import yaml


class FakeExecutor(sync_mod.CommandExecutor):
    """
    Deterministic fake executor.
    You register command -> (stdout, stderr, exitCode)
    """

    def __init__(self, responses: Dict[str, Tuple[str, str, int]]):
        self.responses = responses
        self.commands: List[str] = []
        self.stdin: List[Optional[str]] = []
        self.closed = False

    def execCommand(self, command: str, stdinData: Optional[str] = None):
        self.commands.append(command.strip())
        self.stdin.append(stdinData)
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


def test_install_system_package_failure_raises():
    executor = FakeExecutor(
        {
            "command -v apt": ("", "", 0),
            "dpkg -s curl": ("", "", 1),
            "apt install -y curl": ("", "boom", 100),
        }
    )

    with pytest.raises(RuntimeError, match="boom"):
        sync_mod.installSystemPackage(executor, "curl")


def test_install_system_package_no_manager():
    executor = FakeExecutor({})

    with pytest.raises(RuntimeError):
        sync_mod.installSystemPackage(executor, "curl")


def test_setup_sudoers_sends_password_on_stdin():
    executor = FakeExecutor({"sudo -S": ("", "", 0)})

    assert sync_mod.setupSudoers(executor, "robot", "pi", "s3cret") is True

    assert executor.stdin[0] == "s3cret\n"
    assert "s3cret" not in executor.commands[0]
    assert "NOPASSWD" in executor.commands[0]


def test_setup_sudoers_failure_returns_false():
    executor = FakeExecutor({"sudo -S": ("", "denied", 1)})

    assert sync_mod.setupSudoers(executor, "robot", "pi", "pw") is False


def test_setup_sudoers_rejects_bad_username():
    executor = FakeExecutor({"sudo -S": ("", "", 0)})

    assert sync_mod.setupSudoers(executor, "robot", "pi ALL=(ALL)", "pw") is False
    assert executor.commands == []


def test_install_pip_requirements_failure_raises():
    executor = FakeExecutor(
        {
            "freeze": ("", "", 0),
            "install requests": ("", "no network", 1),
        }
    )

    with pytest.raises(RuntimeError, match="requests"):
        sync_mod.installPipRequirements(executor, ["requests"], "venv/bin/pip")


def test_sync_requirements_happy_path(monkeypatch):
    executor = FakeExecutor(
        {
            "echo $HOME": ("/home/test", "", 0),
        }
    )

    monkeypatch.setattr(sync_mod, "setupSudoers", lambda *a, **k: True)
    monkeypatch.setattr(sync_mod, "installSystemPackage", lambda *a, **k: None)
    monkeypatch.setattr(sync_mod, "ensurePythonInRange", lambda *a, **k: "python3.12")
    monkeypatch.setattr(sync_mod, "ensureVenv", lambda *a, **k: "venv/bin/pip")
    monkeypatch.setattr(sync_mod, "installPipRequirements", lambda *a, **k: None)

    assert (
        sync_mod.syncRequirements(
            executor,
            hostname="robot",
            username="root",
            password="pw",
            requirements=["requests"],
        )
        is True
    )

    assert executor.closed is True


def test_sync_requirements_stops_when_sudoers_fails(monkeypatch):
    executor = FakeExecutor({"sudo -n true": ("", "", 1)})

    monkeypatch.setattr(sync_mod, "setupSudoers", lambda *a, **k: False)
    install = mock.Mock()
    monkeypatch.setattr(sync_mod, "installSystemPackage", install)

    assert (
        sync_mod.syncRequirements(
            executor,
            hostname="robot",
            username="root",
            password="pw",
            requirements=["requests"],
        )
        is False
    )

    install.assert_not_called()
    assert executor.closed is True


def test_sync_cli_without_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert sync_mod.sync([]) == 1


def test_sync_cli_missing_device(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synapseproject").write_text(
        yaml.dump(
            {"deploy": {"robot": {"hostname": "pi", "ip": "1.2.3.4", "password": "pw"}}}
        )
    )

    assert sync_mod.sync(["nope"]) == 1


def test_sync_cli_syncs_all_devices(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synapseproject").write_text(
        yaml.dump(
            {
                "deploy": {
                    "one": {"hostname": "pi", "ip": "1.2.3.4", "password": "pw"},
                    "two": {"hostname": "pi", "ip": "5.6.7.8", "password": "pw"},
                }
            }
        )
    )

    executors = []

    def fake_executor(**kwargs):
        executor = mock.Mock()
        executor.execCommand.return_value = ("", "", 0)
        executors.append(kwargs)
        return executor

    monkeypatch.setattr(sync_mod, "SSHCommandExecutor", fake_executor)
    monkeypatch.setattr(sync_mod, "syncRequirements", mock.Mock(return_value=True))
    monkeypatch.setattr(sync_mod, "getDistRequirements", lambda: [])
    monkeypatch.setattr(sync_mod, "getUserRequirements", lambda *a, **k: [])

    assert sync_mod.sync([]) == 0
    assert [entry["hostname"] for entry in executors] == ["1.2.3.4", "5.6.7.8"]


def test_sync_local_uses_local_executor(monkeypatch):
    executor = mock.Mock()
    monkeypatch.setattr(sync_mod, "LocalCommandExecutor", lambda: executor)
    install = mock.Mock()
    monkeypatch.setattr(sync_mod, "installPipRequirements", install)

    sync_mod.syncLocal(["requests"], "2026")

    install.assert_called_once()
    assert isinstance(install.call_args.args[0], mock.Mock)
    assert install.call_args.args[1] == ["requests"]
