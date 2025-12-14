# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml
from synapse_installer.deploy import (_connectAndDeploy, addDeviceConfig,
                                      deploy, loadDeviceData)
from synapse_installer.util import IsValidIP


def test_is_valid_ip():
    assert IsValidIP("192.168.0.1") is True
    assert IsValidIP("2001:0db8:85a3:0000:0000:8a2e:0370:7334") is True
    assert IsValidIP("not-an-ip") is False


@mock.patch("synapse_installer.deploy.questionary.select")
@mock.patch("synapse_installer.deploy.questionary.text")
@mock.patch("synapse_installer.deploy.questionary.password")
def test_setup_config_file_manual(mock_password, mock_text, mock_select, tmp_path):
    # Prepare mock answers
    mock_select().ask.return_value = "Manual (Provide hostname & password)"
    mock_text.side_effect = [
        mock.Mock(ask=lambda: "my-device"),  # hostname
        mock.Mock(ask=lambda: "my-device"),  # nickname
        mock.Mock(ask=lambda: "192.168.1.5"),  # IP
    ]
    mock_password().ask.return_value = "pass"

    config_path = tmp_path / "config.yml"
    addDeviceConfig(config_path)

    with open(config_path) as f:
        data = yaml.safe_load(f)

    assert "deploy" in data
    assert "my-device" in data["deploy"]
    assert data["deploy"]["my-device"]["ip"] == "192.168.1.5"


@mock.patch("synapse_installer.deploy.paramiko.SSHClient")
@mock.patch("synapse_installer.deploy.SCPClient")
@mock.patch("synapse_installer.deploy.isServiceSetup")
@mock.patch("synapse_installer.deploy.restartService")
@mock.patch("synapse_installer.deploy.setupServiceOnConnectedClient")
def test_connect_and_deploy_success(
    mock_setup, mock_restart, mock_is_setup, mock_scp, mock_ssh
):
    mock_client = mock.Mock()
    mock_transport = mock.Mock()
    mock_stdout = mock.Mock()
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr = mock.Mock()
    mock_stderr.read.return_value = b""

    mock_client.get_transport.return_value = mock_transport
    mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)
    mock_ssh.return_value = mock_client
    mock_is_setup.return_value = False

    zip_path = Path(tempfile.mktemp(suffix=".zip"))
    zip_path.write_text("dummy")

    _connectAndDeploy("host", "1.2.3.4", "pwd", [zip_path])

    mock_scp.assert_called_once()
    mock_setup.assert_called_once()
    mock_restart.assert_called_once()


@mock.patch("synapse_installer.deploy._connectAndDeploy")
def test_deploy_runs_connect_deploy(mock_connect, tmp_path, monkeypatch):
    deploy_cfg = tmp_path / "config.yaml"
    deploy_cfg.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "deploy": {
            "my-device": {"hostname": "host", "ip": "1.2.3.4", "password": "pwd"}
        }
    }
    with open(deploy_cfg, "w") as f:
        yaml.dump(data, f)

    project_zip = tmp_path / "build" / "project.zip"
    package_zip = tmp_path / "build" / "synapse.zip"
    project_zip.parent.mkdir(exist_ok=True)
    project_zip.write_text("data")
    package_zip.write_text("data")

    monkeypatch.setattr(sys, "argv", ["deploy", "my-device"])

    deploy(deploy_cfg, tmp_path, None)

    mock_connect.assert_called_once()


@mock.patch("synapse_installer.deploy.addDeviceConfig")
def test_load_device_data_errors_when_missing(mock_setup, tmp_path):
    path = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        loadDeviceData(path)

    mock_setup.assert_not_called()


@mock.patch("synapse_installer.deploy.addDeviceConfig")
def test_load_device_data_creates_when_empty(mock_setup, tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")
    loadDeviceData(path)
    mock_setup.assert_called_once_with(path)
