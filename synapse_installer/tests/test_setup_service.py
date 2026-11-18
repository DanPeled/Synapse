# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import mock

import pytest
import synapse_installer.setup_service as setup_service
from synapse_installer.command_executor import RemoteCommandError
from synapse_installer.setup_service import (
    SERVICE_NAME,
    ServiceError,
    isServiceActive,
    isServiceSetup,
    restartService,
    startService,
    stopService,
    waitForServiceActive,
)


@pytest.fixture
def mock_ssh_client():
    return mock.MagicMock()


def test_is_service_setup_exists(mock_ssh_client, monkeypatch):
    run = mock.Mock(return_value=("", "", 0))
    monkeypatch.setattr(setup_service, "runCommand", run)

    assert isServiceSetup(mock_ssh_client, SERVICE_NAME) is True
    run.assert_called_once()
    assert "test -f" in run.call_args.args[1]


def test_is_service_setup_missing(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(
        setup_service, "runCommand", mock.Mock(return_value=("", "", 1))
    )

    assert isServiceSetup(mock_ssh_client, SERVICE_NAME) is False


def test_restart_service(mock_ssh_client, monkeypatch):
    run = mock.Mock(return_value=("service restarted", "", 0))
    monkeypatch.setattr(setup_service, "runCommand", run)

    stdout, stderr = restartService(mock_ssh_client, SERVICE_NAME)

    assert "service restarted" in stdout
    assert stderr == ""
    assert run.call_args.args[1] == f"sudo -n systemctl restart {SERVICE_NAME}"


def test_restart_service_failure_raises(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(
        setup_service, "runCommand", mock.Mock(return_value=("", "nope", 1))
    )

    with pytest.raises(ServiceError, match="Restart"):
        restartService(mock_ssh_client, SERVICE_NAME)


def test_restart_service_remote_error_raises(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(
        setup_service,
        "runCommand",
        mock.Mock(side_effect=RemoteCommandError("denied")),
    )

    with pytest.raises(ServiceError, match="denied"):
        restartService(mock_ssh_client, SERVICE_NAME)


def test_is_service_active(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(
        setup_service, "runCommand", mock.Mock(return_value=("", "", 0))
    )
    assert isServiceActive(mock_ssh_client, SERVICE_NAME) is True

    monkeypatch.setattr(
        setup_service, "runCommand", mock.Mock(return_value=("", "", 3))
    )
    assert isServiceActive(mock_ssh_client, SERVICE_NAME) is False


def test_start_service(mock_ssh_client, monkeypatch):
    run = mock.Mock(return_value=("", "", 0))
    monkeypatch.setattr(setup_service, "runCommand", run)

    startService(mock_ssh_client, SERVICE_NAME)

    assert run.call_args.args[1] == f"sudo -n systemctl start {SERVICE_NAME}"


def test_stop_service_skips_when_inactive(mock_ssh_client, monkeypatch):
    run = mock.Mock(return_value=("", "", 3))
    monkeypatch.setattr(setup_service, "runCommand", run)

    assert stopService(mock_ssh_client, SERVICE_NAME) is False
    assert run.call_count == 1


def test_stop_service_stops_when_active(mock_ssh_client, monkeypatch):
    run = mock.Mock(return_value=("", "", 0))
    monkeypatch.setattr(setup_service, "runCommand", run)

    assert stopService(mock_ssh_client, SERVICE_NAME) is True

    commands = [call.args[1] for call in run.call_args_list]
    assert any("is-active" in command for command in commands)
    assert any("systemctl stop" in command for command in commands)


def test_wait_for_service_active_succeeds(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(
        setup_service, "isServiceActive", mock.Mock(side_effect=[False, True])
    )
    monkeypatch.setattr(setup_service.time, "sleep", mock.Mock())

    waitForServiceActive(mock_ssh_client, SERVICE_NAME, timeout=5.0, interval=0)


def test_wait_for_service_active_times_out(mock_ssh_client, monkeypatch):
    monkeypatch.setattr(setup_service, "isServiceActive", mock.Mock(return_value=False))
    monkeypatch.setattr(setup_service.time, "sleep", mock.Mock())

    with pytest.raises(ServiceError, match="did not become active"):
        waitForServiceActive(mock_ssh_client, SERVICE_NAME, timeout=0.01, interval=0)
