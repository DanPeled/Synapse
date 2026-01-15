# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import time
from typing import Iterator, Optional

import paramiko
from paramiko.channel import Channel


class JournalctlNotAvailableError(RuntimeError):
    pass


class SshConnectionError(RuntimeError):
    pass


class SystemdServiceLogStreamer:
    def __init__(
        self,
        sshClient: paramiko.SSHClient,
        service: str,
        useSudo: bool = False,
        userService: bool = False,
    ) -> None:
        self.sshClient: paramiko.SSHClient = sshClient
        self.service: str = service
        self.useSudo: bool = useSudo
        self.userService: bool = userService

        transport = self.sshClient.get_transport()
        if transport is None or not transport.is_active():
            raise SshConnectionError("SSH client is not connected")

    def connect(self) -> None:
        self._checkJournalctl()

    def stream(self) -> Iterator[str]:
        """
        Generator yielding log lines (stdout + stderr).
        """
        channel = self._openChannel(self._buildJournalctlCommand())
        assert channel is not None

        buffer: str = ""

        try:
            while True:
                if channel.recv_ready():
                    data: str = channel.recv(4096).decode(errors="replace")
                    buffer += data

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        yield line

                elif channel.exit_status_ready():
                    break
                else:
                    time.sleep(0.05)
        finally:
            channel.close()

    def _checkJournalctl(self) -> None:
        channel = self._openChannel("command -v journalctl")
        assert channel is not None

        exitCode: int = channel.recv_exit_status()
        channel.close()

        if exitCode != 0:
            raise JournalctlNotAvailableError(
                "journalctl is not installed on the remote host"
            )

    def _openChannel(self, command: str) -> Optional[Channel]:
        transport = self.sshClient.get_transport()
        if transport is not None:
            channel: Channel = transport.open_session()
            channel.exec_command(command)
            return channel
        return None

    def _buildJournalctlCommand(self) -> str:
        parts: list[str] = ["journalctl"]

        if self.userService:
            parts.append("--user")

        parts += ["-u", self.service, "--output=cat", "-f"]

        cmd: str = " ".join(shlex.quote(p) for p in parts)

        if self.useSudo:
            cmd = f"sudo -n {cmd}"

        return cmd
