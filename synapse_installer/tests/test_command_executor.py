# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
import sys
from unittest import mock

import pytest
import synapse_installer.command_executor as command_executor
from synapse_installer.command_executor import (
    CommandExecutor,
    LocalCommandExecutor,
    RemoteCommandError,
    SSHCommandExecutor,
    runCommand,
)

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
    fake_process = mock.MagicMock()
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
    fake_process = mock.MagicMock()
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


def test_local_exec_command_with_stdin(monkeypatch):
    fake_process = mock.MagicMock()
    fake_process.communicate.return_value = ("done\n", "")
    fake_process.returncode = 0

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_process)

    executor = LocalCommandExecutor()
    out, err, code = executor.execCommand("cat", stdinData="secret\n")

    fake_process.communicate.assert_called_once_with("secret\n")
    assert out == "done\n"
    assert err == ""
    assert code == 0


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
    fake_client = mock.MagicMock()

    connect = mock.Mock(return_value=fake_client)
    monkeypatch.setattr(command_executor, "connectSSH", connect)

    executor = SSHCommandExecutor("host", "user", "pass", timeout=5)

    connect.assert_called_once_with("host", "user", "pass", timeout=5)
    assert executor.client is fake_client


# ---------------------------
# SSHCommandExecutor execCommand
# ---------------------------


def _fake_ssh_client(stdout_data: bytes = b"out\n", stderr_data: bytes = b"", code=0):
    fake_channel = mock.MagicMock()
    fake_channel.exit_status_ready.side_effect = [False, True]
    fake_channel.recv_ready.return_value = True
    fake_channel.recv.return_value = stdout_data
    fake_channel.recv_stderr_ready.return_value = False
    fake_channel.recv_exit_status.return_value = code

    fake_stdout = mock.MagicMock(channel=fake_channel)
    fake_stdout.read.return_value = b""

    fake_stderr = mock.MagicMock(channel=fake_channel)
    fake_stderr.read.return_value = stderr_data

    fake_client = mock.MagicMock()
    fake_client.exec_command.return_value = (None, fake_stdout, fake_stderr)
    return fake_client


def test_ssh_exec_command_success(monkeypatch):
    fake_client = _fake_ssh_client()
    monkeypatch.setattr(
        command_executor, "connectSSH", mock.Mock(return_value=fake_client)
    )

    executor = SSHCommandExecutor("host", "user", "pass")
    out, err, code = executor.execCommand("ls")

    assert out == "out\n"
    assert err == ""
    assert code == 0


def test_ssh_exec_command_with_stdin(monkeypatch):
    fake_client = _fake_ssh_client()
    fake_stdin = mock.MagicMock()
    _, fake_stdout, fake_stderr = fake_client.exec_command.return_value
    fake_client.exec_command.return_value = (fake_stdin, fake_stdout, fake_stderr)

    monkeypatch.setattr(
        command_executor, "connectSSH", mock.Mock(return_value=fake_client)
    )

    executor = SSHCommandExecutor("host", "user", "pass")
    executor.execCommand("sudo -S true", stdinData="secret\n")

    fake_stdin.write.assert_called_once_with("secret\n")
    fake_stdin.channel.shutdown_write.assert_called_once()


def test_ssh_exec_command_exception(monkeypatch):
    fake_client = mock.MagicMock()
    fake_client.exec_command.side_effect = Exception("boom")
    monkeypatch.setattr(
        command_executor, "connectSSH", mock.Mock(return_value=fake_client)
    )

    executor = SSHCommandExecutor("host", "user", "pass")

    with pytest.raises(RuntimeError):
        executor.execCommand("ls")


# ---------------------------
# SSHCommandExecutor close
# ---------------------------


def test_ssh_close_success(monkeypatch):
    fake_client = mock.MagicMock()
    monkeypatch.setattr(
        command_executor, "connectSSH", mock.Mock(return_value=fake_client)
    )

    executor = SSHCommandExecutor("host", "user", "pass")
    executor.close()

    fake_client.close.assert_called()


def test_ssh_close_exception(monkeypatch):
    fake_client = mock.MagicMock()
    fake_client.close.side_effect = Exception("close failed")
    monkeypatch.setattr(
        command_executor, "connectSSH", mock.Mock(return_value=fake_client)
    )

    executor = SSHCommandExecutor("host", "user", "pass")
    executor.close()  # should not raise


# ---------------------------
# runCommand
# ---------------------------


def _run_client(stdout_data=b"", stderr_data=b"", code=0):
    fake_stdout = mock.MagicMock()
    fake_stdout.read.return_value = stdout_data
    fake_stdout.channel.recv_exit_status.return_value = code

    fake_stderr = mock.MagicMock()
    fake_stderr.read.return_value = stderr_data

    client = mock.MagicMock()
    client.exec_command.return_value = (mock.MagicMock(), fake_stdout, fake_stderr)
    return client


def test_run_command_success():
    client = _run_client(b"ok\n", b"", 0)

    out, err, code = runCommand(client, "true")

    assert out == "ok\n"
    assert err == ""
    assert code == 0


def test_run_command_failure_without_check():
    client = _run_client(b"", b"bad\n", 1)

    out, err, code = runCommand(client, "false")

    assert out == ""
    assert err == "bad\n"
    assert code == 1


def test_run_command_failure_with_check_raises():
    client = _run_client(b"", b"bad\n", 1)

    with pytest.raises(RemoteCommandError, match="bad"):
        runCommand(client, "false", check=True)
