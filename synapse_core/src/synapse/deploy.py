import os
import subprocess
import tarfile
import time as t
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import paramiko
import pathspec
from synapse.core import config as synconfig


def check_python3_install() -> bool:
    try:
        result = subprocess.run(
            ["python3", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_gitignore_specs(base_path: Path) -> pathspec.PathSpec:
    gitignore_path = os.path.join(base_path, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    return pathspec.PathSpec([])


def add_files_to_tar(
    tar, source_folder: Path, gitignore_spec: pathspec.PathSpec
) -> None:
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


def compile_file(file_path: str) -> bool:
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


def build_project(base_path: Path) -> Tuple[bool, timedelta]:
    print("Building...")
    build_start = datetime.now()
    total_files = 0
    compiled_files = 0

    for root, _, files in os.walk(base_path):
        total_files += sum(1 for file in files if file.endswith(".py"))

    if total_files == 0:
        print("No Python files found to compile.")
        return False, timedelta()

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if not compile_file(file_path):
                    print(f"Build failed for {file_path}. Exiting.")
                    return False, timedelta()
                compiled_files += 1

    build_end = datetime.now()
    return True, build_end - build_start


def deploy(
    tarball_path: str,
    remote_path: str,
    hostname: str,
    port: int,
    username: str,
    password: str,
    service_name: str = "synapse",
) -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(hostname, port, username, password)
    ssh.exec_command(f"mkdir -p {remote_path}")

    sftp = ssh.open_sftp()
    sftp.put(tarball_path, "/tmp/deploy.tar.gz")

    ssh.exec_command(
        f"find {remote_path} -mindepth 1 -not -name 'settings.yml' -exec rm -rf {{}} +"
    )
    ssh.exec_command(f"tar -xzf /tmp/deploy.tar.gz -C {remote_path}")
    ssh.exec_command("rm /tmp/deploy.tar.gz")

    command = f"echo '{password}' | sudo -S systemctl restart {service_name}"
    stdin, stdout, stderr = ssh.exec_command(command)

    t.sleep(1)
    print(stdout.read().decode())
    print(stderr.read().decode())

    print(f"Service {service_name} restarted.")

    sftp.close()
    ssh.close()


def load_config(base_path: Path) -> dict:
    config = synconfig.Config()
    config.load(Path(base_path) / "config" / ".synapseproject")
    return config.getConfigMap()


def main():
    base_path = Path(os.getcwd())
    tarball_path = "/tmp/deploy.tar.gz"
    remote_path = "~/Synapse/"

    gitignore_spec = get_gitignore_specs(base_path)
    network_config = load_config(base_path)

    hostname = network_config["hostname"]
    port = 22
    username = network_config["user"]
    password = network_config["password"]

    with tarfile.open(tarball_path, "w:gz") as tar:
        add_files_to_tar(tar, base_path, gitignore_spec)

    build_ok, build_time = build_project(base_path)
    if build_ok:
        print(f"Built successfully in {build_time.total_seconds()} seconds")
        print(f"Connecting via SSH to {username}@{hostname}...")
        deploy(tarball_path, remote_path, hostname, port, username, password)
        print(f"Deployment to {username}@{hostname}:{remote_path} complete.")


if __name__ == "__main__":
    main()
