# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Deploy a Synapse project to one or more coprocessors.

The deploy path is deliberately conservative:

* SSH host keys are verified before anything is uploaded.
* Archives are validated before connecting, so a broken build cannot leave a
  device half-updated.
* Files are extracted into a staging directory and swapped into place, with the
  previous deployment kept as a backup.
* The running service is stopped before the swap and started again afterwards.
* If anything fails, the previous deployment is restored and the command exits
  non-zero.
"""

import os
import pathlib as pthl
import shlex
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import questionary
import yaml
from paramiko import SSHClient
from rich import print as fprint
from scp import SCPClient
from synapse.bcolors import MarkupColors
from synapse_net.stdout_streamer import SystemdServiceLogStreamer

from .discover import discoverDevices
from .lockfile import createDirectoryZIP, createPackageZIP
from .setup_service import (
    SERVICE_NAME,
    setupServiceOnConnectedClient,
    startService,
    stopService,
    waitForServiceActive,
)
from .ssh import HostKeyError, connectSSH
from .util import (
    NOT_IN_SYNAPSE_PROJECT_ERR,
    SYNAPSE_PROJECT_FILE,
    DeployDeviceConfig,
    IsValidIP,
)

BUILD_DIR = "build"
REMOTE_APP_DIR = "Synapse"
STAGING_PREFIX = ".synapse-staging-"
BACKUP_PREFIX = ".synapse-backup-"


class DeploymentError(RuntimeError):
    """Raised when a deployment cannot be completed safely."""


class SetupOptions(Enum):
    kManual = "Manual (Provide hostname & password)"
    kAutomatic = "Automatic (Find available devices)"


@dataclass
class DeployOptions:
    """Options parsed from the `deploy`/`install` command line."""

    devices: List[str] = field(default_factory=list)
    assumeYes: bool = False
    dryRun: bool = False
    followLogs: bool = True


def parseDeployArgs(argv: Optional[List[str]]) -> DeployOptions:
    """Parse deploy flags and device names."""
    options = DeployOptions()

    for arg in argv or []:
        if arg in ("-y", "--yes"):
            options.assumeYes = True
        elif arg in ("-n", "--dry-run"):
            options.dryRun = True
        elif arg == "--no-logs":
            options.followLogs = False
        elif arg.startswith("-"):
            raise DeploymentError(f"Unknown option `{arg}`. Use `--help` for usage.")
        else:
            options.devices.append(arg)

    return options


def _info(message: str) -> None:
    fprint(f"[cyan]{message}[/cyan]")


def _success(message: str) -> None:
    fprint(MarkupColors.okgreen(message))


def _warn(message: str) -> None:
    fprint(MarkupColors.warning(message))


def _fail(message: str) -> None:
    fprint(MarkupColors.fail(message))


def _quote(value: str) -> str:
    return shlex.quote(value)


def _warnIfConfigPermissionsAreOpen(path: pthl.Path) -> None:
    if os.name != "posix":
        return

    try:
        mode = path.stat().st_mode
    except OSError:
        return

    if mode & 0o077:
        _warn(
            f"{path} stores device passwords and is readable by other users. "
            f"Run `chmod 600 {path}` to restrict access."
        )


def _writeConfig(path: pthl.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as file:
            yaml.dump(data, file, sort_keys=False)
        os.chmod(path, 0o600)
    except OSError as error:
        raise DeploymentError(f"Could not write {path}: {error}") from error


def _promptHostname() -> Optional[str]:
    while True:
        hostname = questionary.text("Device SSH username or hostname?").ask()
        if hostname is None:
            return None
        hostname = hostname.strip()
        if hostname and not any(character.isspace() for character in hostname):
            return hostname
        _warn("Please enter a non-empty hostname without spaces.")


def _promptNickname(hostname: str, existing: Dict[str, object]) -> Optional[str]:
    default = hostname

    while True:
        nickname = questionary.text(
            f"Device nickname (leave blank for `{default}`)", default=default
        ).ask()
        if nickname is None:
            return None
        nickname = nickname.strip() or default
        if nickname not in existing:
            return nickname
        _warn(f"Device with nickname `{nickname}` already exists. Pick another.")


def _promptIP() -> Optional[str]:
    while True:
        ip = questionary.text("Device IP address?").ask()
        if ip is None:
            return None
        ip = ip.strip()
        if IsValidIP(ip):
            return ip
        _warn("Invalid IP address. Please enter a valid IPv4 or IPv6 address.")


def _addManualDevice(baseFile: dict) -> None:
    hostname = _promptHostname()
    if hostname is None:
        return

    deploys = baseFile.setdefault("deploy", {})
    nickname = _promptNickname(hostname, deploys)
    if nickname is None:
        return

    ip = _promptIP()
    if ip is None:
        return

    password = questionary.password(f"Password for {hostname}@{ip}?").ask()
    if password is None:
        return

    deploys[nickname] = DeployDeviceConfig(
        hostname=hostname, ip=ip, password=password
    ).__dict__


def _addDiscoveredDevices(baseFile: dict) -> None:
    _info("Searching for Synapse devices on the network...")
    discovered = discoverDevices()
    if not discovered:
        _warn(
            "No devices found. Make sure the Synapse runtime is running on the "
            "device, then try again."
        )
        return

    deploys = baseFile.setdefault("deploy", {})
    for device in discovered:
        nickname = device.nickname
        if nickname in deploys:
            _warn(f"Skipping `{nickname}`: it is already configured.")
            continue

        _info(f"Found {nickname} at {device.ip} (user: {device.username})")
        if not questionary.confirm(f"Add `{nickname}`?", default=True).ask():
            continue

        password = questionary.password(
            f"Password for {device.username}@{device.ip}?"
        ).ask()
        if password is None:
            continue

        deploys[nickname] = DeployDeviceConfig(
            hostname=device.username or device.hostname,
            ip=device.ip,
            password=password,
        ).__dict__


def addDeviceConfig(path: pthl.Path) -> None:
    """Add one or more devices to the project's deploy configuration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    baseFile: dict = {}
    if path.exists():
        with open(path, "r") as file:
            loaded = yaml.full_load(file) or {}
        if isinstance(loaded, dict):
            baseFile = loaded

    answer = questionary.select(
        "How would you like to add the device?",
        choices=[
            SetupOptions.kManual.value,
            SetupOptions.kAutomatic.value,
        ],
    ).ask()

    if answer == SetupOptions.kManual.value:
        _addManualDevice(baseFile)
    elif answer == SetupOptions.kAutomatic.value:
        _addDiscoveredDevices(baseFile)

    _writeConfig(path, baseFile)


