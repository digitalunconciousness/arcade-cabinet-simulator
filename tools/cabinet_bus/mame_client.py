#!/usr/bin/env python3
# license:CC0-1.0
"""
Tiny socket client for the MAME cabinet_bus Lua plugin.

The plugin (vendor/mame/plugins/cabinet_bus/init.lua) opens a TCP listener
on 127.0.0.1:5051 and accepts newline-terminated JSON commands. This module
wraps that protocol so the Flask server can issue pause/resume/state calls
without caring about socket plumbing.

Connection is persistent and guarded by a lock so the Flask server can issue
commands from multiple threads without reply mixups.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class MameClientConfig:
    host: str = "127.0.0.1"
    port: int = 5051
    timeout_s: float = 2.0


class MameClient:
    """Persistent JSON-line client for the MAME plugin.

    MAME's `emu.file` socket abstraction only accepts one connection at a
    time — when the client closes its socket, MAME's listener may need to
    reopen. This client keeps one long-lived TCP connection and reconnects
    only when the connection actually breaks.
    """

    def __init__(self, config: Optional[MameClientConfig] = None):
        self.config = config or MameClientConfig()
        self._sock: Optional[socket.socket] = None
        self._recv_buffer: bytes = b""
        self._io_lock = threading.Lock()

    def _close_unlocked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._recv_buffer = b""

    def close(self) -> None:
        with self._io_lock:
            self._close_unlocked()

    def is_available(self) -> bool:
        """Quick reachability probe."""
        with self._io_lock:
            try:
                self._ensure_connection()
                return True
            except OSError:
                return False

    def send(self, cmd: dict) -> dict:
        """Send one command and return decoded JSON reply."""
        with self._io_lock:
            for attempt in (1, 2):
                try:
                    self._ensure_connection()
                    assert self._sock is not None
                    self._sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
                    line = self._readline_unlocked()
                    return json.loads(line.decode("utf-8"))
                except (ConnectionResetError, BrokenPipeError, TimeoutError) as e:
                    self._close_unlocked()
                    if attempt == 2:
                        raise ConnectionError(f"MAME plugin connection lost: {e}") from e
                except OSError as e:
                    self._close_unlocked()
                    if attempt == 2:
                        raise ConnectionError(
                            f"MAME plugin not reachable at {self.config.host}:{self.config.port}: {e}"
                        ) from e
        raise ConnectionError("unexpected: send loop exhausted")

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

    def poke_ram(self, addr: int, value: int, cpu: str = "maincpu") -> dict:
        return self.send({
            "cmd": "poke_ram",
            "addr": int(addr),
            "value": int(value),
            "cpu": cpu,
        })

    def stuck_byte(self, addr: int, value: Optional[int], cpu: str = "maincpu") -> dict:
        cmd: dict = {"cmd": "stuck_byte", "addr": int(addr), "cpu": cpu}
        cmd["value"] = None if value is None else int(value)
        return self.send(cmd)

    def clear_stuck(self) -> dict:
        return self.send({"cmd": "clear_stuck"})

    def trackball_delta(self, dx: int, dy: int) -> dict:
        return self.send({"cmd": "trackball_delta", "dx": int(dx), "dy": int(dy)})

    def press_button(self, name: str) -> dict:
        return self.send({"cmd": "press_button", "name": str(name)})

    def release_button(self, name: str) -> dict:
        return self.send({"cmd": "release_button", "name": str(name)})

    def clear_buttons(self) -> dict:
        return self.send({"cmd": "clear_buttons"})

    def list_buttons(self) -> dict:
        return self.send({"cmd": "list_buttons"})

    def set_crt_fault(self, effect: str, brightness: float = 1.0) -> dict:
        return self.send({
            "cmd": "set_crt_fault",
            "effect": str(effect),
            "brightness": float(brightness),
        })

    def list_dip_switches(self) -> dict:
        return self.send({"cmd": "list_dip_switches"})

    def set_dip_switch(self, port: str, name: str, value: int) -> dict:
        return self.send({
            "cmd": "set_dip_switch",
            "port": str(port),
            "name": str(name),
            "value": int(value),
        })

    def _ensure_connection(self) -> None:
        if self._sock is not None:
            return
        s = socket.create_connection((self.config.host, self.config.port), timeout=self.config.timeout_s)
        s.settimeout(self.config.timeout_s)
        self._sock = s

    def _readline_unlocked(self) -> bytes:
        assert self._sock is not None
        while b"\n" not in self._recv_buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                self._close_unlocked()
                raise ConnectionResetError("MAME closed the connection")
            self._recv_buffer += chunk
            if len(self._recv_buffer) > 256 * 1024:
                self._close_unlocked()
                raise ValueError("reply buffer exceeds 256KB; protocol desync?")
        line, _, rest = self._recv_buffer.partition(b"\n")
        self._recv_buffer = rest
        return line


__all__ = ["MameClient", "MameClientConfig"]
