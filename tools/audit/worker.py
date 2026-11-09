#!/usr/bin/env python3
# license:CC0-1.0
"""Apply one legacy fault through the legacy server, in its own process.

The legacy server (create_app in tools/cabinet_bus/server.py) starts a PSU
watcher thread that can't be stopped. Running each fault in a fresh process
keeps one run's watcher from leaking commands into the next run's MAME.

Two modes:
  mame     MAME is paused at the injection frame. Build the app the way the
           shipped launchers do, apply the fault over HTTP (Flask test client),
           send the standard input stimulus, give the PSU watcher one tick,
           then resume MAME. Every plugin command and reply is logged.
  netlist  No MAME. POST each sync-generator fault to /api/run (the UI's
           waveform path) and summarise the nltool waveforms.

Resume requests the app makes on its own (scenario apply resumes a paused
MAME first) are held until injection is complete, so every fault lands on the
same emulated frame. The log marks each held request.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# The same input every run gets, baseline included: trackball motion through
# the peripheral model, the fire button, and a coin, all via the legacy API.
STIMULUS = [
    ("POST", "/api/trackball/motion", {"dx": 8, "dy": 0}),
    ("POST", "/api/trackball/motion", {"dx": 8, "dy": 0}),
    ("POST", "/api/trackball/motion", {"dx": 0, "dy": 8}),
    ("POST", "/api/mame/press_button", {"name": "P1 Button 1"}),
    ("POST", "/api/mame/release_button", {"name": "P1 Button 1"}),
    ("POST", "/api/peripherals/coin", {}),
    ("POST", "/api/mame/press_button", {"name": "Coin 1"}),
    ("POST", "/api/mame/release_button", {"name": "Coin 1"}),
]
PSU_WATCHER_TICK_S = 1.5


def _import_legacy(legacy_root: Path):
    sys.path.insert(0, str(legacy_root / "tools" / "cabinet_bus"))
    import mame_client  # type: ignore[import-not-found]
    import server  # type: ignore[import-not-found]
    return mame_client, server


def _recording_client(mame_client_mod, log: list, port: int):
    base = mame_client_mod.MameClient

    class RecordingClient(base):
        hold_resume = True

        def send(self, cmd: dict) -> dict:
            entry = {"t": round(time.monotonic(), 3), "cmd": cmd}
            if cmd.get("cmd") == "resume" and self.hold_resume:
                entry["held_by_audit"] = True
                log.append(entry)
                return {"ok": True, "paused": False}
            try:
                reply = super().send(cmd)
                entry["reply"] = reply
                return reply
            except Exception as e:  # noqa: BLE001
                entry["error"] = f"{type(e).__name__}: {e}"
                raise
            finally:
                if "held_by_audit" not in entry:
                    log.append(entry)

    return RecordingClient(mame_client_mod.MameClientConfig(port=port))


def _http(client, method: str, path: str, body: dict, http_log: list) -> None:
    resp = client.open(path, method=method, json=body)
    try:
        payload = resp.get_json()
    except Exception:  # noqa: BLE001
        payload = None
    http_log.append({"method": method, "path": path, "body": body,
                     "status": resp.status_code, "response": payload})


def run_mame(args) -> int:
    legacy_root = args.legacy_root.resolve()
    mame_client_mod, server = _import_legacy(legacy_root)
    plugin_log: list = []
    http_log: list = []
    client = _recording_client(mame_client_mod, plugin_log, args.port)
    entry = json.loads(args.entry) if args.entry else None

    board = None
    if entry and entry.get("config") == "board_package":
        board = legacy_root / "boards" / "centipede" / "board.json"
    app = server.create_app(mame_client=client, board_package_path=board)
    http = app.test_client()

    if entry is not None:
        a = entry["apply"]
        _http(http, a["method"], a["path"], a["body"], http_log)
    for method, path, body in STIMULUS:
        _http(http, method, path, body, http_log)
    time.sleep(PSU_WATCHER_TICK_S)

    client.hold_resume = False
    resume_error = None
    try:
        client.resume()
    except Exception as e:  # noqa: BLE001
        resume_error = f"{type(e).__name__}: {e}"

    args.log.write_text(json.dumps({
        "entry": entry,
        "http": http_log,
        "plugin": plugin_log,
        "resume_error": resume_error,
    }, indent=1))
    return 0 if resume_error is None else 2


def _summarise_wave(samples: list) -> dict:
    """Edge counts and level range of one logged net (threshold 2.5 V)."""
    if not samples:
        return {"samples": 0}
    levels = [v for _, v in samples]
    edges_falling = edges_rising = 0
    prev = levels[0] > 2.5
    for v in levels[1:]:
        cur = v > 2.5
        if prev and not cur:
            edges_falling += 1
        elif cur and not prev:
            edges_rising += 1
        prev = cur
    return {"samples": len(samples), "min_v": min(levels), "max_v": max(levels),
            "falling_edges": edges_falling, "rising_edges": edges_rising}


def run_netlist(args) -> int:
    legacy_root = args.legacy_root.resolve()
    mame_client_mod, server = _import_legacy(legacy_root)
    entries = json.loads(args.entry)
    # No MAME in this mode: point the client at a port nothing listens on.
    client = mame_client_mod.MameClient(mame_client_mod.MameClientConfig(port=1, timeout_s=0.2))
    app = server.create_app(mame_client=client, nltool_path=args.nltool.resolve())
    http = app.test_client()
    results = []
    for e in entries:
        resp = http.post("/api/run", json={"faults": e["faults"]})
        body = resp.get_json() or {}
        waves = {net: _summarise_wave(s) for net, s in (body.get("waveforms") or {}).items()}
        results.append({"id": e["id"], "faults": e["faults"], "status": resp.status_code,
                        "error": body.get("error"), "waveforms": waves})
    args.log.write_text(json.dumps(results, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["mame", "netlist"])
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--entry", default="", help="inventory entry (mame) or entry list (netlist) as JSON")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5051)
    parser.add_argument("--nltool", type=Path)
    args = parser.parse_args(argv)
    return run_mame(args) if args.mode == "mame" else run_netlist(args)


if __name__ == "__main__":
    raise SystemExit(main())
