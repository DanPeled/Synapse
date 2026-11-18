# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import time
from pathlib import Path
from typing import Tuple

from paramiko import SSHClient

from .command_executor import RemoteCommandError, runCommand

SERVICE_NAME = "synapse-runtime"

SUDO_HINT = (
    "Passwordless sudo is not configured on the device. "
    "Run `python -m synapse_installer sync <device>` first."
)


class ServiceError(RuntimeError):
    """Raised when the remote Synapse service cannot be managed."""


def _quote(value: str) -> str:
    return shlex.quote(value)


def _run(
    client: SSHClient,
    command: str,
    description: str,
    *,
    useSudo: bool = False,
    check: bool = True,
) -> Tuple[str, str, int]:
    if useSudo:
        command = f"sudo -n {command}"

    try:
        stdout, stderr, exitCode = runCommand(
            client, command, ignoreErrors=not check, check=check
        )
    except RemoteCommandError as error:
        raise ServiceError(f"{description} failed: {error}\n{SUDO_HINT}") from error

    if check and exitCode != 0:
        message = stderr.strip() or stdout.strip() or f"exit code {exitCode}"
        raise ServiceError(f"{description} failed: {message}\n{SUDO_HINT}")

    return stdout, stderr, exitCode


def isServiceSetup(client: SSHClient, serviceName: str = SERVICE_NAME) -> bool:
    """Check if the systemd service file exists on the remote machine."""
    command = f"test -f {_quote(f'/etc/systemd/system/{serviceName}.service')}"
    _, _, exitCode = runCommand(client, command, ignoreErrors=True)
    return exitCode == 0


def isServiceActive(client: SSHClient, serviceName: str = SERVICE_NAME) -> bool:
    """Return whether the remote systemd service is currently running."""
    command = f"systemctl is-active --quiet {_quote(serviceName)}"
    _, _, exitCode = _run(
        client,
        command,
        f"Check {serviceName} status",
        useSudo=True,
        check=False,
    )
    return exitCode == 0


def restartService(
    client: SSHClient, serviceName: str = SERVICE_NAME
) -> Tuple[str, str]:
    """Restart the given systemd service on the remote machine."""
    stdout, stderr, _ = _run(
        client,
        f"systemctl restart {_quote(serviceName)}",
        f"Restart {serviceName}",
        useSudo=True,
    )
    return stdout, stderr


def startService(client: SSHClient, serviceName: str = SERVICE_NAME) -> None:
    """Start the given systemd service on the remote machine."""
    _run(
        client,
        f"systemctl start {_quote(serviceName)}",
        f"Start {serviceName}",
        useSudo=True,
    )


def stopService(client: SSHClient, serviceName: str = SERVICE_NAME) -> bool:
    """Stop the given systemd service if it is running.

    Returns True when the service was running and is now stopped.
    """
    if not isServiceActive(client, serviceName):
        return False

    _run(
        client,
        f"systemctl stop {_quote(serviceName)}",
        f"Stop {serviceName}",
        useSudo=True,
    )
    return True


def waitForServiceActive(
    client: SSHClient,
    serviceName: str = SERVICE_NAME,
    timeout: float = 20.0,
    interval: float = 0.5,
) -> None:
    """Wait until systemd reports the service as active."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if isServiceActive(client, serviceName):
            return
        time.sleep(interval)

    raise ServiceError(
        f"{serviceName} did not become active within {timeout:.0f}s. "
        f"Check the logs with `journalctl -u {serviceName}` on the device."
    )


def setupServiceOnConnectedClient(
    client: SSHClient, username: str, start: bool = True
) -> None:
    """Install the systemd service for Synapse Runtime on the remote machine."""

    stdout, _, _ = _run(client, 'printf %s "$HOME"', "Resolve home directory")
    homeDir = stdout.strip()
    if not homeDir or "\n" in homeDir:
        raise ServiceError("Could not determine the remote home directory.")

    workingDir = Path(homeDir) / "Synapse"
    pythonPath = workingDir.parent / ".venv" / "bin" / "python"
    mainPath = workingDir / "main.py"

    if "\n" in username:
        raise ServiceError("Invalid username in the device configuration.")

    serviceContent = f"""[Unit]
Description=Start Synapse Runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={pythonPath.as_posix()} {mainPath.as_posix()}
WorkingDirectory={workingDir.as_posix()}
Restart=always
RestartSec=5
User={username}

[Install]
WantedBy=multi-user.target
"""

    servicePath = f"/etc/systemd/system/{SERVICE_NAME}.service"
    heredoc = f"tee {_quote(servicePath)} > /dev/null << 'EOF'\n{serviceContent}\nEOF"

    print("Creating systemd service file remotely...")
    _run(client, heredoc, "Write the systemd service file", useSudo=True)

    print("Reloading systemd daemon...")
    _run(client, "systemctl daemon-reload", "Reload systemd", useSudo=True)

    print(f"Enabling {SERVICE_NAME} service...")
    _run(
        client,
        f"systemctl enable {_quote(SERVICE_NAME)}",
        "Enable service",
        useSudo=True,
    )

    if start:
        print(f"Starting {SERVICE_NAME} service...")
        startService(client)

    print("Synapse Runtime service installed successfully.")
