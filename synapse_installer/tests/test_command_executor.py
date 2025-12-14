# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
import sys
import types
from unittest.mock import MagicMock

import pytest
from synapse_installer.command_executor import (CommandExecutor,
                                                LocalCommandExecutor,
                                                SSHCommandExecutor)

# ---------------------------
# helpers
# ---------------------------


def infinite_readline(lines):
    """Return a callable that mimics readline(): returns lines, then '' forever."""
    it = iter(lines)

    def _readline():
        try:
            return next(it)
        except StopIteration:
            return ""

    return _readline


# ---------------------------
# Abstract base class
# ---------------------------


def test_command_executor_is_abstract():
    with pytest.raises(TypeError):
        CommandExecutor()  # pyright: ignore


# ---------------------------
# LocalCommandExecutor
# ---------------------------


def test_local_exec_command_success(monkeypatch):
    fake_process = MagicMock()
    fake_process.stdout.readline.side_effect = infinite_readline(["hello\n"])
    fake_process.stderr.readline.side_effect = infinite_readline([])
    fake_process.poll.side_effect = [None, 0]
    fake_process.returncode = 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_process)

    executor = LocalCommandExecutor()
    out, err, code = executor.execCommand("echo hello")

    assert out == "hello\n"
    assert err == ""
    assert code == 0


def test_local_exec_command_stderr(monkeypatch):
    fake_process = MagicMock()
    fake_process.stdout.readline.side_effect = infinite_readline([])
    fake_process.stderr.readline.side_effect = infinite_readline(["err\n"])
    fake_process.poll.side_effect = [None, 1]
    fake_process.returncode = 1

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_process)

    executor = LocalCommandExecutor()
    out, err, code = executor.execCommand("badcmd")

    assert out == ""
    assert err == "err\n"
    assert code == 1


def test_local_close_is_noop():
    LocalCommandExecutor().close()


# ---------------------------
# SSHCommandExecutor init
# ---------------------------


def test_ssh_init_missing_paramiko(monkeypatch):
    monkeypatch.setitem(sys.modules, "paramiko", None)

    with pytest.raises(ImportError):
        SSHCommandExecutor("host", "user", "pass")


def test_ssh_init_connects(monkeypatch):
    fake_client = MagicMock()

    fake_paramiko = types.SimpleNamespace(
        SSHClient=lambda: fake_client,
        AutoAddPolicy=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    SSHCommandExecutor("host", "user", "pass")

    fake_client.connect.assert_called()


# ---------------------------
# SSHCommandExecutor execCommand
# ---------------------------


def test_ssh_exec_command_success(monkeypatch):
    fake_channel = MagicMock()
    fake_channel.exit_status_ready.side_effect = [False, True]
    fake_channel.recv_ready.return_value = True
    fake_channel.recv.return_value = b"out\n"
    fake_channel.recv_stderr_ready.return_value = False
    fake_channel.recv_exit_status.return_value = 0

    fake_stdout = MagicMock(channel=fake_channel)
    fake_stdout.read.return_value = b""

    fake_stderr = MagicMock(channel=fake_channel)
    fake_stderr.read.return_value = b""

    fake_client = MagicMock()
    fake_client.exec_command.return_value = (None, fake_stdout, fake_stderr)

    fake_paramiko = types.SimpleNamespace(
        SSHClient=lambda: fake_client,
        AutoAddPolicy=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    executor = SSHCommandExecutor("host", "user", "pass")
    out, err, code = executor.execCommand("ls")

    assert out == "out\n"
    assert err == ""
    assert code == 0


def test_ssh_exec_command_exception(monkeypatch):
    fake_client = MagicMock()
    fake_client.exec_command.side_effect = Exception("boom")

    fake_paramiko = types.SimpleNamespace(
        SSHClient=lambda: fake_client,
        AutoAddPolicy=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    executor = SSHCommandExecutor("host", "user", "pass")

    with pytest.raises(RuntimeError):
        executor.execCommand("ls")


# ---------------------------
# SSHCommandExecutor close
# ---------------------------


def test_ssh_close_success(monkeypatch):
    fake_client = MagicMock()

    fake_paramiko = types.SimpleNamespace(
        SSHClient=lambda: fake_client,
        AutoAddPolicy=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    executor = SSHCommandExecutor("host", "user", "pass")
    executor.close()

    fake_client.close.assert_called()


def test_ssh_close_exception(monkeypatch):
    fake_client = MagicMock()
    fake_client.close.side_effect = Exception("close failed")

    fake_paramiko = types.SimpleNamespace(
        SSHClient=lambda: fake_client,
        AutoAddPolicy=lambda: None,
    )

    monkeypatch.setitem(sys.modules, "paramiko", fake_paramiko)

    executor = SSHCommandExecutor("host", "user", "pass")
    executor.close()  # should not raise
