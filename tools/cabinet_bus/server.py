#!/usr/bin/env python3
# license:CC0-1.0
"""
Cabinet-bus HTTP server.

Hosts the minimal UI and exposes JSON endpoints for fault injection.
Run via tools/cabinet_bus/start.sh; defaults to http://127.0.0.1:5050.

Endpoints:
  GET  /                  → static index.html
  GET  /static/<file>     → app.js, style.css
  GET  /api/manifest      → fault-injection targets + run config
  POST /api/run           → run a scenario, return waveforms JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Local import; runner.py lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
import runner  # noqa: E402
from mame_client import MameClient  # noqa: E402

# Peripherals package lives one level up.
sys.path.insert(0, str(Path(__file__).parent.parent / "peripherals"))
from models import PeripheralRegistry  # noqa: E402

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402


# Repo layout. Discovered relative to this file.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
INSTRUMENTED_DIR = REPO_ROOT / "build" / "instrumented"
DEFAULT_TEMPLATE = INSTRUMENTED_DIR / "sync_generator.cpp"
DEFAULT_MANIFEST = INSTRUMENTED_DIR / "sync_generator.manifest.json"
DEFAULT_NLTOOL = REPO_ROOT / "vendor" / "mame" / "nltool"
UI_DIR = REPO_ROOT / "ui"

# Nets the UI plots. Tied to sync_generator.cpp; bump these if you add
# more probes to the netlist.
DEFAULT_LOG_NETS = ["HSYNC_n", "VSYNC_n"]
DEFAULT_DURATION_S = 0.001


def create_app(
    template_path: Path = DEFAULT_TEMPLATE,
    manifest_path: Path = DEFAULT_MANIFEST,
    nltool_path: Path = DEFAULT_NLTOOL,
    ui_dir: Path = UI_DIR,
    log_nets: list[str] | None = None,
) -> Flask:
    if log_nets is None:
        log_nets = DEFAULT_LOG_NETS

    app = Flask(__name__, static_folder=None)
    mame = MameClient()
    peripherals = PeripheralRegistry()

    # Cache the manifest at boot; it's small and rarely changes.
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"manifest not found at {manifest_path}; "
            f"run tools/preprocessor/instrument.py first"
        )
    manifest = json.loads(manifest_path.read_text())

    if not template_path.exists():
        raise FileNotFoundError(
            f"instrumented netlist not found at {template_path}"
        )
    if not nltool_path.exists():
        raise FileNotFoundError(
            f"nltool not built at {nltool_path}; "
            f"run `make -j3 SOURCES=src/mame/atari/centiped.cpp TOOLS=1` "
            f"in vendor/mame"
        )

    @app.route("/")
    def index():
        return send_from_directory(ui_dir, "index.html")

    @app.route("/static/<path:filename>")
    def static_file(filename):
        # Restrict to the ui/ directory so we don't serve random files.
        return send_from_directory(ui_dir, filename)

    @app.route("/api/manifest")
    def api_manifest():
        return jsonify({
            "fault_targets": manifest,
            "log_nets": log_nets,
            "duration_s": DEFAULT_DURATION_S,
            "modes": runner.MODE_LABELS,
        })

    @app.route("/api/run", methods=["POST"])
    def api_run():
        body = request.get_json(silent=True) or {}
        faults_in = body.get("faults", {}) or {}
        # Normalize: only allow keys that appear in the manifest.
        manifest_devices = {e["fault_device"] for e in manifest}
        faults = {}
        for k, v in faults_in.items():
            if k not in manifest_devices:
                return jsonify({"error": f"unknown fault device: {k}"}), 400
            try:
                faults[k] = int(v)
            except (TypeError, ValueError):
                return jsonify({"error": f"mode must be int, got {v!r}"}), 400

        duration = float(body.get("duration_s", DEFAULT_DURATION_S))
        # Bound the request: never let the UI ask for >50ms — that gets
        # expensive and the demo doesn't need it.
        duration = max(1e-5, min(duration, 0.05))

        spec = runner.RunSpec(
            template_path=template_path,
            nltool_path=nltool_path,
            log_nets=log_nets,
            faults=faults,
            duration_s=duration,
        )
        try:
            result = runner.run(spec)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except subprocess.TimeoutExpired:  # type: ignore[name-defined]
            return jsonify({"error": "nltool timed out"}), 504

        return jsonify({
            "waveforms": runner.waveforms_to_json(result.waveforms),
            "duration_s": result.duration_s,
            "fault_mode_count": result.fault_mode_count,
            "stderr_tail": result.stderr.splitlines()[-5:],
        })

    # ---------- MAME bridge ----------
    # All endpoints below proxy to the cabinet_bus Lua plugin running
    # inside MAME. They return 503 with `{available: false}` when MAME
    # isn't reachable; the UI uses that to hide the panel gracefully.

    def _mame_request(cmd: str):
        try:
            method = getattr(mame, cmd)
            reply = method()
            return jsonify({"available": True, **reply})
        except ConnectionError as e:
            return jsonify({"available": False, "error": str(e)}), 503
        except Exception as e:  # noqa: BLE001
            return jsonify({"available": True, "ok": False, "error": str(e)}), 502

    @app.route("/api/mame/state")
    def api_mame_state():
        return _mame_request("get_state")

    @app.route("/api/mame/ping")
    def api_mame_ping():
        return _mame_request("ping")

    @app.route("/api/mame/pause", methods=["POST"])
    def api_mame_pause():
        return _mame_request("pause")

    @app.route("/api/mame/resume", methods=["POST"])
    def api_mame_resume():
        return _mame_request("resume")

    @app.route("/api/mame/soft_reset", methods=["POST"])
    def api_mame_reset():
        return _mame_request("soft_reset")

    # Centipede video-RAM map (centiped_state::centiped_base_map):
    #   0x0400-0x07BF = 32 cols x 30 rows of tile indices, byte-per-cell.
    # Translating (col, row) -> address lets the UI pin a stuck tile to
    # an exact on-screen location regardless of what the game writes.
    CENTIPED_VRAM_BASE = 0x0400
    CENTIPED_VRAM_COLS = 32
    CENTIPED_VRAM_ROWS = 30

    def _vram_addr_for(col: int, row: int) -> int:
        if not (0 <= col < CENTIPED_VRAM_COLS):
            raise ValueError(f"col out of range 0..{CENTIPED_VRAM_COLS - 1}")
        if not (0 <= row < CENTIPED_VRAM_ROWS):
            raise ValueError(f"row out of range 0..{CENTIPED_VRAM_ROWS - 1}")
        return CENTIPED_VRAM_BASE + row * CENTIPED_VRAM_COLS + col

    @app.route("/api/mame/poke_ram", methods=["POST"])
    def api_mame_poke_ram():
        body = request.get_json(silent=True) or {}
        try:
            raw_addr = body["addr"]
            raw_val = body["value"]
            addr = int(raw_addr, 0) if isinstance(raw_addr, str) else int(raw_addr)
            value = int(raw_val, 0) if isinstance(raw_val, str) else int(raw_val)
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "addr and value (int) are required"}), 400
        cpu = body.get("cpu") or "maincpu"
        try:
            reply = mame.poke_ram(addr, value, cpu)
            return jsonify({"available": True, **reply})
        except ConnectionError as e:
            return jsonify({"available": False, "error": str(e)}), 503

    @app.route("/api/mame/stuck_byte", methods=["POST"])
    def api_mame_stuck_byte():
        """Arm or clear a per-frame stuck-at fault.

        Body fields (one of two forms):
          {addr: int|hex, value: int|null, cpu?: str}
          {col: int, row: int, value: int|null}    # Centipede VRAM helper

        Pass value=null to clear the fault.
        """
        body = request.get_json(silent=True) or {}
        cpu = body.get("cpu") or "maincpu"
        try:
            if "col" in body and "row" in body:
                addr = _vram_addr_for(int(body["col"]), int(body["row"]))
            else:
                raw = body.get("addr")
                if raw is None:
                    raise ValueError("addr or (col,row) is required")
                addr = int(raw, 0) if isinstance(raw, str) else int(raw)
        except (TypeError, ValueError) as e:
            return jsonify({"error": str(e)}), 400
        raw_value = body.get("value")
        if raw_value is None:
            value: Optional[int] = None
        else:
            try:
                value = int(raw_value, 0) if isinstance(raw_value, str) else int(raw_value)
            except (TypeError, ValueError):
                return jsonify({"error": "value must be int or null"}), 400
        try:
            reply = mame.stuck_byte(addr, value, cpu)
            return jsonify({"available": True, "addr_resolved": addr, **reply})
        except ConnectionError as e:
            return jsonify({"available": False, "error": str(e)}), 503

    @app.route("/api/mame/clear_stuck", methods=["POST"])
    def api_mame_clear_stuck():
        return _mame_request("clear_stuck")

    # ---------- Peripherals ----------
    # In-process registry of cabinet-level peripherals (PSU, coin mech,
    # buttons, marquee, harness segments). Faults applied here are pure
    # state changes; the UI renders the resulting state. Phase 5+ work
    # will couple PSU rail voltage back into the netlist solver.

    @app.route("/api/peripherals/state")
    def api_peripherals_state():
        return jsonify({"peripherals": peripherals.all()})

    @app.route("/api/peripherals/fault", methods=["POST"])
    def api_peripherals_fault():
        body = request.get_json(silent=True) or {}
        ident = body.get("id")
        fault = body.get("fault", "")
        if not ident:
            return jsonify({"error": "missing 'id'"}), 400
        try:
            return jsonify(peripherals.apply_fault(ident, fault))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/peripherals/adjust", methods=["POST"])
    def api_peripherals_adjust():
        body = request.get_json(silent=True) or {}
        ident = body.get("id")
        param = body.get("param")
        value = body.get("value")
        if not ident or not param:
            return jsonify({"error": "missing 'id' or 'param'"}), 400
        try:
            return jsonify(peripherals.adjust(ident, param, value))
        except (ValueError, TypeError) as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/peripherals/reset", methods=["POST"])
    def api_peripherals_reset():
        peripherals.reset_all()
        return jsonify({"peripherals": peripherals.all()})

    @app.route("/api/peripherals/coin", methods=["POST"])
    def api_peripherals_coin():
        """Drop a coin into the coin mech (action endpoint, not a fault)."""
        peripherals.coin.insert_coin()
        return jsonify(peripherals.coin.state())

    @app.route("/api/crt/preview")
    def api_crt_preview():
        """Expose CRT state for the standalone preview pane."""
        return jsonify(peripherals.crt.state())

    @app.route("/api/trackball/motion", methods=["POST"])
    def api_trackball_motion():
        body = request.get_json(silent=True) or {}
        try:
            dx = int(body.get("dx", 0))
            dy = int(body.get("dy", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "dx and dy must be integers"}), 400

        packet = peripherals.trackball.apply_motion(dx, dy)

        # Direct push mode: forward immediately to the MAME bridge.
        try:
            mame_reply = mame.trackball_delta(packet["quad_dx"], packet["quad_dy"])
            return jsonify({"available": True, "packet": packet, "mame": mame_reply})
        except ConnectionError as e:
            return jsonify({"available": False, "packet": packet, "error": str(e)}), 503

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cabinet_bus.server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    app = create_app()
    print(f"Cabinet bus listening on http://{args.host}:{args.port}",
          file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    # subprocess imported for type-only use above.
    import subprocess  # noqa: F401
    main()