def _runRemote(
    client: SSHClient,
    command: str,
    description: str,
    *,
    check: bool = True,
) -> Tuple[str, str, int]:
    stdin, stdout, stderr = client.exec_command(command)  # pyright: ignore
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    exitCode = stdout.channel.recv_exit_status()

    if check and exitCode != 0:
        message = err.strip() or out.strip() or f"exit code {exitCode}"
        raise DeploymentError(f"{description} failed: {message}")

    return out, err, exitCode


def _validateArchive(path: pthl.Path, requiredFiles: Sequence[str] = ()) -> None:
    if not path.exists():
        raise DeploymentError(f"Deployment archive not found: {path}")
    if not path.is_file() or path.stat().st_size == 0:
        raise DeploymentError(f"Deployment archive is empty: {path}")

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as error:
        raise DeploymentError(
            f"Invalid deployment archive {path.name}: {error}"
        ) from error

    names = [info.filename for info in infos]
    if not names:
        raise DeploymentError(f"Deployment archive {path.name} is empty")

    for info in infos:
        name = info.filename
        normalized = name.replace("\\", "/")
        parts = normalized.split("/")
        if normalized.startswith("/") or any(part == ".." for part in parts):
            raise DeploymentError(f"Unsafe path in {path.name}: {name}")
        if len(normalized) > 1 and normalized[1] == ":":
            raise DeploymentError(f"Unsafe path in {path.name}: {name}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise DeploymentError(
                f"Symbolic links are not allowed in {path.name}: {name}"
            )

    missing = [required for required in requiredFiles if required not in names]
    if missing:
        raise DeploymentError(
            f"{path.name} is missing required file(s): {', '.join(missing)}"
        )


