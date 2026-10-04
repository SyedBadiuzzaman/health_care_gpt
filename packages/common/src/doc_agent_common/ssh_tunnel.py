"""Manage the existing SSH path to PostgreSQL."""

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from typing import Self

from doc_agent_common.config import AppSettings


@dataclass
class SshTunnel:
    """Open a local-only PostgreSQL forward for one process."""

    settings: AppSettings
    process: subprocess.Popen[bytes] | None = None

    async def __aenter__(self) -> Self:
        if not self.settings.use_ssh_tunnel:
            return self
        for path, label in (
            (self.settings.ssh_key_path, "SSH private key"),
            (self.settings.ssh_known_hosts_path, "SSH known_hosts file"),
        ):
            if not path.is_file():
                raise RuntimeError(f"The {label} does not exist.")

        forward = (
            f"127.0.0.1:{self.settings.tunnel_local_port}:"
            f"127.0.0.1:{self.settings.database_port}"
        )
        command = [
            "ssh",
            "-N",
            "-L",
            forward,
            "-i",
            str(self.settings.ssh_key_path),
            "-o",
            "BatchMode=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={self.settings.ssh_known_hosts_path}",
            f"{self.settings.ssh_user}@{self.settings.database_host}",
        ]
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = await asyncio.to_thread(
            subprocess.Popen,
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        await self._wait_until_ready()
        return self

    async def _wait_until_ready(self) -> None:
        """Wait until the forwarded port accepts connections or SSH exits."""
        assert self.process is not None
        for _ in range(40):
            if self.process.poll() is not None:
                raise RuntimeError("The SSH database tunnel could not start.")
            try:
                _, writer = await asyncio.open_connection(
                    "127.0.0.1", self.settings.tunnel_local_port
                )
            except OSError:
                await asyncio.sleep(0.1)
                continue
            writer.close()
            await writer.wait_closed()
            return
        await self.close()
        raise RuntimeError("The SSH database tunnel did not become ready.")

    async def close(self) -> None:
        """Stop the forwarding process without affecting the SSH server."""
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            await asyncio.to_thread(self.process.wait, 5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            await asyncio.to_thread(self.process.wait)

    async def __aexit__(self, *_: object) -> None:
        await self.close()
