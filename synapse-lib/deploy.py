import os
from typing import Tuple
import paramiko
import tarfile
import subprocess
import pathspec
from datetime import datetime, timedelta
import synapse.nt_client


def check_python3_install() -> bool:
    try:
        result = subprocess.run(
            ["python3", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_gitignore_specs() -> pathspec.PathSpec:
    """Load the .gitignore file to filter out ignored files."""
    gitignore_path = os.path.join(os.getcwd(), ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
            return spec
    return pathspec.PathSpec([])


def add_files_to_tar(tar, source_folder, gitignore_spec):
    """Add files to tarball, excluding gitignored files."""
    for root, dirs, files in os.walk(source_folder):
        dirs[:] = [
            d for d in dirs if not gitignore_spec.match_file(os.path.join(root, d))
        ]
        for file in files:
            file_path = os.path.join(root, file)
            if not gitignore_spec.match_file(file_path):
                tar.add(
                    file_path, arcname=os.path.relpath(file_path, start=source_folder)
                )


def compile_file(file_path) -> bool:
    """Compile a single Python file and return the result."""
    try:
        python_cmd = "python3" if check_python3_install() else "python"
        result = subprocess.run(
            [python_cmd, "-m", "py_compile", file_path],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            print(f"Error compiling {file_path}:\n{result.stderr.decode()}")
            return False
        return True
    except Exception as e:
        print(f"Error compiling {file_path}: {e}")
        return False


def build_project() -> Tuple[bool, timedelta]:
    """Compile Python files in the project."""
    print("Building...")
    build_start = datetime.now()
    total_files = 0
    compiled_files = 0

    for root, _, files in os.walk("."):
        total_files += sum(1 for file in files if file.endswith(".py"))

    if total_files == 0:
        print("No Python files found to compile.")
        return False, timedelta()

    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if not compile_file(file_path):
                    print(f"Build failed for {file_path}. Exiting.")
                    return False, timedelta()
                compiled_files += 1

    build_end = datetime.now()
    return True, build_end - build_start


def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(hostname, port, username, password)
    ssh.exec_command(f"mkdir -p {remote_path}")

    sftp = ssh.open_sftp()
    sftp.put(tarball_path, "/tmp/deploy.tar.gz")
    ssh.exec_command(f"tar -xzf /tmp/deploy.tar.gz -C {remote_path}")
    ssh.exec_command("rm /tmp/deploy.tar.gz")

    client = synapse.nt_client.NtClient()
    client.setup(9738, "deploySynapse", False)
    if client.getPID() != -1:
        ssh.exec_command(f"kill {client.getPID()}")
        ssh.exec_command("cd ~/Synapse && python3 main.py")
    service_name = "synapse_runtime"
    service_path = f"/etc/systemd/system/{service_name}.service"

    # Service definition
    service_content = f"""
    [Unit]
    Description=Synapse Runtime
    After=network.target

    [Service]
    ExecStart=/usr/bin/python3 {remote_path}main.py
    Restart=always
    User={username}
    WorkingDirectory={remote_path}

    [Install]
    WantedBy=multi-user.target
    """

    stdin, stdout, stderr = ssh.exec_command(f"test -f {service_path} && echo exists")
    service_exists = "exists" in stdout.read().decode()

    if not service_exists:
        temp_service_path = f"/tmp/{service_name}.service"

        # Write service content to a temporary location
        with ssh.open_sftp().file(temp_service_path, "w") as service_file:
            service_file.write(service_content)

        # Move the service file to /etc/systemd/system using sudo
        ssh.exec_command(f"sudo mv {temp_service_path} {service_path}")
        ssh.exec_command("sudo systemctl daemon-reload")
        ssh.exec_command(f"sudo systemctl enable {service_name}")

    ssh.exec_command(f"systemctl restart {service_name}")
    print(f"Service {service_name} restarted.")

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    hostname = "10.97.38.14"
    port = 22
    username = "orangepi"
    password = "orangepi"

    current_folder = os.getcwd()
    remote_path = "~/Synapse/"
    gitignore_spec = get_gitignore_specs()
    tarball_path = "/tmp/deploy.tar.gz"

    with tarfile.open(tarball_path, "w:gz") as tar:
        add_files_to_tar(tar, current_folder, gitignore_spec)

    build_OK, time = build_project()
    if build_OK:
        print(f"Built successfully in {time.total_seconds()} seconds")
        print(f"Connecting via SSH to {username}@{hostname}...")
        deploy()
        print(f"Deployment to {username}@{hostname}:{remote_path} complete.")
