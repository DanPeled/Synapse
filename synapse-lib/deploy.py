import os
from typing_extensions import Tuple
import paramiko
import tarfile
import subprocess
import pathspec
from datetime import datetime, timedelta


def check_python3_install() -> bool:
    try:
        result = subprocess.run(
            ["python3", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            return True
        else:
            return False
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
        # Remove ignored directories from the walk
        dirs[:] = [
            d for d in dirs if not gitignore_spec.match_file(os.path.join(root, d))
        ]
        for file in files:
            file_path = os.path.join(root, file)
            if (
                ".ruff_cache" in file_path
                or "__pycache__" in file_path
                or file_path.endswith(".pyc")
            ):
                # print(f"Excluded {file_path}")
                ...
            elif not gitignore_spec.match_file(file_path):
                # print(f"Including {file_path}")
                tar.add(
                    file_path, arcname=os.path.relpath(file_path, start=source_folder)
                )
            else:
                # print(f"Excluded {file_path}")
                ...


def compile_file(file_path) -> bool:
    """Compile a single Python file and return the result."""
    try:
        python_cmd = "python3" if check_python3_install() else "python"
        result = subprocess.run(
            [python_cmd, "-m", "py_compile", file_path],
            check=False,  # We will manually check the result
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            print(f"Error compiling {file_path}:")
            print(result.stderr.decode())
            return False

        # print(f"Compiled {file_path} successfully.")
        return True

    except Exception as e:
        print(f"Error compiling {file_path}: {e}")
        return False


def build_project() -> Tuple[bool, timedelta]:
    """Ensure the Python project is built or tested before deployment, file-by-file."""
    print("Building...")
    build_start = datetime.now()
    total_files = 0
    compiled_files = 0

    # First pass: Count all Python files
    for root, _, files in os.walk("."):
        total_files += sum(1 for file in files if file.endswith(".py"))

    if total_files == 0:
        print("No Python files found to compile.")
        return False, timedelta()

    # Second pass: Compile each Python file and track progress
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                print(
                    f"Compiling {file_path}...", end="", flush=True
                )  # Progress on the same line
                if not compile_file(file_path):
                    print(f"Build failed for {file_path}. Exiting.")
                    return False, timedelta()
                compiled_files += 1
                # Update progress on the same line
                print(
                    f"\rProgress: {compiled_files}/{total_files} files compiled.",
                    end="",
                    flush=True,
                )

    print()
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

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    hostname = "192.168.1.158"
    port = 22
    username = "orangepi"
    password = "orangepi"

    current_folder = os.getcwd()

    remote_path = "~/Synapse/"

    # Load the .gitignore patterns
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
