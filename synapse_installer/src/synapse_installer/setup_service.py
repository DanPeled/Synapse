# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Tuple

from paramiko import SSHClient

SERVICE_NAME: str = "synapseruntime"


def isServiceSetup(client: SSHClient, service_name: str) -> bool:
    """
    Check if the systemd service file exists on the remote machine.
    """
    cmd = f"test -f /etc/systemd/system/{service_name}.service && echo exists || echo missing"
    stdin, stdout, stderr = client.exec_command(cmd)
    result = stdout.read().decode().strip()
    return result == "exists"


def restartService(client: SSHClient, service_name: str) -> Tuple[str, str]:
    """
    Restart the given systemd service on the remote machine.
    Returns (stdout, stderr).
    """
    stdin, stdout, stderr = client.exec_command(
        f"sudo systemctl restart {service_name}"
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err


def setupServiceOnConnectedClient(
    client: SSHClient,
    username: str,
) -> None:
    SERVICE_NAME = "synapse-runtime"  # or whatever your service name is

    find_python_cmd = r"""
    LOW="3.9.0"
    HIGH="3.12.0"
    ver_ge() {
        [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$2" ]
    }
    ver_in_range() {
        local ver=$1
        ver_ge "$ver" "$LOW" && ver_ge "$HIGH" "$ver"
    }
    highest_version=""
    highest_path=""
    mapfile -t python_execs < <(compgen -c python | sort -u)
    for py in "${python_execs[@]}"; do
        path=$(command -v "$py" 2>/dev/null)
        if [[ -x "$path" ]]; then
            version=$("$path" --version 2>&1 | awk '{print $2}')
            if [[ -n $version ]] && ver_in_range "$version"; then
                if [[ -z "$highest_version" ]] || ver_ge "$version" "$highest_version"; then
                    highest_version=$version
                    highest_path=$path
                fi
            fi
        fi
    done
    echo "$highest_path"
    """

    stdin, stdout, stderr = client.exec_command(find_python_cmd)
    python_path = stdout.read().decode().strip()
    err = stderr.read().decode()
    if err:
        print("Error finding python:", err)

    if not python_path:
        python_path = "/usr/bin/python3"

    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    stdin, stdout, stderr = client.exec_command("echo $HOME")
    home_dir = stdout.read().decode().strip()
    working_dir = f"{home_dir}/Synapse"
    main_path = f"{working_dir}/main.py"

    service_content = f"""[Unit]
Description=Start Synapse Runtime 
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={python_path} {main_path}
WorkingDirectory={working_dir}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

    heredoc = f"sudo tee {service_path} > /dev/null << 'EOF'\n{service_content}\nEOF\n"

    def run_command(cmd: str) -> Tuple[str, str]:
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if err and "Created symlink" not in err:
            print("Error:", err)
        return out, err

    # Make sure main.py is executable
    run_command(f"chmod +x {main_path}")

    # Create the service file remotely
    print("Creating systemd service file remotely...")
    run_command(heredoc)

    # Enable and start the service
    print("Enabling and starting the service...")
    run_command("sudo systemctl daemon-reexec")
    run_command("sudo systemctl daemon-reload")
    run_command(f"sudo systemctl enable {SERVICE_NAME}")
    run_command(f"sudo systemctl start {SERVICE_NAME}")

    print("Synapse Runtime Service installed and started.")