def _validateArchives(archives: Iterable[Tuple[pthl.Path, Sequence[str]]]) -> None:
    for path, requiredFiles in archives:
        _validateArchive(path, requiredFiles)


def _validateDevice(nickname: str, data: object) -> Dict[str, str]:
    if not isinstance(data, dict):
        raise DeploymentError(f"Device `{nickname}` must be a YAML mapping.")

    missing = [key for key in ("hostname", "ip", "password") if not data.get(key)]
    if missing:
        raise DeploymentError(f"Device `{nickname}` is missing: {', '.join(missing)}")

    hostname = str(data["hostname"])
    ip = str(data["ip"])
    password = str(data["password"])

    if any(character.isspace() for character in hostname):
        raise DeploymentError(f"Device `{nickname}` has an invalid hostname.")
    if not IsValidIP(ip):
        raise DeploymentError(f"Device `{nickname}` has an invalid IP address.")

    return {"hostname": hostname, "ip": ip, "password": password}


@dataclass(frozen=True)
class _RemoteLayout:
    home: str
    live: str
    staging: str
    backup: str
    temp: str = ""


def _remoteHome(client: SSHClient) -> str:
    stdout, _, _ = _runRemote(client, 'printf %s "$HOME"', "Resolve home directory")
    home = stdout.strip()
    if not home.startswith("/") or "\n" in home:
        raise DeploymentError("Could not determine the remote home directory.")
    return home


def _copyConfig(client: SSHClient, layout: _RemoteLayout) -> None:
    liveConfig = f"{layout.live}/config"
    stagingConfig = f"{layout.staging}/config"
    command = (
        f"if [ -d {_quote(liveConfig)} ]; then "
        f"mkdir -p {_quote(stagingConfig)} && "
        f"cp -a {_quote(liveConfig + '/.')} {_quote(stagingConfig + '/')}; "
        "fi"
    )
    _runRemote(client, command, "Preserve configuration")


def _swapDeployment(client: SSHClient, layout: _RemoteLayout) -> bool:
    _, _, liveExists = _runRemote(
        client,
        f"test -d {_quote(layout.live)}",
        "Check current deployment",
        check=False,
    )

    if liveExists == 0:
        _runRemote(
            client,
            f"mv {_quote(layout.live)} {_quote(layout.backup)}",
            "Back up current deployment",
        )

    try:
        _runRemote(
            client,
            f"mv {_quote(layout.staging)} {_quote(layout.live)}",
            "Activate new deployment",
        )
    except DeploymentError as error:
        if liveExists == 0:
            _runRemote(
                client,
                f"mv {_quote(layout.backup)} {_quote(layout.live)}",
                "Restore previous deployment",
                check=False,
            )
        raise DeploymentError(
            f"Could not activate the new deployment. "
            f"The previous version is at {layout.backup}. {error}"
        ) from error

    return liveExists == 0


def _rollback(client: SSHClient, layout: _RemoteLayout, hadBackup: bool) -> None:
    _warn("Deployment failed; rolling back...")

    if hadBackup:
        _, _, restoreCode = _runRemote(
            client,
            f"rm -rf {_quote(layout.live)} && "
            f"mv {_quote(layout.backup)} {_quote(layout.live)}",
            "Restore previous deployment",
            check=False,
        )
        if restoreCode != 0:
            _fail(
                "Could not restore the previous deployment. "
                f"It is still at {layout.backup}, and the service was left stopped."
            )
            return

        try:
            startService(client, SERVICE_NAME)
            waitForServiceActive(client, SERVICE_NAME, timeout=10.0)
            _warn("Previous deployment restored and restarted.")
        except Exception as error:
            _fail(f"Could not restart the previous deployment: {error}")
    else:
        _runRemote(
            client,
            f"rm -rf {_quote(layout.live)}",
            "Remove failed deployment",
            check=False,
        )
        _warn("No previous deployment to restore.")


