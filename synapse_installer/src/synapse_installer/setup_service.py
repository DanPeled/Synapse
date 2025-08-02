# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Tuple

from paramiko import SSHClient

SERVICE_NAME = "synapse-runtime"

FIND_PYTHON_CMD = r"""
LOW="3.9.0"
HIGH="3.12.0"

verGe() {
  # Returns true if $1 >= $2
  [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$2" ]
}

verInRange() {
  local ver=$1
  verGe "$ver" "$LOW" && verGe "$HIGH" "$ver"
}

highestVersion=""
highestPath=""

mapfile -t pythonExecs < <(compgen -c python | sort -u)

for py in "${pythonExecs[@]}"; do
  path=$(command -v "$py" 2>/dev/null)
  if [[ -x "$path" ]]; then
    version=$("$path" --version 2>&1 | awk '{print $2}')
    if [[ -n $version ]] && verInRange "$version"; then
      if [[ -z "$highestVersion" ]] || verGe "$version" "$highestVersion"; then
        highestVersion=$version
        highestPath=$path
      fi
    fi
  fi
done

echo "$highestPath"
"""


def isServiceSetup(client: SSHClient, serviceName: str) -> bool:
    """
    Check if the systemd service file exists on the remote machine.
    """
    cmd = f"test -f /etc/systemd/system/{serviceName}.service && echo exists || echo missing"
    stdin, stdout, stderr = client.exec_command(cmd)
    result = stdout.read().decode().strip()
    return result == "exists"


def restartService(client: SSHClient, serviceName: str) -> Tuple[str, str]:
    """
    Restart the given systemd service on the remote machine.
    Returns (stdout, stderr).
    """
    stdin, stdout, stderr = client.exec_command(f"sudo systemctl restart {serviceName}")
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err


def runCommand(
    client: SSHClient, cmd: str, ignoreErrors: bool = False
) -> Tuple[str, str]:
    """
    Run a command on the remote client and return (stdout, stderr).
    Prints errors unless ignoreErrors=True.
    """
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err and not ignoreErrors and "Created symlink" not in err:
        print(f"Error: {err.strip()}")
    return out, err


def setupServiceOnConnectedClient(client: SSHClient, username: str) -> None:
    """
    Sets up the systemd service for Synapse Runtime on the remote machine.
    """
    # Find best Python executable path
    stdin, stdout, stderr = client.exec_command(FIND_PYTHON_CMD)
    pythonPath = stdout.read().decode().strip()
    err = stderr.read().decode()
    if err:
        print("Error finding python:", err)
    if not pythonPath:
        pythonPath = "/usr/bin/python3"

    # Get home directory and setup paths
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
ExecStart={pythonPath} {mainPath.as_posix()}
WorkingDirectory={workingDir.as_posix()}
Restart=always
RestartSec=5
User={username}

[Install]
WantedBy=multi-user.target
"""

    heredocCmd = f"sudo tee /etc/systemd/system/{SERVICE_NAME}.service > /dev/null << 'EOF'\n{serviceContent}\nEOF\n"

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
