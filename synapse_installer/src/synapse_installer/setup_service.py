import tempfile
from typing import Tuple

from paramiko import SFTPClient, SSHClient

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
    import os

    sftp: SFTPClient = client.open_sftp()

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
        # Fallback to /usr/bin/python3
        python_path = "/usr/bin/python3"

    remote_main: str = f"/home/{username}/main.py"
    sftp.chmod(remote_main, 0o755)

    service_content: str = f"""[Unit]
Description=Start Synapse Runtime 
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={python_path} /home/{username}/main.py
WorkingDirectory=/home/{username}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

    remote_service_tmp: str = f"/home/{username}/{SERVICE_NAME}.service"
    with tempfile.NamedTemporaryFile("w", delete=False) as temp_file:
        temp_file.write(service_content)
        temp_file_path = temp_file.name

    sftp.put(temp_file_path, remote_service_tmp)

    def run_sudo(cmd: str) -> Tuple[str, str]:
        stdin, stdout, stderr = client.exec_command(f"sudo -S bash -c '{cmd}'")
        out: str = stdout.read().decode()
        err: str = stderr.read().decode()
        print(out)
        if err:
            print("Error:", err)
        return out, err

    print(
        "Moving synapse runtime service file to system directory and enabling service..."
    )
    run_sudo(f"mv {remote_service_tmp} /etc/systemd/system/{SERVICE_NAME}.service")
    run_sudo("systemctl daemon-reexec")
    run_sudo("systemctl daemon-reload")
    run_sudo(f"systemctl enable {SERVICE_NAME}")
    run_sudo(f"systemctl start {SERVICE_NAME}")

    sftp.close()
    os.remove(temp_file_path)
    print("Synapse Runtime Service installed and started.")