def _pruneBackups(client: SSHClient, layout: _RemoteLayout) -> None:
    command = (
        f"find {_quote(layout.home)} -mindepth 1 -maxdepth 1 -type d "
        f"-name {_quote(BACKUP_PREFIX + '*')} ! -path {_quote(layout.backup)} "
        "-exec rm -rf {} +"
    )
    _runRemote(client, command, "Remove old backups", check=False)


def _streamLogs(client: SSHClient, hostname: str) -> None:
    _info(f"Following runtime logs for {hostname} (Ctrl+C to stop)...")
    try:
        streamer = SystemdServiceLogStreamer(sshClient=client, service=SERVICE_NAME)
        streamer.connect()
        for line in streamer.stream():
            print(line)
    except KeyboardInterrupt:
        _info("Stopped following logs.")
    except Exception as error:
        _warn(f"Could not follow logs: {error}")


def _connectAndDeploy(
    hostname: str,
    ip: str,
    password: str,
    zip_paths: List[pthl.Path],
    *,
    followLogs: bool = True,
) -> None:
    start = time.perf_counter()
    _info(f"Connecting to {hostname}@{ip}...")

    try:
        client = connectSSH(ip, hostname, password)
    except HostKeyError as error:
        raise DeploymentError(str(error)) from error
    except Exception as error:
        raise DeploymentError(
            f"Could not connect to {hostname}@{ip}: {error}"
        ) from error

    layout: Optional[_RemoteLayout] = None
    swapped = False
    hadBackup = False
    stopped = False

    try:
        _runRemote(client, "command -v unzip >/dev/null 2>&1", "Check for unzip")
        _runRemote(client, "sudo -n true", "Check passwordless sudo")

        home = _remoteHome(client)
        suffix = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        layout = _RemoteLayout(
            home=home,
            live=f"{home}/{REMOTE_APP_DIR}",
            staging=f"{home}/{STAGING_PREFIX}{suffix}",
            backup=f"{home}/{BACKUP_PREFIX}{suffix}",
        )

        temp, _, _ = _runRemote(
            client, "mktemp -d", "Create remote temporary directory"
        )
        layout = replace(layout, temp=temp.strip())
        if not layout.temp.startswith("/"):
            raise DeploymentError(
                "Could not create a temporary directory on the device."
            )

        _runRemote(
            client,
            f"mkdir -p {_quote(layout.staging)}",
            "Create staging directory",
        )

        transport = client.get_transport()
        if transport is None:
            raise DeploymentError("SSH transport is not available.")

        with SCPClient(transport) as scp:
            for zip_path in zip_paths:
                remoteZip = f"{layout.temp}/{zip_path.name}"
                _info(f"Uploading {zip_path.name}...")
                scp.put(str(zip_path), remoteZip)

        for zip_path in zip_paths:
            remoteZip = f"{layout.temp}/{zip_path.name}"
            _info(f"Extracting {zip_path.name}...")
            _runRemote(
                client,
                f"unzip -q -o {_quote(remoteZip)} -d {_quote(layout.staging)}",
                f"Extract {zip_path.name}",
            )

        _info("Stopping the running service...")
        stopped = stopService(client, SERVICE_NAME)

        _copyConfig(client, layout)
        hadBackup = _swapDeployment(client, layout)
        swapped = True

        _info("Installing and starting the service...")
        setupServiceOnConnectedClient(client, hostname, start=False)
        startService(client, SERVICE_NAME)
        waitForServiceActive(client, SERVICE_NAME)
    except Exception as error:
        if layout is not None and swapped:
            _rollback(client, layout, hadBackup)
        elif stopped:
            try:
                startService(client, SERVICE_NAME)
                _warn("Deployment failed; the previous deployment was restarted.")
            except Exception as restartError:
                _fail(f"Could not restart the previous deployment: {restartError}")

        if isinstance(error, DeploymentError):
            raise
        raise DeploymentError(str(error)) from error
    else:
        elapsed = time.perf_counter() - start
        _success(f"Deployed {hostname} in {elapsed:.1f}s")

        if hadBackup and layout is not None:
            _info(f"Previous version kept at {layout.backup}")
            _pruneBackups(client, layout)

        if followLogs:
            _streamLogs(client, hostname)
    finally:
        if layout is not None and layout.temp:
            try:
                _runRemote(
                    client,
                    f"rm -rf {_quote(layout.temp)}",
                    "Remove temporary files",
                    check=False,
                )
            except Exception:
                pass
        client.close()


