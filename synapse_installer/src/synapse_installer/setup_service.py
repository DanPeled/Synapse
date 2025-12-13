# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Tuple

from paramiko import SSHClient

SERVICE_NAME = "synapse-runtime"


def isServiceSetup(client: SSHClient, serviceName: str) -> bool:
    """Check if the systemd service file exists on the remote machine."""
    cmd = f"test -f /etc/systemd/system/{serviceName}.service && echo exists || echo missing"
    stdin, stdout, stderr = client.exec_command(cmd)
    result = stdout.read().decode().strip()
    return result == "exists"


def runCommand(
    client: SSHClient, cmd: str, ignoreErrors: bool = False
) -> Tuple[str, str]:
    """Run a command on the remote client and return (stdout, stderr)."""
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err and not ignoreErrors and "Created symlink" not in err:
        print(f"Error: {err.strip()}")
    return out, err


def restartService(client: SSHClient, serviceName: str) -> Tuple[str, str]:
    """Restart the given systemd service on the remote machine."""
    return runCommand(client, f"sudo systemctl restart {serviceName}")


def setupServiceOnConnectedClient(client: SSHClient, username: str) -> None:
    """
    Sets up the systemd service for Synapse Runtime on the remote machine.
    Uses Python 3.10 explicitly.
    """
    pythonPath = "/usr/local/bin/python3.10"

    # Get home directory
    stdin, stdout, stderr = client.exec_command("echo $HOME")
    homeDir = stdout.read().decode().strip()

    workingDir = Path(homeDir) / "Synapse"
    mainPath = workingDir / "main.py"

    serviceContent = f"""[Unit]
Description=Start Synapse Runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={pythonPath} {mainPath.as_posix()} --server
WorkingDirectory={workingDir.as_posix()}
Restart=always
RestartSec=5
User={username}

[Install]
WantedBy=multi-user.target
"""

    # Write the systemd service file using heredoc
    heredocCmd = f"sudo tee /etc/systemd/system/{SERVICE_NAME}.service > /dev/null << 'EOF'\n{serviceContent}\nEOF"

    print(f"Making {mainPath.as_posix()} executable...")
    runCommand(client, f"chmod +x {mainPath.as_posix()}")

    print("Creating systemd service file remotely...")
    runCommand(client, heredocCmd)

    print("Reloading systemd daemon...")
    runCommand(client, "sudo systemctl daemon-reload")

    print(f"Enabling {SERVICE_NAME} service...")
    runCommand(client, f"sudo systemctl enable {SERVICE_NAME}")

    print(f"Starting {SERVICE_NAME} service...")
    runCommand(client, f"sudo systemctl start {SERVICE_NAME}")

    print("Synapse Runtime Service installed and started successfully.")
