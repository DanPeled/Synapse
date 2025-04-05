import os
import tarfile
import time as t
from datetime import datetime, timedelta
from typing import Tuple

import paramiko
import pathspec


def check_python3_install(ssh) -> bool:
    """Check if Python 3 is installed on the remote system."""
    try:
        stdin, stdout, stderr = ssh.exec_command("python3 --version")
        if stdout.channel.recv_exit_status() == 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error checking Python3 installation: {e}")
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


def compile_file_remotely(ssh, file_path) -> bool:
    """Compile a single Python file on the remote system and return the result."""
    try:
        python_cmd = "python3" if check_python3_install(ssh) else "python"
        remote_compile_cmd = f"{python_cmd} -m py_compile {file_path}"
        stdin, stdout, stderr = ssh.exec_command(remote_compile_cmd)

        if stdout.channel.recv_exit_status() != 0:
            print(f"Error compiling {file_path}:\n{stderr.read().decode()}")
            return False
        return True
    except Exception as e:
        print(f"Error compiling {file_path} remotely: {e}")
        return False


def build_project_remotely(ssh) -> Tuple[bool, timedelta]:
    """Compile Python files on the remote system."""
    print("Building remotely...")
    build_start = datetime.now()
    total_files = 0
    compiled_files = 0

    # Transfer files and count the Python files
    for root, _, files in os.walk("."):
        total_files += sum(1 for file in files if file.endswith(".py"))

    if total_files == 0:
        print("No Python files found to compile.")
        return False, timedelta()

    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                remote_file_path = os.path.join(remote_path, file_path)

                # Copy file to remote server
                sftp = ssh.open_sftp()
                sftp.put(file_path, remote_file_path)
                sftp.close()

                if not compile_file_remotely(ssh, remote_file_path):
                    print(f"Build failed for {file_path} remotely. Exiting.")
                    return False, timedelta()
                compiled_files += 1

    build_end = datetime.now()
    return True, build_end - build_start


def deploy(ssh, tarball_path):
    ssh.exec_command(f"mkdir -p {remote_path}")

    sftp = ssh.open_sftp()
    sftp.put(tarball_path, "/tmp/deploy.tar.gz")
    ssh.exec_command(f"tar -xzf /tmp/deploy.tar.gz -C {remote_path}")
    ssh.exec_command("rm /tmp/deploy.tar.gz")

    service_name = "synapse"

    # Run sudo command and provide the password
    command = f"echo '{password}' | sudo -S systemctl restart {service_name}"
    stdin, stdout, stderr = ssh.exec_command(command)

    # Wait for the command to complete and print any output/errors
    t.sleep(1)
    print(stdout.read().decode())
    print(stderr.read().decode())

    print(f"Service {service_name} restarted.")

    sftp.close()


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

    # Establish SSH connection to the remote server
    print(f"Connecting via SSH to {username}@{hostname}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)

    # Build project remotely
    build_OK, time = build_project_remotely(ssh)
    if build_OK:
        print(f"Built remotely in {time.total_seconds()} seconds")
        deploy(ssh, tarball_path)
        print(f"Deployment to {username}@{hostname}:{remote_path} complete.")

    ssh.close()
