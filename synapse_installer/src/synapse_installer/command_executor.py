# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class CommandExecutor(ABC):
    """Abstract base class for executing commands locally or remotely."""

    @abstractmethod
    def execCommand(self, command: str) -> Tuple[str, str, int]:
        """
        Execute a command and return stdout, stderr, and exit code.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (stdout, stderr, exit_code)

        Raises:
            RuntimeError: If command execution fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection (if applicable)."""
        pass

    @staticmethod
    def _normalizePythonCommand(command: str, pythonPath: str) -> str:
        """
        Replace generic python/python3 invocations with specific python path.

        Args:
            command: Original command string
            pythonPath: Path to python executable to use

        Returns:
            Normalized command with python replaced
        """
        # Replace both "python3 " and "python " with the venv python
        result = command.replace("python3 ", f"{pythonPath} ")
        # Only replace "python " if not already replaced
        if "python " in result and pythonPath not in result:
            result = result.replace("python ", f"{pythonPath} ")
        return result


class LocalCommandExecutor(CommandExecutor):
    """Executes commands locally using subprocess with venv Python."""

    def __init__(self, venvDir: Path = Path.cwd() / ".venv") -> None:
        """
        Initialize local executor with virtual environment.

        Args:
            venvDir: Path to virtual environment directory

        Raises:
            RuntimeError: If virtual environment python not found
        """
        self.venvDir: Path = Path(venvDir)
        self.pythonPath: Path = self._getVenvPython(self.venvDir)
        logger.debug(f"LocalCommandExecutor initialized with python: {self.pythonPath}")

    @staticmethod
    def _getVenvPython(venvDir: Path) -> Path:
        """
        Get the path to the venv Python executable for current platform.

        Args:
            venvDir: Path to virtual environment directory

        Returns:
            Path to python executable

        Raises:
            RuntimeError: If python executable not found in venv
        """
        python: Path = (
            venvDir / "Scripts" / "python.exe"
            if os.name == "nt"
            else venvDir / "bin" / "python"
        )
        if not python.exists():
            raise RuntimeError(f"Virtual environment python not found at {python}")
        return python

    def execCommand(self, command: str) -> Tuple[str, str, int]:
        """
        Execute a command locally using venv Python.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        normalizedCommand: str = self._normalizePythonCommand(
            command, str(self.pythonPath)
        )
        logger.debug(f"Executing local command: {normalizedCommand}")

        result: subprocess.CompletedProcess[str] = subprocess.run(
            normalizedCommand,
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(
                f"Command failed with exit code {result.returncode}: {result.stderr}"
            )

        return result.stdout, result.stderr, result.returncode

    def close(self) -> None:
        """No-op for local execution."""
        pass


class SSHCommandExecutor(CommandExecutor):
    """Executes commands remotely via SSH, using venv on remote machine."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        venvDir: str = ".venv",
        timeout: int = 10,
    ) -> None:
        """
        Initialize SSH executor with remote connection.

        Args:
            hostname: Remote host address
            username: SSH username
            password: SSH password
            venvDir: Path to venv on remote machine (default: .venv)
            timeout: Connection timeout in seconds

        Raises:
            ImportError: If paramiko is not installed
            RuntimeError: If SSH connection fails
        """
        try:
            import paramiko
        except ImportError:
            raise ImportError(
                "paramiko is required for SSH execution. Install with: pip install paramiko"
            )

        self.hostname: str = hostname
        self.username: str = username
        self.venvDir: str = venvDir
        self.venvPython: str = f"{venvDir}/bin/python"

        try:
            self.client: paramiko.SSHClient = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname,
                username=username,
                password=password,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=5,
            )
            self.transport: paramiko.Transport | None = self.client.get_transport()
            if self.transport is None:
                raise RuntimeError("Failed to establish SSH transport")
            logger.debug(f"SSHCommandExecutor connected to {hostname}@{username}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {hostname}: {str(e)}")

    def execCommand(self, command: str) -> Tuple[str, str, int]:
        """
        Execute a command via SSH, using venv Python.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (stdout, stderr, exit_code)

        Raises:
            RuntimeError: If SSH command execution fails
        """
        normalizedCommand: str = self._normalizePythonCommand(command, self.venvPython)
        logger.debug(f"Executing SSH command on {self.hostname}: {normalizedCommand}")

        try:
            stdin, stdout, stderr = self.client.exec_command(normalizedCommand)
            exitCode: int = stdout.channel.recv_exit_status()
            stdoutText: str = stdout.read().decode()
            stderrText: str = stderr.read().decode()

            if exitCode != 0:
                logger.warning(
                    f"SSH command failed with exit code {exitCode}: {stderrText}"
                )

            return stdoutText, stderrText, exitCode
        except Exception as e:
            raise RuntimeError(f"SSH command execution failed: {str(e)}")

    def close(self) -> None:
        """Close the SSH connection."""
        try:
            self.client.close()
            logger.debug(f"SSH connection to {self.hostname} closed")
        except Exception as e:
            logger.warning(f"Error closing SSH connection: {str(e)}")
