# test_sync.py
import io
from unittest import mock

import paramiko
import pytest
from synapse_installer.sync import (installPipRequirements,
                                    installSystemPackage, setupSudoers, sync,
                                    syncRequirements)


@pytest.fixture
def mock_client(mocker):
    """Create a mock SSHClient with exec_command behavior."""
    client = mocker.Mock(spec=paramiko.SSHClient)
    mock_channel = mocker.Mock()
    mock_channel.recv_exit_status.return_value = 0

    stdout = io.BytesIO(b"")
    stdout.channel = mock_channel  # pyright: ignore
    stderr = io.BytesIO(b"")

    client.exec_command.return_value = (io.BytesIO(b""), stdout, stderr)
    client.get_transport.return_value = True
    return client


def test_sync_requirements_success(mocker, mock_client):
    mocker.patch("paramiko.SSHClient", return_value=mock_client)
    mocker.patch("synapse_installer.sync.setupSudoers")
    mocker.patch("synapse_installer.sync.installSystemPackage")
    mocker.patch("synapse_installer.sync.installPipRequirements")

    syncRequirements("host", "pass", "1.2.3.4")

    mock_client.connect.assert_called_once()
    mock_client.close.assert_called_once()


def test_sync_requirements_exception(mocker):
    mock_client = mocker.Mock(spec=paramiko.SSHClient)
    mock_client.connect.side_effect = Exception("fail")
    mocker.patch("paramiko.SSHClient", return_value=mock_client)
    fail_mock = mocker.patch("synapse_installer.sync.fprint")
    syncRequirements("h", "p", "ip")
    assert fail_mock.call_count == 1


def test_sync_adds_device_config(mocker, tmp_path):
    proj_file = tmp_path / "synapse.yaml"
    proj_file.write_text("{}")
    mocker.patch("synapse_installer.sync.SYNAPSE_PROJECT_FILE", proj_file.name)
    mocker.patch("synapse_installer.sync.os.getcwd", return_value=str(tmp_path))
    mocker.patch(
        "synapse_installer.sync.addDeviceConfig",
        side_effect=lambda x: proj_file.write_text(
            'deploy: {"dev":{"hostname":"h","password":"p","ip":"1"}}'
        ),
    )
    mocker.patch("synapse_installer.sync.syncRequirements")
    sync(["cmd", "dev"])


def test_sync_no_args(mocker, tmp_path):
    proj_file = tmp_path / "synapse.yaml"
    proj_file.write_text("deploy: {}")
    mocker.patch("synapse_installer.sync.SYNAPSE_PROJECT_FILE", proj_file.name)
    mocker.patch("synapse_installer.sync.os.getcwd", return_value=str(tmp_path))
    fail_mock = mocker.patch("synapse_installer.sync.fprint")
    sync(["cmd"])
    fail_mock.assert_called_once()


def test_sync_device_not_found(mocker, tmp_path):
    proj_file = tmp_path / "synapse.yaml"
    proj_file.write_text("deploy: {}")
    mocker.patch("synapse_installer.sync.SYNAPSE_PROJECT_FILE", proj_file.name)
    mocker.patch("synapse_installer.sync.os.getcwd", return_value=str(tmp_path))
    fail_mock = mocker.patch("synapse_installer.sync.fprint")
    sync(["cmd", "unknown"])
    assert "No device named" in str(fail_mock.call_args[0][0])


def test_setup_sudoers_success(mock_client, mocker):
    fprint_mock = mocker.patch("synapse_installer.sync.fprint")
    setupSudoers(mock_client, "host")
    assert fprint_mock.call_count == 1
    assert "Sudoers rule added" in str(fprint_mock.call_args[0][0])


