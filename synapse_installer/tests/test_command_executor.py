# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
from pathlib import Path
from unittest import mock

import paramiko
import pytest
from synapse_installer.command_executor import (LocalCommandExecutor,
                                                SSHCommandExecutor)


class TestLocalCommandExecutor:
    """Tests for LocalCommandExecutor."""

    def test_execute_success(self, mocker) -> None:
        """Test successful local command execution."""
        mockRun: mock.Mock = mocker.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=0, stdout="output", stderr=""),
        )
        mocker.patch.object(
            LocalCommandExecutor, "_getVenvPython", return_value=Path("/mock/python")
        )

        executor: LocalCommandExecutor = LocalCommandExecutor(venvDir=Path(".venv"))
        stdout: str
        stderr: str
        exitCode: int
        stdout, stderr, exitCode = executor.execCommand("echo hello")

        assert stdout == "output"
        assert stderr == ""
        assert exitCode == 0
        mockRun.assert_called_once()

    def test_execute_failure(self, mocker) -> None:
        """Test local command execution with non-zero exit code."""
        mocker.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="error"),
        )
        mocker.patch.object(
            LocalCommandExecutor, "_getVenvPython", return_value=Path("/mock/python")
        )

        executor: LocalCommandExecutor = LocalCommandExecutor(venvDir=Path(".venv"))
        stdout: str
        stderr: str
        exitCode: int
        stdout, stderr, exitCode = executor.execCommand("invalid command")

        assert stderr == "error"
        assert exitCode == 1

    def test_venv_python_normalization(self, mocker) -> None:
        """Test that python commands are normalized with venv path."""
        mockRun: mock.Mock = mocker.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=0, stdout="3.11.0", stderr=""),
        )
        mocker.patch.object(
            LocalCommandExecutor,
            "_getVenvPython",
            return_value=Path("/venv/bin/python"),
        )

        executor: LocalCommandExecutor = LocalCommandExecutor(venvDir=Path(".venv"))
        executor.execCommand("python --version")

        callArgs: str = mockRun.call_args[0][0]
        assert "/venv/bin/python" in callArgs

    def test_python3_normalization(self, mocker) -> None:
        """Test that python3 commands are normalized with venv path."""
        mockRun: mock.Mock = mocker.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=0, stdout="3.11.0", stderr=""),
        )
        mocker.patch.object(
            LocalCommandExecutor,
            "_getVenvPython",
            return_value=Path("/venv/bin/python"),
        )

        executor: LocalCommandExecutor = LocalCommandExecutor(venvDir=Path(".venv"))
        executor.execCommand("python3 script.py")

        callArgs: str = mockRun.call_args[0][0]
        assert "/venv/bin/python script.py" in callArgs

    def test_close_noop(self, mocker) -> None:
        """Test that close() is a no-op for local executor."""
        mocker.patch.object(
            LocalCommandExecutor, "_getVenvPython", return_value=Path("/mock/python")
        )

        executor: LocalCommandExecutor = LocalCommandExecutor(venvDir=Path(".venv"))
        # Should not raise
        executor.close()


class TestSSHCommandExecutor:
    """Tests for SSHCommandExecutor."""

    @pytest.fixture
    def mockSSHClient(self, mocker) -> mock.Mock:
        """Create a mock SSH client."""
        client: mock.Mock = mocker.Mock(spec=paramiko.SSHClient)
        mockChannel: mock.Mock = mocker.Mock()
        mockChannel.recv_exit_status.return_value = 0

        stdout: io.BytesIO = io.BytesIO(b"output")
        stdout.channel = mockChannel
        stderr: io.BytesIO = io.BytesIO(b"")

        client.exec_command.return_value = (io.BytesIO(b""), stdout, stderr)
        client.get_transport.return_value = mocker.Mock()
        return client

    def test_init_success(self, mocker, mockSSHClient) -> None:
        """Test successful SSH initialization and connection."""
        mocker.patch("paramiko.SSHClient", return_value=mockSSHClient)

        executor: SSHCommandExecutor = SSHCommandExecutor(
            hostname="robot",
            username="admin",
            password="pass123",
            venvDir=".venv",
        )

        mockSSHClient.connect.assert_called_once()
        assert executor.hostname == "robot"
        assert executor.venvPython == ".venv/bin/python"

    def test_execute_remote_command(self, mocker, mockSSHClient) -> None:
        """Test executing a command on remote machine."""
        mocker.patch("paramiko.SSHClient", return_value=mockSSHClient)

        executor: SSHCommandExecutor = SSHCommandExecutor(
            hostname="robot",
            username="admin",
            password="pass123",
            venvDir=".venv",
        )
        stdout: str
        stderr: str
        exitCode: int
        stdout, stderr, exitCode = executor.execCommand("echo hello")

        mockSSHClient.exec_command.assert_called()
        assert stdout == "output"
        assert exitCode == 0

    def test_close_connection(self, mocker, mockSSHClient) -> None:
        """Test closing SSH connection."""
        mocker.patch("paramiko.SSHClient", return_value=mockSSHClient)

        executor: SSHCommandExecutor = SSHCommandExecutor(
            hostname="robot",
            username="admin",
            password="pass123",
            venvDir=".venv",
        )
        executor.close()

        mockSSHClient.close.assert_called_once()

    def test_execute_with_venv_normalization(self, mocker, mockSSHClient) -> None:
        """Test that remote venv path is used in python commands."""
        mocker.patch("paramiko.SSHClient", return_value=mockSSHClient)

        executor: SSHCommandExecutor = SSHCommandExecutor(
            hostname="robot",
            username="admin",
            password="pass123",
            venvDir="/custom/venv",
        )
        executor.execCommand("python script.py")

        callArgs: str = mockSSHClient.exec_command.call_args[0][0]
        assert "/custom/venv/bin/python script.py" in callArgs

    def test_connection_failure(self, mocker) -> None:
        """Test handling of SSH connection failure."""
        mockClient: mock.Mock = mocker.Mock(spec=paramiko.SSHClient)
        mockClient.connect.side_effect = Exception("Connection refused")
        mocker.patch("paramiko.SSHClient", return_value=mockClient)

        with pytest.raises(RuntimeError, match="Failed to connect"):
            SSHCommandExecutor(
                hostname="invalid",
                username="admin",
                password="pass",
                venvDir=".venv",
            )

    def test_missing_paramiko(self, mocker) -> None:
        """Test ImportError when paramiko is not installed."""
        mocker.patch.dict("sys.modules", {"paramiko": None})

        with pytest.raises(ImportError, match="paramiko is required"):
            SSHCommandExecutor(
                hostname="robot",
                username="admin",
                password="pass",
                venvDir=".venv",
            )
