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

    remote_main: str = f"/home/{username}/main.py"
    sftp.chmod(remote_main, 0o755)

    service_content: str = f"""[Unit]
Description=Start Synapse Runtime 
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/{username}/main.py
WorkingDirectory=/home/{username}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

    remote_service_tmp: str = f"/home/{username}/{SERVICE_NAME}.service"
    with open("/tmp/temp.service", "w") as f:
        f.write(service_content)
    sftp.put("/tmp/temp.service", remote_service_tmp)

    def run_sudo(cmd: str) -> Tuple[str, str]:
        stdin, stdout, stderr = client.exec_command(f"sudo -S bash -c '{cmd}'")
        # Note: If sudo asks for password, you'd handle stdin here.
        out: str = stdout.read().decode()
        err: str = stderr.read().decode()
        print(out)
        if err:
            print("Error:", err)
        return out, err

    print("Moving service file to system directory and enabling service...")
    run_sudo(f"mv {remote_service_tmp} /etc/systemd/system/{SERVICE_NAME}.service")
    run_sudo("systemctl daemon-reexec")
    run_sudo("systemctl daemon-reload")
    run_sudo(f"systemctl enable {SERVICE_NAME}")
    run_sudo(f"systemctl start {SERVICE_NAME}")

    sftp.close()
    os.remove("/tmp/temp.service")
    print("Service installed and started.")
