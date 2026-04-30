#!/usr/bin/env python3
# license:CC0-1.0
"""
Tiny socket client for the MAME cabinet_bus Lua plugin.

The plugin (vendor/mame/plugins/cabinet_bus/init.lua) opens a TCP listener
on 127.0.0.1:5051 and accepts newline-terminated JSON commands. This module
wraps that protocol so the Flask server can issue pause/resume/state calls
without caring about socket plumbing.

Connection is established lazily on each request and torn down at the end.
That keeps the client stateless and tolerant of MAME being started, stopped,
and restarted while the Flask server keeps running.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Optional


@dataclass
class MameClientConfig:
    host: str = "127.0.0.1"
    port: int = 5051
    timeout_s: float = 1.0


class MameClient:
    """Persistent JSON-line client for the MAME plugin.

    MAME's `emu.file` socket abstraction only accepts one connection at a
    time — when the client closes its socket, MAME's listener is gone too.
    To work around that, this client holds one long-lived TCP connection
    across calls and only reconnects when the connection actually breaks
    (MAME exits, plugin restarts, etc.). Flask is single-threaded by
    default, so there's no contention.
    """

    def __init__(self, config: Optional[MameClientConfig] = None):
        self.config = config or MameClientConfig()
        self._sock: Optional[socket.socket] = None

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def is_available(self) -> bool:
        """Quick reachability probe. Returns True if we have or can open a connection."""
        try:
            self._ensure_connection()
            return True
        except OSError:
            return False

    def send(self, cmd: dict) -> dict:
        """Send one command, return the decoded reply.

        Auto-reconnects once on a broken connection (e.g., MAME restart).
        Raises ConnectionError if the plugin still isn't reachable.
        """
        for attempt in (1, 2):
            try:
                self._ensure_connection()
                assert self._sock is not None
                self._sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
                buf = b""
                while b"\n" not in buf:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        # Peer closed; drop and (on attempt 1) retry.
                        self.close()
                        raise ConnectionResetError("MAME closed the connection")
                    buf += chunk
                    if len(buf) > 64 * 1024:
                        self.close()
                        raise ValueError("reply exceeds 64KB; protocol desync?")
                line, _, _ = buf.partition(b"\n")
                return json.loads(line.decode("utf-8"))
            except (ConnectionResetError, BrokenPipeError, TimeoutError) as e:
                self.close()
                if attempt == 2:
                    raise ConnectionError(
                        f"MAME plugin connection lost: {e}"
                    ) from e
            except OSError as e:
                self.close()
                raise ConnectionError(
                    f"MAME plugin not reachable at "
                    f"{self.config.host}:{self.config.port}: {e}"
                ) from e
        # Unreachable; loop above either returns or raises.
        raise ConnectionError("unexpected: send loop exhausted")

    # Convenience wrappers for the supported commands.

    def ping(self) -> dict:
        return self.send({"cmd": "ping"})

    def get_state(self) -> dict:
        return self.send({"cmd": "get_state"})

    def pause(self) -> dict:
        return self.send({"cmd": "pause"})

    def resume(self) -> dict:
        return self.send({"cmd": "resume"})

    def soft_reset(self) -> dict:
        return self.send({"cmd": "soft_reset"})

    def _ensure_connection(self) -> None:
        """Open the cached socket if not already up."""
        if self._sock is not None:
            return
        s = socket.create_connection(
            (self.config.host, self.config.port),
            timeout=self.config.timeout_s,
        )
        s.settimeout(self.config.timeout_s)
        self._sock = s


__all__ = ["MameClient", "MameClientConfig"]
