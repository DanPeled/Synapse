# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""SSH connection helpers with host-key verification.

Deploying to a robot means sending code that will run automatically, so the
installer verifies the remote host key instead of silently trusting whatever
answers on the network. When the installer is run interactively, an unknown key
is shown as a SHA-256 fingerprint and the user can choose to trust and remember
it. Non-interactive runs reject unknown keys and tell the user what to do.
"""

import base64
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional

import paramiko
import questionary
from rich import print as fprint


class HostKeyError(RuntimeError):
    """Raised when an SSH host key is missing, untrusted, or changed."""


def _knownHostsPath() -> Optional[Path]:
    try:
        return Path.home() / ".ssh" / "known_hosts"
    except RuntimeError:
        return None


def fingerprint(key: paramiko.PKey) -> str:
    """Return a short, human-readable SHA-256 fingerprint for a host key."""
    digest = hashlib.sha256(key.asbytes()).digest()
    encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{encoded}"


class PromptingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Ask before trusting an unknown host key and remember the answer."""

    def __init__(self, knownHostsPath: Optional[Path]):
        self.knownHostsPath = knownHostsPath

    def missing_host_key(
        self,
        client: paramiko.SSHClient,
        hostname: str,
        key: paramiko.PKey,
    ) -> None:
        keyFingerprint = fingerprint(key)

        if not sys.stdin.isatty():
            raise HostKeyError(
                f"Host key for {hostname} is not trusted.\n"
                f"Fingerprint: {keyFingerprint}\n"
                "Add the key to ~/.ssh/known_hosts or run the installer "
                "interactively to trust it."
            )

        fprint(
            f"[yellow]The authenticity of host '{hostname}' can't be established.[/yellow]"
        )
        fprint(f"Key fingerprint: [bold]{keyFingerprint}[/bold]")

        if not questionary.confirm(
            f"Trust this host key for {hostname}?", default=False
        ).ask():
            raise HostKeyError(f"Host key for {hostname} was not trusted.")

        client.get_host_keys().add(hostname, key.get_name(), key)
        self._saveKnownHosts(client, hostname)

    def _saveKnownHosts(self, client: paramiko.SSHClient, hostname: str) -> None:
        if self.knownHostsPath is None:
            return

        try:
            self.knownHostsPath.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            client.save_host_keys(str(self.knownHostsPath))
            os.chmod(self.knownHostsPath, 0o600)
        except OSError as error:
            fprint(
                f"[yellow]Warning: could not save the host key for {hostname}: "
                f"{error}[/yellow]"
            )


def connectSSH(
    hostname: str,
    username: str,
    password: Optional[str],
    timeout: int = 10,
    port: int = 22,
) -> paramiko.SSHClient:
    """Connect to a device while verifying its SSH host key.

    Raises:
        HostKeyError: The key is unknown in a non-interactive run, the user
            declined to trust it, or the key does not match the known one.
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()

    knownHostsPath = _knownHostsPath()
    if knownHostsPath is not None and knownHostsPath.exists():
        try:
            client.load_host_keys(str(knownHostsPath))
        except (OSError, paramiko.SSHException) as error:
            fprint(
                f"[yellow]Warning: could not read {knownHostsPath}: {error}[/yellow]"
            )

    if sys.stdin.isatty():
        client.set_missing_host_key_policy(PromptingHostKeyPolicy(knownHostsPath))
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        client.connect(
            hostname,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
    except paramiko.BadHostKeyException as error:
        client.close()
        raise HostKeyError(
            f"The SSH host key for {hostname} does not match the key in "
            "known_hosts. If the device was reflashed, remove the old key and "
            "run the installer again."
        ) from error
    except paramiko.SSHException as error:
        client.close()
        message = str(error)
        if "not found in known_hosts" in message or "No host key" in message:
            raise HostKeyError(
                f"Host key for {hostname} is not trusted.\n"
                "Add the key to ~/.ssh/known_hosts or run the installer "
                "interactively to trust it."
            ) from error
        raise

    return client
