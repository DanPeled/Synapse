# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import stat
import zipfile
from pathlib import Path
from unittest import mock

import pytest
import synapse_installer.deploy as deploy_mod
import yaml
from synapse_installer.deploy import (
    DeploymentError,
    DeployOptions,
    _confirmDeploy,
    _connectAndDeploy,
    _RemoteLayout,
    _rollback,
    _validateArchive,
    _warnIfConfigPermissionsAreOpen,
    _writeConfig,
    addDeviceConfig,
    deploy,
    listDevices,
    loadDeviceData,
    parseDeployArgs,
    removeDevice,
    resolveDeploys,
    setupAndRunDeploy,
)
from synapse_installer.discover import DiscoveredDevice
from synapse_installer.util import IsValidIP

DEVICE = {"hostname": "pi", "ip": "192.168.1.5", "password": "pw"}


def writeConfig(path: Path, devices: dict) -> None:
    path.write_text(yaml.dump({"deploy": devices}))
    os.chmod(path, 0o600)


def makeZip(path: Path, names) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, "data")
    return path


def test_is_valid_ip():
    assert IsValidIP("192.168.0.1") is True
    assert IsValidIP("2001:0db8:85a3:0000:0000:8a2e:0370:7334") is True
    assert IsValidIP("not-an-ip") is False


# ---------------------------
# command-line options
# ---------------------------


def test_parse_deploy_args():
    options = parseDeployArgs(["-y", "-n", "--no-logs", "robot", "robot"])

    assert options.assumeYes is True
    assert options.dryRun is True
    assert options.followLogs is False
    assert options.devices == ["robot", "robot"]


def test_parse_deploy_args_unknown_option():
    with pytest.raises(DeploymentError, match="Unknown option"):
        parseDeployArgs(["--bogus"])


# ---------------------------
# device configuration
# ---------------------------


@mock.patch("synapse_installer.deploy.questionary.select")
@mock.patch("synapse_installer.deploy.questionary.text")
@mock.patch("synapse_installer.deploy.questionary.password")
def test_add_device_config_manual(mock_password, mock_text, mock_select, tmp_path):
    mock_select().ask.return_value = "Manual (Provide hostname & password)"
    mock_text.side_effect = [
        mock.Mock(ask=lambda: "my-device"),  # hostname
        mock.Mock(ask=lambda: "my-device"),  # nickname
        mock.Mock(ask=lambda: "192.168.1.5"),  # IP
    ]
    mock_password().ask.return_value = "pass"

    configPath = tmp_path / "config.yml"
    addDeviceConfig(configPath)

    with open(configPath) as file:
        data = yaml.safe_load(file)

    assert "deploy" in data
    assert "my-device" in data["deploy"]
    assert data["deploy"]["my-device"]["ip"] == "192.168.1.5"
    assert stat.S_IMODE(configPath.stat().st_mode) == 0o600


@mock.patch("synapse_installer.deploy.discoverDevices")
@mock.patch("synapse_installer.deploy.questionary.select")
@mock.patch("synapse_installer.deploy.questionary.confirm")
@mock.patch("synapse_installer.deploy.questionary.password")
def test_add_device_config_automatic(
    mock_password, mock_confirm, mock_select, mock_discover, tmp_path
):
    mock_select().ask.return_value = "Automatic (Find available devices)"
    mock_discover.return_value = [
        DiscoveredDevice(
            nickname="robot", hostname="robot", ip="10.0.0.2", username="pi"
        )
    ]
    mock_confirm().ask.return_value = True
    mock_password().ask.return_value = "pass"

    configPath = tmp_path / "config.yml"
    addDeviceConfig(configPath)

    with open(configPath) as file:
        data = yaml.safe_load(file)

    assert data["deploy"]["robot"] == {
        "hostname": "pi",
        "ip": "10.0.0.2",
        "password": "pass",
    }