def _printDeviceSummary(devices: Dict[str, dict]) -> None:
    fprint(MarkupColors.header("Deployment targets"))
    for nickname, data in devices.items():
        fprint(
            f"  [bold]{nickname}[/bold]  "
            f"{data.get('hostname', '?')}@{data.get('ip', '?')}"
        )


def _confirmDeploy(devices: Dict[str, dict], options: DeployOptions) -> bool:
    if options.assumeYes or options.devices:
        return True

    if not sys.stdin.isatty():
        _fail(
            "Refusing to deploy to every device without confirmation in a "
            "non-interactive terminal. Use `--yes` to continue."
        )
        return False

    return (
        questionary.confirm(
            f"Deploy to all {len(devices)} configured device(s)?", default=True
        ).ask()
        is True
    )


def _readConfig(path: pthl.Path) -> dict:
    if not path.exists():
        raise DeploymentError(f"Deploy config not found: {path}")

    with open(path, "r") as file:
        data = yaml.full_load(file) or {}

    if not isinstance(data, dict):
        raise DeploymentError(f"{path} must contain a YAML mapping.")

    return data


def _getDeploys(data: dict, path: pthl.Path) -> Dict[str, dict]:
    deploys = data.get("deploy") or {}
    if not isinstance(deploys, dict):
        raise DeploymentError(f"`deploy` in {path} must be a mapping.")
    return deploys


def resolveDeploys(
    deployConfigPath: pthl.Path, argv: Optional[List[str]] = None
) -> Tuple[Dict[str, dict], List[str]]:
    """Load configured devices and report requested names that are missing."""
    if not deployConfigPath.exists():
        addDeviceConfig(deployConfigPath)

    _warnIfConfigPermissionsAreOpen(deployConfigPath)

    data = _readConfig(deployConfigPath)
    deploys = _getDeploys(data, deployConfigPath)

    if not deploys:
        addDeviceConfig(deployConfigPath)
        data = _readConfig(deployConfigPath)
        deploys = _getDeploys(data, deployConfigPath)

    if argv:
        requested = list(dict.fromkeys(argv))
        selected = {name: cfg for name, cfg in deploys.items() if name in requested}
        missing = [name for name in requested if name not in deploys]
        return selected, missing

    return dict(deploys), []


def listDevices(deployConfigPath: pthl.Path) -> int:
    """Print the configured deployment devices."""
    try:
        _warnIfConfigPermissionsAreOpen(deployConfigPath)
        data = _readConfig(deployConfigPath)
        deploys = _getDeploys(data, deployConfigPath)
    except DeploymentError as error:
        _fail(str(error))
        return 1

    if not deploys:
        _warn("No devices are configured. Run `device add` to add one.")
        return 0

    _printDeviceSummary(deploys)
    return 0


def removeDevice(deployConfigPath: pthl.Path, nickname: str) -> int:
    """Remove a device from the deployment configuration."""
    try:
        data = _readConfig(deployConfigPath)
        deploys = _getDeploys(data, deployConfigPath)
    except DeploymentError as error:
        _fail(str(error))
        return 1

    if nickname not in deploys:
        _fail(f"Device `{nickname}` not found in config.")
        return 1

    if not questionary.confirm(
        f"Remove `{nickname}` from {deployConfigPath}?", default=False
    ).ask():
        _warn("Cancelled.")
        return 1

    del deploys[nickname]
    data["deploy"] = deploys

    try:
        _writeConfig(deployConfigPath, data)
    except DeploymentError as error:
        _fail(str(error))
        return 1

    _success(f"Removed `{nickname}`.")
    return 0


