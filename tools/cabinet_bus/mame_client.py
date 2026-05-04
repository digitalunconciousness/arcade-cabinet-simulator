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
import threading
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
        self._recv_buffer: bytes = b""
        # Flask serves requests in multiple threads; serialize socket I/O so
        # requests cannot race and consume each other's replies.
        self._io_lock = threading.Lock()

    def close(self) -> None:
        with self._io_lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            self._recv_buffer = b""

    def is_available(self) -> bool:
        """Quick reachability probe. Returns True if we have or can open a connection."""
        with self._io_lock:
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
        with self._io_lock:
            for attempt in (1, 2):
                try:
                    self._ensure_connection()
                    assert self._sock is not None
                    self._sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
                    line = self._readline()
                    return json.loads(line.decode("utf-8"))
                except (ConnectionResetError, BrokenPipeError, TimeoutError) as e:
                    if self._sock is not None:
                        try:
                            self._sock.close()
                        except OSError:
                            pass
                        self._sock = None
                    self._recv_buffer = b""
                    if attempt == 2:
                        raise ConnectionError(
                            f"MAME plugin connection lost: {e}"
                        ) from e
                except OSError as e:
                    if self._sock is not None:
                        try:
                            self._sock.close()
                        except OSError:
                            pass
                        self._sock = None
                    self._recv_buffer = b""
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

    def poke_ram(self, addr: int, value: int, cpu: str = "maincpu") -> dict:
        """One-shot byte write to the named CPU's program space.

        For game-managed regions like VRAM the running game will overwrite
        within a frame; use stuck_byte() instead for persistent faults.
        """
        return self.send({
            "cmd": "poke_ram",
            "addr": int(addr),
            "value": int(value),
            "cpu": cpu,
        })

    def stuck_byte(
        self,
        addr: int,
        value: Optional[int],
        cpu: str = "maincpu",
    ) -> dict:
        """Arm or clear a per-frame stuck-at fault on a memory cell.

        Pass value=None to clear the fault on this address. Otherwise the
        plugin re-writes value to addr on every emulator frame, so the
        running game can never overwrite it. Same fault model as the
        BAD_RAM_CELL netlist device, applied at the MAME-CPU layer.
        """
        cmd: dict = {"cmd": "stuck_byte", "addr": int(addr), "cpu": cpu}
        cmd["value"] = None if value is None else int(value)
        return self.send(cmd)

    def clear_stuck(self) -> dict:
        """Disarm every armed stuck-byte fault."""
        return self.send({"cmd": "clear_stuck"})

    def trackball_delta(self, dx: int, dy: int) -> dict:
        """Push one quadrature-friendly trackball delta packet to MAME."""
        return self.send({
            "cmd": "trackball_delta",
            "dx": int(dx),
            "dy": int(dy),
        })

    def press_button(self, name: str) -> dict:
        """Hold a digital ioport button by its MAME field name (e.g. 'P1 Fire')."""
        return self.send({"cmd": "press_button", "name": str(name)})

    def release_button(self, name: str) -> dict:
        """Release a previously held digital ioport button."""
        return self.send({"cmd": "release_button", "name": str(name)})

    def clear_buttons(self) -> dict:
        """Release all held buttons at once."""
        return self.send({"cmd": "clear_buttons"})

    def list_buttons(self) -> dict:
        """Return all available button field names for the current game."""
        return self.send({"cmd": "list_buttons"})

    def set_crt_fault(self, effect: str, brightness: float = 1.0) -> dict:
        """Set the active CRT overlay in the running MAME session.

        effect:     CRT fault name (e.g. "dim_picture") or "normal" to clear.
        brightness: effective brightness multiplier 0.0..1.2; values below 1.0
                    add an additional dark veil on top of the named effect.
        """
        return self.send({
            "cmd": "set_crt_fault",
            "effect": str(effect),
            "brightness": float(brightness),
        })

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

    def _readline(self) -> bytes:
        """Read exactly one newline-delimited reply, preserving overflow bytes."""
        assert self._sock is not None
        while b"\n" not in self._recv_buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                self.close()
                raise ConnectionResetError("MAME closed the connection")
            self._recv_buffer += chunk
            if len(self._recv_buffer) > 256 * 1024:
                self.close()
                raise ValueError("reply buffer exceeds 256KB; protocol desync?")
        line, _, rest = self._recv_buffer.partition(b"\n")
        self._recv_buffer = rest
        return line


__all__ = ["MameClient", "MameClientConfig"]
