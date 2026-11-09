# license:CC0-1.0
"""Smoke test for Sim Control Protocol v1 (plugin/cabsim/server.lua).

Starts MAME headless with CABSIM_PORT set, then drives a fault through the
socket the way the app will: hello, apply, list, clear, input. Works with
any romset the driver runs, including the test ROM.

  python -m tools.cabsim.scp_smoke --mame vendor/mame/mame --rompath roms --romset centiped3
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .mame import PLUGIN_DIR


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, port: int, timeout: float = 5.0):
        deadline = time.monotonic() + 30
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        self.file = self.sock.makefile("rwb")
        self.n = 0

    def call(self, cmd: str, **kw) -> dict:
        self.n += 1
        req = {"cmd": cmd, "req": self.n, **kw}
        self.file.write((json.dumps(req) + "\n").encode())
        self.file.flush()
        reply = json.loads(self.file.readline())
        if reply.get("req") != self.n:
            raise AssertionError(f"reply out of order: {reply}")
        return reply


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mame", type=Path, required=True)
    ap.add_argument("--rompath", type=Path, required=True)
    ap.add_argument("--romset", default="centiped3")
    args = ap.parse_args(argv)

    port = free_port()
    work = Path(tempfile.mkdtemp(prefix="scp-"))
    env = dict(os.environ, CABSIM_PORT=str(port), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    env.pop("CABSIM_SCRIPT", None)
    mame = args.mame.resolve()
    proc = subprocess.Popen(
        [str(mame), args.romset, "-rompath", str(args.rompath.resolve()),
         "-pluginspath", f"{mame.parent / 'plugins'};{PLUGIN_DIR}", "-plugin", "cabsim",
         "-video", "none", "-sound", "none", "-skip_gameinfo", "-noreadconfig",
         "-cfg_directory", str(work / "cfg"), "-nvram_directory", str(work / "nv"),
         "-homepath", str(work / "home")],
        cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    checks = []

    def check(name, cond, detail):
        checks.append((name, bool(cond), detail))

    try:
        c = Client(port)
        hello = c.call("hello")
        check("hello", hello.get("ok") and hello.get("protocol") == "scp/1", hello)
        ap1 = c.call("fault.apply", primitive="reg_read_override",
                     params={"space": ":maincpu", "addr": 0x100A, "rule": {"constant": 0}})
        check("fault.apply", ap1.get("ok") and isinstance(ap1.get("id"), int) and ap1.get("tier") == "A", ap1)
        lst = c.call("fault.list")
        check("fault.list", lst.get("ok") and len(lst.get("faults", [])) == 1, lst)
        bad = c.call("fault.apply", primitive="no_such_primitive", params={})
        check("unknown primitive refused", bad.get("ok") is False and "unknown primitive" in bad.get("error", ""), bad)
        clr = c.call("fault.clear", id=ap1.get("id"))
        check("fault.clear", clr.get("ok") is True, clr)
        lst2 = c.call("fault.list")
        check("list empty after clear", lst2.get("ok") and lst2.get("faults") == [], lst2)
        btn = c.call("input.button", port=":IN1", field="Coin 1", down=True)
        check("input.button", btn.get("ok") is True, btn)
        btn2 = c.call("input.button", port=":IN1", field="Coin 1", down=False)
        check("input.button release", btn2.get("ok") is True, btn2)
        st = c.call("state")
        check("state", st.get("ok") and st.get("romset") == args.romset, st)
        unk = c.call("nope")
        check("unknown command refused", unk.get("ok") is False, unk)
    except Exception as e:  # noqa: BLE001
        check("connection", False, f"{type(e).__name__}: {e}")
    finally:
        proc.kill()
        out = proc.communicate()[0].decode(errors="replace")
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"{'ok ' if ok else 'BAD'} {name}: {detail}")
    if failed:
        print(out[-2000:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