def loadDeviceData(
    deployConfigPath: pthl.Path, argv: Optional[List[str]] = None
) -> dict:
    """Load device deploy data, reporting requested devices that are missing."""
    selected, missing = resolveDeploys(deployConfigPath, argv)
    for name in missing:
        _fail(f"Device `{name}` not found in config.")
    return selected


def deploy(
    path: pthl.Path,
    cwd: pthl.Path,
    argv: Optional[List[str]] = None,
    devices: Optional[Dict[str, dict]] = None,
    *,
    followLogs: bool = True,
) -> int:
    """Deploy the built project archives to the selected devices."""
    try:
        selected = devices if devices is not None else loadDeviceData(path, argv)
    except DeploymentError as error:
        _fail(str(error))
        return 1

    if not selected:
        _fail("No devices selected for deployment.")
        return 1

    projectZip = cwd / BUILD_DIR / "project.zip"
    packageZip = cwd / BUILD_DIR / "synapse.zip"

    try:
        _validateArchives(
            [
                (projectZip, ("main.py",)),
                (packageZip, ()),
            ]
        )
    except DeploymentError as error:
        _fail(str(error))
        return 1

    failures = 0
    for nickname, rawDeviceData in selected.items():
        try:
            deviceData = _validateDevice(nickname, rawDeviceData)
            _connectAndDeploy(
                deviceData["hostname"],
                deviceData["ip"],
                deviceData["password"],
                [projectZip, packageZip],
                followLogs=followLogs,
            )
        except Exception as error:
            failures += 1
            _fail(f"Deployment to `{nickname}` failed: {error}")
            if os.environ.get("SYNAPSE_DEBUG"):
                traceback.print_exc()

    if failures:
        _fail(f"{failures} of {len(selected)} deployment(s) failed.")
        return 1

    _success(f"Deployed to {len(selected)} device(s).")
    return 0


def _fileShouldDeploy(cwd: pthl.Path):
    deployDir = cwd / "deploy"

    def shouldDeploy(path: pthl.Path) -> bool:
        return str(path).endswith(".py") or path.is_relative_to(deployDir)

    return shouldDeploy


def _setupAndRunDeploy(options: DeployOptions) -> int:
    cwd = pthl.Path(os.getcwd())
    if not (cwd / SYNAPSE_PROJECT_FILE).exists():
        _fail(NOT_IN_SYNAPSE_PROJECT_ERR)
        return 1

    configPath = cwd / SYNAPSE_PROJECT_FILE

    try:
        selected, missing = resolveDeploys(configPath, options.devices)
    except DeploymentError as error:
        _fail(str(error))
        return 1

    for name in missing:
        _fail(f"Device `{name}` not found in config.")

    if missing or not selected:
        if not selected and not missing:
            _fail("No devices selected for deployment.")
        return 1

    _printDeviceSummary(selected)

    if options.dryRun:
        _info("Dry run: no files will be uploaded and no services will be changed.")
        return 0

    if not _confirmDeploy(selected, options):
        _warn("Deployment cancelled.")
        return 1

    _info("Packaging the project...")
    createPackageZIP(cwd / BUILD_DIR)
    createDirectoryZIP(
        pthl.Path(os.getcwd()),
        cwd / BUILD_DIR / "project.zip",
        _fileShouldDeploy(cwd),
    )

    return deploy(
        configPath,
        cwd,
        options.devices,
        selected,
        followLogs=options.followLogs,
    )


def setupAndRunDeploy(
    argv: Optional[Union[List[str], DeployOptions]] = None,
) -> int:
    """Package the project and deploy it to the selected devices."""
    if isinstance(argv, DeployOptions):
        options = argv
    else:
        try:
            options = parseDeployArgs(argv)
        except DeploymentError as error:
            _fail(str(error))
            return 1

    try:
        return _setupAndRunDeploy(options)
    except KeyboardInterrupt:
        _warn("Deployment cancelled.")
        return 1
    except Exception as error:
        _fail(f"Deployment failed: {error}")
        if os.environ.get("SYNAPSE_DEBUG"):
            traceback.print_exc()
        return 1
