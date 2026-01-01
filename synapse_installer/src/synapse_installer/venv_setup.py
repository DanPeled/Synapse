# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from paramiko import SSHClient

from .command_executor import CommandExecutor


def runAndGetWithSSH(cmd: str, client: SSHClient) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if err and "command not found" not in err:
        raise RuntimeError(err)
    return out


def runAndGetWithExecutor(cmd: str, executor: CommandExecutor) -> str:
    """
    Run a command using the given CommandExecutor and return stdout.
    Raises RuntimeError if exit code != 0 and error is not "command not found".
    """
    stdout, stderr, exitCode = executor.execCommand(cmd)
    if exitCode != 0 and "command not found" not in stderr:
        raise RuntimeError(stderr)
    return stdout.strip()


def ensureVenvAutoPython(client: SSHClient) -> Path:
    """
    Ensure a Python 3.12 venv exists at <workingDir>/.venv.
    Auto-detects a Python 3.12+ interpreter if needed.
    Returns the absolute path to the venv's python executable.
    """

    stdin, stdout, stderr = client.exec_command("echo $HOME")
    homeDir = stdout.read().decode().strip()

    workingDir = Path(homeDir) / "Synapse"

    venvDir = workingDir / ".venv"
    pythonExec = venvDir / "bin" / "python"

    # 1) Check if venv exists and is valid
    try:
        out = runAndGetWithSSH(
            f"""
            if [ -x "{pythonExec.as_posix()}" ]; then
                "{pythonExec.as_posix()}" -c "import sys; print(sys.executable)"
            fi
            """,
            client,
        )
        if out:
            return Path(out)
    except RuntimeError:
        pass

    # 2) Find Python 3.12+ automatically
    candidates = ["python3.12", "python3.13", "python3"]
    pythonCmd = None
    for cmd in candidates:
        try:
            version = runAndGetWithSSH(
                f"{cmd} -c 'import sys; print(sys.version_info[:3])'", client
            )
            major, minor, _ = eval(version)
            if major == 3 and minor >= 12:
                pythonCmd = cmd
                break
        except Exception:
            continue

    if not pythonCmd:
        raise RuntimeError("No Python 3.12+ found on remote system")

    # 3) Create venv
    print(f"Creating venv with {pythonCmd}...")
    runAndGetWithSSH(f"cd {workingDir.as_posix()} && {pythonCmd} -m venv .venv", client)

    # 4) Upgrade pip
    runAndGetWithSSH(f"{pythonExec.as_posix()} -m pip install --upgrade pip", client)

    # 5) Final verification
    out = runAndGetWithSSH(
        f'{pythonExec.as_posix()} -c "import sys; print(sys.executable)"', client
    )
    return Path(out)
