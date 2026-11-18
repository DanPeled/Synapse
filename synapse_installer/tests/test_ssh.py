# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import hashlib
from pathlib import Path
from unittest import mock

import paramiko
import pytest
import synapse_installer.ssh as ssh_mod
from synapse_installer.ssh import (
    HostKeyError,
    PromptingHostKeyPolicy,
    connectSSH,
    fingerprint,
)


def test_fingerprint_is_sha256():
    key = mock.Mock()
    key.asbytes.return_value = b"key-bytes"

    expected = base64.b64encode(hashlib.sha256(b"key-bytes").digest()).decode()
    assert fingerprint(key) == f"SHA256:{expected.rstrip('=')}"


def test_policy_rejects_unknown_key_non_interactive(monkeypatch):
    key = mock.Mock()
    key.asbytes.return_value = b"key"
    policy = PromptingHostKeyPolicy(Path("/tmp/known_hosts"))

    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: False)

    with pytest.raises(HostKeyError, match="not trusted"):
        policy.missing_host_key(mock.Mock(), "robot", key)


def test_policy_rejects_declined_key(monkeypatch):
    key = mock.Mock()
    key.asbytes.return_value = b"key"
    client = mock.Mock()
    policy = PromptingHostKeyPolicy(Path("/tmp/known_hosts"))

    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        ssh_mod.questionary, "confirm", lambda *a, **k: mock.Mock(ask=lambda: False)
    )

    with pytest.raises(HostKeyError, match="was not trusted"):
        policy.missing_host_key(client, "robot", key)


def test_policy_accepts_and_saves_key(monkeypatch, tmp_path):
    key = mock.Mock()
    key.asbytes.return_value = b"key"
    key.get_name.return_value = "ssh-ed25519"
    client = mock.Mock()
    knownHosts = tmp_path / ".ssh" / "known_hosts"
    policy = PromptingHostKeyPolicy(knownHosts)

    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        ssh_mod.questionary, "confirm", lambda *a, **k: mock.Mock(ask=lambda: True)
    )

    policy.missing_host_key(client, "robot", key)

    client.get_host_keys().add.assert_called_once_with("robot", "ssh-ed25519", key)
    client.save_host_keys.assert_called_once_with(str(knownHosts))


def test_connect_ssh_success(monkeypatch):
    client = mock.Mock()
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: client)
    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: False)

    assert connectSSH("robot", "pi", "pw") is client
    client.connect.assert_called_once()
    client.load_system_host_keys.assert_called_once()


def test_connect_ssh_untrusted_key(monkeypatch):
    client = mock.Mock()
    client.connect.side_effect = paramiko.SSHException("not found in known_hosts")
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: client)
    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: False)

    with pytest.raises(HostKeyError, match="not trusted"):
        connectSSH("robot", "pi", "pw")

    client.close.assert_called_once()


def test_connect_ssh_changed_key(monkeypatch):
    client = mock.Mock()
    client.connect.side_effect = paramiko.BadHostKeyException(
        "robot", mock.Mock(), mock.Mock()
    )
    monkeypatch.setattr(ssh_mod.paramiko, "SSHClient", lambda: client)
    monkeypatch.setattr(ssh_mod.sys.stdin, "isatty", lambda: False)

    with pytest.raises(HostKeyError, match="does not match"):
        connectSSH("robot", "pi", "pw")

    client.close.assert_called_once()