def test_setup_sudoers_failure(mock_client, mocker):
    fprint_mock = mocker.patch("synapse_installer.sync.fprint")
    stderr = io.BytesIO(b"err")
    stdout = io.BytesIO(b"")
    stdout.channel = mocker.Mock()  # pyright: ignore
    stdout.channel.recv_exit_status.return_value = 0  # pyright: ignore
    mock_client.exec_command.return_value = (io.BytesIO(), stdout, stderr)
    setupSudoers(mock_client, "host")
    assert "Failed to setup sudoers" in str(fprint_mock.call_args[0][0])


def test_install_system_package_already_installed(mocker, mock_client):
    mocker.patch.object(
        mock_client,
        "exec_command",
        side_effect=[
            # command -v mgr found
            (
                io.BytesIO(),
                type(
                    "Stdout",
                    (),
                    {"channel": type("Ch", (), {"recv_exit_status": lambda _: 0})()},
                )(),
                io.BytesIO(),
            ),
            # check_cmd installed
            (
                io.BytesIO(),
                type(
                    "Stdout",
                    (),
                    {"channel": type("Ch", (), {"recv_exit_status": lambda _: 0})()},
                )(),
                io.BytesIO(),
            ),
        ],
    )
    installSystemPackage(mock_client, "pkg")


def test_install_system_package_installs(mocker, mock_client):
    mocker.patch.object(
        mock_client,
        "exec_command",
        side_effect=[
            # command -v mgr found
            (
                io.BytesIO(),
                type(
                    "Stdout",
                    (),
                    {"channel": type("Ch", (), {"recv_exit_status": lambda _: 0})()},
                )(),
                io.BytesIO(),
            ),
            # check_cmd not installed
            (
                io.BytesIO(),
                type(
                    "Stdout",
                    (),
                    {"channel": type("Ch", (), {"recv_exit_status": lambda _: 1})()},
                )(),
                io.BytesIO(),
            ),
            # install command
            (io.BytesIO(), io.BytesIO(), io.BytesIO()),
        ],
    )
    installSystemPackage(mock_client, "pkg")


def test_install_system_package_no_manager(mocker, mock_client):
    mocker.patch.object(
        mock_client,
        "exec_command",
        return_value=(
            io.BytesIO(),
            type(
                "Stdout",
                (),
                {"channel": type("Ch", (), {"recv_exit_status": lambda _: 1})()},
            )(),
            io.BytesIO(),
        ),
    )
    with pytest.raises(RuntimeError):
        installSystemPackage(mock_client, "pkg")


def make_stdout(data: bytes):
    mock_stdout = mock.Mock()
    mock_stdout.read.return_value = data
    mock_stdout.channel = mock.Mock()
    mock_stdout.channel.recv_exit_status.return_value = 0
    return mock_stdout


def make_stderr(data: bytes = b""):
    mock_stderr = mock.Mock()
    mock_stderr.read.return_value = data
    return mock_stderr


def test_install_pip_requirements(mocker, mock_client):
    mocker.patch(
        "synapse_installer.sync.getDistRequirements",
        return_value=["pkg1==1.0", "pkg2==2.0"],
    )
    mocker.patch("synapse_installer.sync.getWPILibYear", return_value=2025)

    def exec_command_side_effect(cmd, *args, **kwargs):
        if "pip freeze" in cmd:
            stdout = make_stdout(b"pkg1==1.0\n")
            stderr = make_stderr()
            return mock.Mock(), stdout, stderr
        elif "pip install" in cmd:
            stdout = make_stdout(b"")
            stderr = make_stderr()
            return mock.Mock(), stdout, stderr
        else:
            stdout = make_stdout(b"")
            stderr = make_stderr()
            return mock.Mock(), stdout, stderr

    mock_client.exec_command.side_effect = exec_command_side_effect

    fprint_mock = mocker.patch("synapse_installer.sync.fprint")

    installPipRequirements(mock_client)

    assert any("pkg1" in call.args[0] for call in fprint_mock.call_args_list), (
        "Expected fprint to be called indicating pkg1 already installed"
    )
