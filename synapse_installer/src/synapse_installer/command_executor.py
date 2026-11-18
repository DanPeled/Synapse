# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from paramiko import SSHClient

from .ssh import connectSSH

logger = logging.getLogger(__name__)


class RemoteCommandError(RuntimeError):
    """Raised when a remote command exits with a non-zero status."""


class CommandExecutor(ABC):
    """Abstract base class for executing commands locally or remotely."""

    @abstractmethod
    def execCommand(
        self, command: str, stdinData: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """Execute a command and return stdout, stderr, and exit code."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection (if applicable)."""
        pass


class LocalCommandExecutor(CommandExecutor):
    """Executes commands locally using system Python."""

    def execCommand(
        self, command: str, stdinData: Optional[str] = None
    ) -> Tuple[str, str, int]:
        logger.debug(f"Executing local command: {command}")

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdinData is not None else None,
            text=True,
        )

        if stdinData is not None:
            stdout, stderr = process.communicate(stdinData)
            print(stdout, end="")
            print(stderr, end="")
            return stdout, stderr, process.returncode

        stdout_lines, stderr_lines = [], []

        # Print stdout/stderr live
        while True:
            out_line = process.stdout.readline() if process.stdout else ""
            err_line = process.stderr.readline() if process.stderr else ""

            if out_line:
                print(out_line, end="")
                stdout_lines.append(out_line)
            if err_line:
                print(err_line, end="")
                stderr_lines.append(err_line)

            if out_line == "" and err_line == "" and process.poll() is not None:
                break

        return "".join(stdout_lines), "".join(stderr_lines), process.returncode

    def close(self) -> None:
        """No-op for local execution."""
        pass


class SSHCommandExecutor(CommandExecutor):
    """Executes commands remotely via SSH using system Python."""

    def __init__(
        self, hostname: str, username: str, password: str, timeout: int = 10
    ) -> None:
        try:
            import paramiko  # noqa: F401
        except ImportError:
            raise ImportError("paramiko is required: pip install paramiko")

        self.hostname = hostname
        self.username = username
        self.client = connectSSH(hostname, username, password, timeout=timeout)
        logger.debug(f"SSH connected to {hostname}@{username}")

    def execCommand(
        self, command: str, stdinData: Optional[str] = None
    ) -> Tuple[str, str, int]:
        logger.debug(f"Executing SSH command on {self.hostname}: {command}")

        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            if stdinData is not None:
                stdin.write(stdinData)
                stdin.flush()
                stdin.channel.shutdown_write()

            stdout_lines, stderr_lines = [], []

            # Print stdout/stderr live
            while not stdout.channel.exit_status_ready():
                if stdout.channel.recv_ready():
                    out_data = stdout.channel.recv(1024).decode()
                    print(out_data, end="")
                    stdout_lines.append(out_data)
                if stderr.channel.recv_stderr_ready():
                    err_data = stderr.channel.recv_stderr(1024).decode()
                    print(err_data, end="")
                    stderr_lines.append(err_data)

            # Read remaining data
            out_data = stdout.read().decode()
            err_data = stderr.read().decode()
            if out_data:
                print(out_data, end="")
                stdout_lines.append(out_data)
            if err_data:
                print(err_data, end="")
                stderr_lines.append(err_data)

            exit_code = stdout.channel.recv_exit_status()
            return "".join(stdout_lines), "".join(stderr_lines), exit_code

        except Exception as e:
            raise RuntimeError(f"SSH command execution failed: {e}")

    def close(self) -> None:
        try:
            self.client.close()
            logger.debug(f"SSH connection to {self.hostname} closed")
        except Exception as e:
            logger.warning(f"Error closing SSH connection: {e}")


def runCommand(
    client: SSHClient,
    cmd: str,
    ignoreErrors: bool = False,
    check: bool = False,
) -> Tuple[str, str, int]:
    """Run a command on the remote client and return (stdout, stderr, exit code)."""
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    exitCode = stdout.channel.recv_exit_status()

    if exitCode != 0 and not ignoreErrors:
        message = err.strip() or out.strip() or f"exit code {exitCode}"
        print(f"Error: {message}")
        if check:
            raise RemoteCommandError(message)

    return out, err, exitCode