@mock.patch("synapse_installer.deploy.discoverDevices", return_value=[])
@mock.patch("synapse_installer.deploy.questionary.select")
def test_add_device_config_automatic_no_devices(mock_select, mock_discover, tmp_path):
    mock_select().ask.return_value = "Automatic (Find available devices)"

    configPath = tmp_path / "config.yml"
    addDeviceConfig(configPath)

    with open(configPath) as file:
        data = yaml.safe_load(file)

    assert data in ({}, None)


def test_write_config_is_private(tmp_path):
    configPath = tmp_path / "nested" / "config.yml"

    _writeConfig(configPath, {"deploy": {}})

    assert stat.S_IMODE(configPath.stat().st_mode) == 0o600


def test_warn_when_config_is_readable(tmp_path):
    configPath = tmp_path / "config.yml"
    configPath.write_text("deploy: {}\n")
    os.chmod(configPath, 0o644)

    with mock.patch.object(deploy_mod, "_warn") as warn:
        _warnIfConfigPermissionsAreOpen(configPath)

    warn.assert_called_once()


def test_no_warning_when_config_is_private(tmp_path):
    configPath = tmp_path / "config.yml"
    configPath.write_text("deploy: {}\n")
    os.chmod(configPath, 0o600)

    with mock.patch.object(deploy_mod, "_warn") as warn:
        _warnIfConfigPermissionsAreOpen(configPath)

    warn.assert_not_called()


# ---------------------------
# archive validation
# ---------------------------


def test_validate_archive_accepts_required_file(tmp_path):
    archive = makeZip(tmp_path / "project.zip", ["main.py", "lib/thing.py"])

    _validateArchive(archive, ("main.py",))


def test_validate_archive_requires_main(tmp_path):
    archive = makeZip(tmp_path / "project.zip", ["lib/thing.py"])

    with pytest.raises(DeploymentError, match="main.py"):
        _validateArchive(archive, ("main.py",))


@pytest.mark.parametrize("name", ["../evil.py", "/etc/passwd", "C:/evil.py"])
def test_validate_archive_rejects_unsafe_paths(tmp_path, name):
    archive = makeZip(tmp_path / "project.zip", [name])

    with pytest.raises(DeploymentError, match="Unsafe path"):
        _validateArchive(archive)


def test_validate_archive_rejects_missing_file(tmp_path):
    with pytest.raises(DeploymentError, match="not found"):
        _validateArchive(tmp_path / "missing.zip")


def test_validate_archive_rejects_empty_file(tmp_path):
    archive = tmp_path / "project.zip"
    archive.write_bytes(b"")

    with pytest.raises(DeploymentError, match="empty"):
        _validateArchive(archive)


def test_validate_archive_rejects_invalid_zip(tmp_path):
    archive = tmp_path / "project.zip"
    archive.write_text("not a zip")

    with pytest.raises(DeploymentError, match="Invalid deployment archive"):
        _validateArchive(archive)


def test_validate_archive_rejects_symlinks(tmp_path):
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as archiveFile:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        archiveFile.writestr(info, "target")

    with pytest.raises(DeploymentError, match="Symbolic links"):
        _validateArchive(archive)


# ---------------------------
# deployment configuration loading
# ---------------------------


def test_load_device_data_errors_when_missing(tmp_path):
    path = tmp_path / "nonexistent.yaml"

    with mock.patch("synapse_installer.deploy.addDeviceConfig") as add:
        with pytest.raises(DeploymentError):
            loadDeviceData(path)

    add.assert_called_once_with(path)


def test_load_device_data_creates_when_empty(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")

    def fakeAdd(configPath):
        writeConfig(configPath, {"robot": DEVICE})

    with mock.patch("synapse_installer.deploy.addDeviceConfig", side_effect=fakeAdd):
        selected = loadDeviceData(path)

    assert selected == {"robot": DEVICE}


def test_resolve_deploys_reports_missing(tmp_path):
    configPath = tmp_path / "config.yml"
    writeConfig(configPath, {"robot": DEVICE})

    selected, missing = resolveDeploys(configPath, ["robot", "nope"])

    assert list(selected) == ["robot"]
    assert missing == ["nope"]


def test_list_devices(tmp_path):
    configPath = tmp_path / "config.yml"
    writeConfig(configPath, {"robot": DEVICE})

    with mock.patch.object(deploy_mod, "_printDeviceSummary") as summary:
        assert listDevices(configPath) == 0

    summary.assert_called_once_with({"robot": DEVICE})


def test_list_devices_missing_config(tmp_path):
    assert listDevices(tmp_path / "nope.yml") == 1


@mock.patch("synapse_installer.deploy.questionary.confirm")
def test_remove_device(mock_confirm, tmp_path):
    configPath = tmp_path / "config.yml"
    writeConfig(configPath, {"robot": DEVICE, "other": DEVICE})
    mock_confirm().ask.return_value = True

    assert removeDevice(configPath, "robot") == 0

    with open(configPath) as file:
        data = yaml.safe_load(file)
    assert list(data["deploy"]) == ["other"]
    assert stat.S_IMODE(configPath.stat().st_mode) == 0o600


@mock.patch("synapse_installer.deploy.questionary.confirm")
def test_remove_device_cancelled(mock_confirm, tmp_path):
    configPath = tmp_path / "config.yml"
    writeConfig(configPath, {"robot": DEVICE})
    mock_confirm().ask.return_value = False

    assert removeDevice(configPath, "robot") == 1

    with open(configPath) as file:
        data = yaml.safe_load(file)
    assert "robot" in data["deploy"]


def test_remove_device_missing(tmp_path):
    configPath = tmp_path / "config.yml"
    writeConfig(configPath, {"robot": DEVICE})

    assert removeDevice(configPath, "nope") == 1


# ---------------------------
# confirmation
# ---------------------------


def test_confirm_deploy_skipped_for_explicit_devices():
    options = DeployOptions(devices=["robot"])

    with mock.patch.object(deploy_mod.sys.stdin, "isatty", return_value=False):
        assert _confirmDeploy({"robot": DEVICE}, options) is True


def test_confirm_deploy_refuses_non_interactive():
    options = DeployOptions()

    with mock.patch.object(deploy_mod.sys.stdin, "isatty", return_value=False):
        assert _confirmDeploy({"robot": DEVICE}, options) is False


@mock.patch("synapse_installer.deploy.questionary.confirm")
def test_confirm_deploy_interactive(mock_confirm):
    mock_confirm().ask.return_value = True

    with mock.patch.object(deploy_mod.sys.stdin, "isatty", return_value=True):
        assert _confirmDeploy({"robot": DEVICE}, DeployOptions()) is True


# ---------------------------
# deploy
# ---------------------------


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_runs_connect_deploy(mock_connect, tmp_path):
    configPath = tmp_path / "config.yaml"
    writeConfig(configPath, {"my-device": DEVICE})
    makeZip(tmp_path / "build" / "project.zip", ["main.py"])
    makeZip(tmp_path / "build" / "synapse.zip", ["synapse/__init__.py"])

    assert deploy(configPath, tmp_path, ["my-device"]) == 0

    mock_connect.assert_called_once()
    assert mock_connect.call_args.args[:3] == ("pi", "192.168.1.5", "pw")


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_validates_archives_before_connecting(mock_connect, tmp_path):
    configPath = tmp_path / "config.yaml"
    writeConfig(configPath, {"my-device": DEVICE})

    assert deploy(configPath, tmp_path, ["my-device"]) == 1

    mock_connect.assert_not_called()


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_rejects_archive_without_main(mock_connect, tmp_path):
    configPath = tmp_path / "config.yaml"
    writeConfig(configPath, {"my-device": DEVICE})
    makeZip(tmp_path / "build" / "project.zip", ["other.py"])
    makeZip(tmp_path / "build" / "synapse.zip", ["synapse/__init__.py"])

    assert deploy(configPath, tmp_path, ["my-device"]) == 1

    mock_connect.assert_not_called()


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_reports_failure(mock_connect, tmp_path):
    configPath = tmp_path / "config.yaml"
    writeConfig(configPath, {"my-device": DEVICE})
    makeZip(tmp_path / "build" / "project.zip", ["main.py"])
    makeZip(tmp_path / "build" / "synapse.zip", ["synapse/__init__.py"])
    mock_connect.side_effect = RuntimeError("boom")

    assert deploy(configPath, tmp_path, ["my-device"]) == 1


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_rejects_invalid_device(mock_connect, tmp_path):
    configPath = tmp_path / "config.yaml"
    writeConfig(
        configPath, {"my-device": {"hostname": "pi", "ip": "nope", "password": "pw"}}
    )
    makeZip(tmp_path / "build" / "project.zip", ["main.py"])
    makeZip(tmp_path / "build" / "synapse.zip", ["synapse/__init__.py"])

    assert deploy(configPath, tmp_path, ["my-device"]) == 1

    mock_connect.assert_not_called()


# ---------------------------
# _connectAndDeploy
# ---------------------------


def _fake_run_remote(client, command, description, *, check=True):
    if command.startswith("printf"):
        return ("/home/pi", "", 0)
    if command == "mktemp -d":
        return ("/tmp/synapse-123", "", 0)
    if command.startswith("test -d"):
        return ("", "", 0)
    return ("", "", 0)


@mock.patch("synapse_installer.deploy.waitForServiceActive")
@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy.stopService")
@mock.patch("synapse_installer.deploy.setupServiceOnConnectedClient")
@mock.patch("synapse_installer.deploy._pruneBackups")
@mock.patch("synapse_installer.deploy._runRemote")
@mock.patch("synapse_installer.deploy.SCPClient")
@mock.patch("synapse_installer.deploy.connectSSH")
def test_connect_and_deploy_success(
    mock_connect,
    mock_scp,
    mock_run,
    mock_prune,
    mock_setup,
    mock_stop,
    mock_start,
    mock_wait,
    tmp_path,
):
    mock_client = mock.Mock()
    mock_connect.return_value = mock_client
    mock_run.side_effect = _fake_run_remote

    projectZip = tmp_path / "project.zip"
    packageZip = tmp_path / "synapse.zip"
    projectZip.write_bytes(b"project")
    packageZip.write_bytes(b"package")

    _connectAndDeploy(
        "pi", "192.168.1.5", "pw", [projectZip, packageZip], followLogs=False
    )

    mock_stop.assert_called_once()
    mock_setup.assert_called_once()
    assert mock_setup.call_args.kwargs.get("start") is False
    mock_start.assert_called_once()
    mock_wait.assert_called_once()
    mock_prune.assert_called_once()

    scp = mock_scp.return_value.__enter__.return_value
    assert scp.put.call_count == 2

    commands = [call.args[1] for call in mock_run.call_args_list]
    assert any(command.startswith("mv ") for command in commands)
    assert any(command.startswith("rm -rf") for command in commands)
    mock_client.close.assert_called_once()


@mock.patch("synapse_installer.deploy._rollback")
@mock.patch("synapse_installer.deploy.waitForServiceActive")
@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy.stopService")
@mock.patch("synapse_installer.deploy.setupServiceOnConnectedClient")
@mock.patch("synapse_installer.deploy._runRemote")
@mock.patch("synapse_installer.deploy.SCPClient")
@mock.patch("synapse_installer.deploy.connectSSH")
def test_connect_and_deploy_rolls_back_on_failure(
    mock_connect,
    mock_scp,
    mock_run,
    mock_setup,
    mock_stop,
    mock_start,
    mock_wait,
    mock_rollback,
    tmp_path,
):
    mock_connect.return_value = mock.Mock()
    mock_run.side_effect = _fake_run_remote
    mock_setup.side_effect = RuntimeError("service broke")

    projectZip = tmp_path / "project.zip"
    projectZip.write_bytes(b"project")

    with pytest.raises(DeploymentError):
        _connectAndDeploy("pi", "192.168.1.5", "pw", [projectZip], followLogs=False)

    mock_rollback.assert_called_once()
    assert mock_rollback.call_args.args[2] is True


@mock.patch("synapse_installer.deploy._rollback")
@mock.patch("synapse_installer.deploy.stopService")
@mock.patch("synapse_installer.deploy._runRemote")
@mock.patch("synapse_installer.deploy.SCPClient")
@mock.patch("synapse_installer.deploy.connectSSH")
def test_connect_and_deploy_no_rollback_before_swap(
    mock_connect,
    mock_scp,
    mock_run,
    mock_stop,
    mock_rollback,
    tmp_path,
):
    mock_connect.return_value = mock.Mock()
    mock_run.side_effect = _fake_run_remote
    mock_stop.side_effect = RuntimeError("cannot stop")

    projectZip = tmp_path / "project.zip"
    projectZip.write_bytes(b"project")

    with pytest.raises(DeploymentError):
        _connectAndDeploy("pi", "192.168.1.5", "pw", [projectZip], followLogs=False)

    mock_rollback.assert_not_called()


@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy._rollback")
@mock.patch("synapse_installer.deploy._copyConfig")
@mock.patch("synapse_installer.deploy.stopService")
@mock.patch("synapse_installer.deploy._runRemote")
@mock.patch("synapse_installer.deploy.SCPClient")
@mock.patch("synapse_installer.deploy.connectSSH")
def test_connect_and_deploy_restarts_old_service_before_swap(
    mock_connect,
    mock_scp,
    mock_run,
    mock_stop,
    mock_copy,
    mock_rollback,
    mock_start,
    tmp_path,
):
    mock_connect.return_value = mock.Mock()
    mock_run.side_effect = _fake_run_remote
    mock_stop.return_value = True
    mock_copy.side_effect = DeploymentError("copy failed")

    projectZip = tmp_path / "project.zip"
    projectZip.write_bytes(b"project")

    with pytest.raises(DeploymentError):
        _connectAndDeploy("pi", "192.168.1.5", "pw", [projectZip], followLogs=False)

    mock_rollback.assert_not_called()
    mock_start.assert_called_once()


def _layout(tmp_path):
    home = str(tmp_path)
    return _RemoteLayout(
        home=home,
        live=f"{home}/Synapse",
        staging=f"{home}/.synapse-staging-x",
        backup=f"{home}/.synapse-backup-x",
        temp=f"{home}/tmp",
    )


@mock.patch("synapse_installer.deploy.waitForServiceActive")
@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy._runRemote")
def test_rollback_restarts_restored_deployment(
    mock_run, mock_start, mock_wait, tmp_path
):
    mock_run.return_value = ("", "", 0)

    _rollback(mock.Mock(), _layout(tmp_path), hadBackup=True)

    mock_start.assert_called_once()
    mock_wait.assert_called_once()


@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy._runRemote")
def test_rollback_does_not_start_when_restore_fails(mock_run, mock_start, tmp_path):
    mock_run.return_value = ("", "restore failed", 1)

    _rollback(mock.Mock(), _layout(tmp_path), hadBackup=True)

    mock_start.assert_not_called()


@mock.patch("synapse_installer.deploy.startService")
@mock.patch("synapse_installer.deploy._runRemote")
def test_rollback_without_backup_removes_new_deployment(mock_run, mock_start, tmp_path):
    mock_run.return_value = ("", "", 0)

    _rollback(mock.Mock(), _layout(tmp_path), hadBackup=False)

    mock_start.assert_not_called()
    assert "rm -rf" in mock_run.call_args.args[1]


# ---------------------------
# setupAndRunDeploy
# ---------------------------


def test_setup_and_run_deploy_rejects_unknown_option():
    assert setupAndRunDeploy(["--bogus"]) == 1


def test_dry_run_does_not_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synapseproject").write_text("")

    monkeypatch.setattr(
        deploy_mod, "resolveDeploys", lambda *a, **k: ({"robot": DEVICE}, [])
    )
    package = mock.Mock()
    monkeypatch.setattr(deploy_mod, "createPackageZIP", package)
    monkeypatch.setattr(deploy_mod, "createDirectoryZIP", package)

    assert setupAndRunDeploy(["-n"]) == 0

    package.assert_not_called()


def test_setup_and_run_deploy_requires_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert setupAndRunDeploy([]) == 1
