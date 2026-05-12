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
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

# Local import; runner.py lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
import runner  # noqa: E402
from config import load_config, save_config  # noqa: E402
from mame_client import MameClient  # noqa: E402

# Peripherals package lives one level up.
sys.path.insert(0, str(Path(__file__).parent.parent / "peripherals"))
from models import PeripheralRegistry  # noqa: E402

# Training / scenario runner.
sys.path.insert(0, str(Path(__file__).parent.parent / "training"))
import scenario_runner as _scenario_runner  # noqa: E402

# Schematic/KiCad import helpers.
sys.path.insert(0, str(Path(__file__).parent.parent / "schematic"))
try:
    from board_package import load_board_package, summarize_board_package  # noqa: E402
    from kicad_netlist import load_kicad_netlist, summarize_model  # noqa: E402
except Exception:  # noqa: BLE001
    load_board_package = None
    summarize_board_package = None
    load_kicad_netlist = None
    summarize_model = None

from flask import Flask, Response, abort, jsonify, request, send_from_directory  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402


# Repo layout. Discovered relative to this file.
HERE = Path(__file__).resolve().parent


def _bundle_root() -> Path:
    """Root directory for bundled data assets.

    In a PyInstaller --onefile build, all ``datas`` entries land under
    ``sys._MEIPASS``.  In normal development the root is the repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return HERE.parent.parent


REPO_ROOT = _bundle_root()
INSTRUMENTED_DIR = REPO_ROOT / "build" / "instrumented"
DEFAULT_TEMPLATE = INSTRUMENTED_DIR / "sync_generator.cpp"
DEFAULT_MANIFEST = INSTRUMENTED_DIR / "sync_generator.manifest.json"
DEFAULT_NLTOOL = REPO_ROOT / "vendor" / "mame" / "nltool"
UI_DIR = REPO_ROOT / "ui"

# Nets the UI plots. Tied to sync_generator.cpp; bump these if you add
# more probes to the netlist.
DEFAULT_LOG_NETS = ["HSYNC_n", "VSYNC_n"]
DEFAULT_DURATION_S = 0.001
MANIFEST_VERSION = 1

# Whitelist of xdotool key names that may be injected into the MAME window.
# Keeping this explicit prevents path-traversal / injection via the key field.
_XDOTOOL_ALLOWED_KEYS: frozenset[str] = frozenset({
    # Player controls - Centipede defaults
    "ctrl",          # P1 Button 1 (Left Control)
    # Coin / start
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    # System
    "Escape", "Return", "Tab",
    "F1", "F2", "F3", "F4", "F5", "F9",
    "p",             # pause in MAME
    # Arrow keys (MAME keyboard trackball simulation fallback)
    "Left", "Right", "Up", "Down",
})


def create_app(
    template_path: Path = DEFAULT_TEMPLATE,
    manifest_path: Path = DEFAULT_MANIFEST,
    nltool_path: Path = DEFAULT_NLTOOL,
    ui_dir: Path = UI_DIR,
    log_nets: list[str] | None = None,
    mame_client: MameClient | None = None,
    peripheral_registry: PeripheralRegistry | None = None,
    scenario_loader: Callable[[], list[dict]] | None = None,
    kicad_netlist_path: Path | None = None,
    board_package_path: Path | None = None,
) -> Flask:
    if log_nets is None:
        log_nets = DEFAULT_LOG_NETS

    app = Flask(__name__, static_folder=None)
    mame = mame_client if mame_client is not None else MameClient()
    peripherals = (
        peripheral_registry
        if peripheral_registry is not None
        else PeripheralRegistry()
    )
    trackball_diag = {
        "received": 0,
        "forwarded_ok": 0,
        "bad_payload": 0,
        "mame_unavailable": 0,
        "last_dx": 0,
        "last_dy": 0,
        "last_ok": False,
        "last_error": "",
        "last_ts": 0.0,
    }

    # Cache the manifest at boot; it's small and rarely changes.
    # Missing manifest is non-fatal — the app still starts so the UI loads.
    _manifest_error: str = ""
    if not manifest_path.exists():
        _manifest_error = (
            f"manifest not found at {manifest_path}; "
            f"run tools/preprocessor/instrument.py first"
        )
        manifest = []
    else:
        try:
            raw_manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            _manifest_error = f"failed to load manifest at {manifest_path}: {e}"
            raw_manifest = []

        # Accept only well-formed rows so /api/run never crashes while
        # normalizing request faults.
        manifest = []
        if isinstance(raw_manifest, list):
            for entry in raw_manifest:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("fault_device"):
                    continue
                manifest.append(entry)
        else:
            _manifest_error = (
                f"manifest at {manifest_path} must be a JSON list of objects"
            )
    manifest_by_refpin = {
        (e.get("refdes", ""), e.get("pin", "")): e.get("fault_device", "")
        for e in manifest
    }
    schematic_faults: dict[str, int] = {}

    # Optional board package / KiCad netlist import path (Stage 8 foundation).
    package_path = board_package_path
    if package_path is None:
        raw = os.environ.get("CABINET_BOARD_PATH", "").strip()
        package_path = Path(raw) if raw else None

    netlist_path = kicad_netlist_path
    if netlist_path is None:
        raw = os.environ.get("CABINET_KICAD_NETLIST", "").strip()
        netlist_path = Path(raw) if raw else None

    board_package = None
    schematic_model = None
    schematic_load_error = ""
    fault_map_by_refpin: dict[tuple[str, str], dict] = {}
    if package_path is not None:
        try:
            if load_board_package is None:
                raise RuntimeError("board package loader unavailable")
            board_package = load_board_package(package_path)
            fault_map_by_refpin = {
                entry.key(): {
                    "ref": entry.ref,
                    "pin": entry.pin,
                    "net_name": entry.net_name,
                    "fault_device": entry.fault_device,
                    "fault_type": entry.fault_type,
                    "description": entry.description,
                }
                for entry in board_package.fault_map
            }
        except Exception as e:  # noqa: BLE001
            schematic_load_error = str(e)
    elif netlist_path is not None:
        try:
            if load_kicad_netlist is None:
                raise RuntimeError("kicad parser unavailable")
            schematic_model = load_kicad_netlist(netlist_path)
        except Exception as e:  # noqa: BLE001
            schematic_load_error = str(e)

    _template_error: str = ""
    if not template_path.exists():
        _template_error = f"instrumented netlist not found at {template_path}"

    # In bundled builds, vendor/mame/nltool may be absent from _MEIPASS.
    # Fall back to nltool next to the configured MAME binary or PATH.
    if not nltool_path.exists():
        cfg = load_config()
        mame_bin = (
            os.environ.get("ARCADE_SIM_MAME_BINARY", "").strip()
            or cfg.get("mame_binary", "").strip()
            or shutil.which("mame")
            or ""
        )
        if mame_bin:
            candidate = Path(mame_bin).resolve().parent / "nltool"
            if candidate.exists():
                nltool_path = candidate

    _nltool_error: str = ""
    if not nltool_path.exists():
        _nltool_error = (
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
            "manifest_version": MANIFEST_VERSION,
            "fault_targets": manifest,
            "log_nets": log_nets,
            "duration_s": DEFAULT_DURATION_S,
            "modes": runner.MODE_LABELS,
        })

    @app.errorhandler(Exception)
    def api_error_handler(err: Exception):
        # Ensure API clients never receive Flask's HTML error page.
        if request.path.startswith("/api/"):
            if isinstance(err, HTTPException):
                return jsonify({"error": err.description}), int(err.code or 500)
            return jsonify({"error": f"internal server error: {err}"}), 500
        if isinstance(err, HTTPException):
            return err
        raise err

    @app.errorhandler(404)
    def api_not_found(err):
        # Return JSON for /api/* 404s instead of HTML.
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return err

    @app.route("/api/run", methods=["POST"])
    def api_run():
        body = request.get_json(silent=True) or {}
        faults_in = body.get("faults", {}) or {}
        # Normalize: only allow keys that appear in the manifest.
        manifest_devices = {
            e.get("fault_device") for e in manifest
            if isinstance(e, dict) and e.get("fault_device")
        }
        faults = dict(schematic_faults)
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
        except FileNotFoundError as e:
            return jsonify({"error": str(e), "hint": _nltool_error or _template_error}), 503
        except subprocess.TimeoutExpired:  # type: ignore[name-defined]
            return jsonify({"error": "nltool timed out"}), 504
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"simulation failed: {e}"}), 500

        return jsonify({
            "waveforms": runner.waveforms_to_json(result.waveforms),
            "duration_s": result.duration_s,
            "fault_mode_count": result.fault_mode_count,
            "schematic_fault_count": len([m for m in schematic_faults.values() if m != 0]),
            "stderr_tail": result.stderr.splitlines()[-5:],
        })

    # ---------- Health check (Phase 9 sidecar contract) ----------

    @app.route("/api/health")
    def api_health():
        bid = None
        if board_package is not None:
            bid = board_package.board_id
        return jsonify({"status": "ok", "board_id": bid})

    @app.route("/api/mame/runtime_info")
    def api_mame_runtime_info():
        """Report MAME binary + ROM path discovery state.

        Used by the Tauri first-run dialog to decide whether to show the
        MAME path picker.  Never raises; returns safe defaults if anything
        is misconfigured.
        """
        import shutil
        cfg = load_config()
        mame_bin = cfg["mame_binary"] or shutil.which("mame") or ""
        mame_found = bool(mame_bin and Path(mame_bin).is_file())
        return jsonify({
            "mame_found": mame_found,
            "mame_path": mame_bin or None,
            "rom_path": cfg["rom_path"] or None,
            "display": cfg["display"] or _resolve_mame_display(),
        })

    # ---------- Schematic import + click-to-fault foundations ----------

    @app.route("/api/schematic/summary")
    def api_schematic_summary():
        if board_package is not None:
            if summarize_board_package is None:
                return jsonify({"available": False, "error": "board package summary unavailable"}), 500
            return jsonify({"available": True, **summarize_board_package(board_package)})
        if schematic_model is None:
            return jsonify({
                "available": False,
                "error": schematic_load_error or "no schematic source loaded",
                "hint": "set CABINET_BOARD_PATH to a board.json path or CABINET_KICAD_NETLIST to a KiCad XML netlist path",
            }), 404
        if summarize_model is None:
            return jsonify({"available": False, "error": "summary unavailable"}), 500
        return jsonify({"available": True, **summarize_model(schematic_model)})

    @app.route("/api/schematic/faults")
    def api_schematic_faults():
        return jsonify({"faults": schematic_faults})

    @app.route("/api/schematic/fault/apply", methods=["POST"])
    def api_schematic_fault_apply():
        body = request.get_json(silent=True) or {}
        refdes = str(body.get("refdes") or body.get("ref") or "").strip()
        pin = str(body.get("pin", "")).strip()
        if not refdes or not pin:
            return jsonify({"error": "ref/refdes and pin are required"}), 400
        try:
            mode = int(body.get("mode", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "mode must be integer"}), 400
        if mode not in runner.MODE_LABELS:
            return jsonify({"error": f"unsupported mode: {mode}"}), 400

        fault_entry = fault_map_by_refpin.get((refdes, pin), {})
        fault_device = fault_entry.get("fault_device") or manifest_by_refpin.get((refdes, pin), "")
        if not fault_device:
            return jsonify({
                "error": f"no instrumented fault target for {refdes}.{pin}",
                "hint": "instrument the target net and map it in fault_map.json so it appears in the board package",
            }), 404

        if mode == 0:
            schematic_faults.pop(fault_device, None)
        else:
            schematic_faults[fault_device] = mode

        return jsonify({
            "ok": True,
            "refdes": refdes,
            "ref": refdes,
            "pin": pin,
            "fault_device": fault_device,
            "mode": mode,
            "label": runner.MODE_LABELS[mode],
            "fault": fault_entry or None,
            "active_faults": schematic_faults,
        })

    @app.route("/api/schematic/fault/clear", methods=["POST"])
    def api_schematic_fault_clear():
        body = request.get_json(silent=True) or {}
        refdes = str(body.get("refdes") or body.get("ref") or "").strip()
        pin = str(body.get("pin", "")).strip()
        if refdes and pin:
            fault_entry = fault_map_by_refpin.get((refdes, pin), {})
            fault_device = fault_entry.get("fault_device") or manifest_by_refpin.get((refdes, pin), "")
            if not fault_device:
                return jsonify({"error": f"no instrumented fault target for {refdes}.{pin}"}), 404
            schematic_faults.pop(fault_device, None)
            return jsonify({"ok": True, "faults": schematic_faults})

        schematic_faults.clear()
        return jsonify({"ok": True, "faults": schematic_faults})

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
        # Clear all injected faults so the reset starts clean.
        schematic_faults.clear()
        try:
            mame.clear_stuck()
        except ConnectionError:
            pass
        try:
            mame.clear_buttons()
        except ConnectionError:
            pass
        try:
            mame.set_crt_fault("normal", 1.0)
        except ConnectionError:
            pass
        peripherals.reset_all()
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

    @app.route("/api/mame/press_button", methods=["POST"])
    def api_mame_press_button():
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        if not name:
            return jsonify({"error": "missing 'name'"}), 400
        try:
            reply = mame.press_button(name)
            return jsonify({"available": True, **reply})
        except ConnectionError as e:
            return jsonify({"available": False, "error": str(e)}), 503

    @app.route("/api/mame/release_button", methods=["POST"])
    def api_mame_release_button():
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        if not name:
            return jsonify({"error": "missing 'name'"}), 400
        try:
            reply = mame.release_button(name)
            return jsonify({"available": True, **reply})
        except ConnectionError as e:
            return jsonify({"available": False, "error": str(e)}), 503

    @app.route("/api/mame/clear_buttons", methods=["POST"])
    def api_mame_clear_buttons():
        return _mame_request("clear_buttons")

    @app.route("/api/mame/list_buttons")
    def api_mame_list_buttons():
        return _mame_request("list_buttons")

    @app.route("/api/mame/trackball_delta", methods=["POST"])
    def api_mame_trackball_delta():
        trackball_diag["received"] += 1
        body = request.get_json(silent=True) or {}
        try:
            dx = int(body.get("dx", 0))
            dy = int(body.get("dy", 0))
        except (TypeError, ValueError):
            trackball_diag["bad_payload"] += 1
            trackball_diag["last_ok"] = False
            trackball_diag["last_error"] = "dx and dy must be integers"
            trackball_diag["last_ts"] = time.time()
            return jsonify({"error": "dx and dy must be integers"}), 400
        trackball_diag["last_dx"] = dx
        trackball_diag["last_dy"] = dy
        try:
            reply = mame.trackball_delta(dx, dy)
            trackball_diag["forwarded_ok"] += 1
            trackball_diag["last_ok"] = True
            trackball_diag["last_error"] = ""
            trackball_diag["last_ts"] = time.time()
            return jsonify({"available": True, **reply})
        except ConnectionError as e:
            trackball_diag["mame_unavailable"] += 1
            trackball_diag["last_ok"] = False
            trackball_diag["last_error"] = str(e)
            trackball_diag["last_ts"] = time.time()
            return jsonify({"available": False, "error": str(e)}), 503

    @app.route("/api/mame/trackball_diag")
    def api_mame_trackball_diag():
        return jsonify({
            "ok": True,
            "counts": {
                "received": trackball_diag["received"],
                "forwarded_ok": trackball_diag["forwarded_ok"],
                "bad_payload": trackball_diag["bad_payload"],
                "mame_unavailable": trackball_diag["mame_unavailable"],
            },
            "last": {
                "dx": trackball_diag["last_dx"],
                "dy": trackball_diag["last_dy"],
                "ok": trackball_diag["last_ok"],
                "error": trackball_diag["last_error"],
                "ts": trackball_diag["last_ts"],
            },
        })

    @app.route("/api/mame/xkey", methods=["POST"])
    def api_mame_xkey():
        """Inject a keyboard event directly into the MAME X11 window via xdotool.

        Body: {"action": "keydown"|"keyup"|"key", "key": "<xdotool_keyname>"}

        This bypasses the Lua TCP plugin entirely, giving MAME the same input
        it would receive from a real keyboard attached to the Xvfb display.
        Only keys listed in _XDOTOOL_ALLOWED_KEYS are accepted.
        """
        body = request.get_json(silent=True) or {}
        action = str(body.get("action", "key")).strip()
        key = str(body.get("key", "")).strip()
        if action not in ("keydown", "keyup", "key"):
            return jsonify({"error": "action must be keydown, keyup, or key"}), 400
        if not key or key not in _XDOTOOL_ALLOWED_KEYS:
            return jsonify({"error": "key not in allowed list"}), 400
        display = _resolve_mame_display()
        if not display:
            return jsonify({"error": "no MAME display configured"}), 503
        try:
            # For atomic "key" presses, add --delay 50ms so MAME's input
            # polling loop sees the press before the release arrives.
            cmd = ["xdotool", action]
            if action == "key":
                cmd += ["--delay", "50"]
            cmd += ["--clearmodifiers", key]
            subprocess.Popen(
                cmd,
                env={**os.environ, "DISPLAY": display},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return jsonify({"ok": True, "action": action, "key": key})
        except OSError as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/mame/xmouse", methods=["POST"])
    def api_mame_xmouse():
        """Move the virtual mouse on the MAME display (trackball = mouse in MAME).

        Body: {"dx": int, "dy": int}

        MAME maps IPT_TRACKBALL_X/Y to the mouse by default, so sending
        relative mouse moves via xdotool produces smooth trackball movement
        with no polarity bugs and no Lua round-trip overhead.
        """
        body = request.get_json(silent=True) or {}
        try:
            dx = int(body.get("dx", 0))
            dy = int(body.get("dy", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "dx and dy must be integers"}), 400
        dx = max(-500, min(500, dx))
        dy = max(-500, min(500, dy))
        if dx == 0 and dy == 0:
            return jsonify({"ok": True})
        display = _resolve_mame_display()
        if not display:
            return jsonify({"error": "no MAME display configured"}), 503
        try:
            subprocess.Popen(
                ["xdotool", "mousemove_relative", "--", str(dx), str(dy)],
                env={**os.environ, "DISPLAY": display},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return jsonify({"ok": True, "dx": dx, "dy": dy})
        except OSError as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/mame/xcenter", methods=["POST"])
    def api_mame_xcenter():
        """Warp the Xvfb cursor to the centre of the capture area.

        Called before each click-drag gesture so the cursor has the maximum
        possible room to move in every direction before hitting a display edge.
        """
        display = _resolve_mame_display()
        if not display:
            return jsonify({"ok": True})
        parts = _capture_size().split("x")
        cx, cy = int(parts[0]) // 2, int(parts[1]) // 2
        try:
            subprocess.Popen(
                ["xdotool", "mousemove", str(cx), str(cy)],
                env={**os.environ, "DISPLAY": display},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return jsonify({"ok": True, "cx": cx, "cy": cy})
        except OSError as e:
            return jsonify({"error": str(e)}), 500

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

    @app.route("/api/mame/video")
    def api_mame_video():
        """MJPEG stream of the MAME virtual display.

        Requires MAME_DISPLAY env var pointing at an X11 display (typically
        set by run-demo.sh when Xvfb is available).  Returns 503 JSON when
        the display is not configured.  The stream is per-connection; each
        browser tab that loads the <img> tag gets its own ffmpeg instance.
        """
        display = _resolve_mame_display()
        display_target = _normalize_x11_display(display)
        if not display:
            return jsonify({
                "error": "MAME video stream not available",
                "hint": "Install xorg-server-xvfb and launch via tools/run-demo.sh",
            }), 503
        if not _ffmpeg_available():
            return jsonify({"error": "ffmpeg not found in PATH"}), 503
        window_id = _find_mame_window_id(display)
        if not _x11_grab_available(display_target):
            return jsonify({
                "error": f"display {display_target} is not capturable",
                "hint": "restart via tools/run-demo.sh so MAME and Xvfb share the same display",
            }), 503

        # Build a best-effort visual filter chain from current CRT state.
        crt_state = peripherals.crt.state()
        effect = crt_state["shader_effect"].replace("crt_", "")
        brightness = float(crt_state.get("effective_brightness", 1.0))

        def stream():
            vf_chain = _video_filter_chain(effect, brightness)
            capture_size = _capture_size()
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "quiet",
                "-f", "x11grab", "-framerate", "15",
                "-video_size", capture_size,
                "-i", display_target,
                "-vf", vf_chain,
                "-f", "mpjpeg", "-q:v", "5",
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    yield chunk
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

        return Response(
            stream(),
            mimetype="multipart/x-mixed-replace; boundary=ffmpeg",
        )

    def _ffmpeg_available() -> bool:
        import shutil
        return shutil.which("ffmpeg") is not None

    def _resolve_mame_display() -> str:
        """Best-effort display resolution for mame video capture.

        Preferred source is MAME_DISPLAY env (set by run-demo.sh).  Falls back
        to ARCADE_SIM_DISPLAY (set by Tauri before spawning the sidecar).  If
        neither is set and an Xvfb :99 process is running, falls back to :99 so
        a manual Flask restart still preserves video streaming.
        """
        disp = (
            os.environ.get("MAME_DISPLAY", "").strip()
            or os.environ.get("ARCADE_SIM_DISPLAY", "").strip()
        )
        if disp:
            return disp
        try:
            r = subprocess.run(
                ["pgrep", "-af", "Xvfb :99"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=0.8,
                check=False,
            )
            if r.returncode == 0 and (r.stdout or "").strip():
                return ":99"
        except (OSError, subprocess.TimeoutExpired):
            pass
        return ""

    def _normalize_x11_display(display: str) -> str:
        """Normalize ':99' -> ':99.0+0,0' for ffmpeg x11grab."""
        if not display:
            return ""
        if "+" in display:
            return display
        if "." not in display:
            return f"{display}.0+0,0"
        return f"{display}+0,0"

    def _capture_size() -> str:
        """Return capture size as '<w>x<h>' (defaults to portrait Centipede)."""
        raw = os.environ.get("MAME_CAPTURE_SIZE", "").strip().lower()
        if raw:
            parts = raw.split("x")
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                w = int(parts[0])
                h = int(parts[1])
                if w > 0 and h > 0:
                    return f"{w}x{h}"
        return "480x640"

    def _find_mame_window_id(display: str) -> Optional[str]:
        """Return first X11 window id for WM_CLASS 'mame' on the display."""
        if not display:
            return None
        try:
            r = subprocess.run(
                ["xdotool", "search", "--class", "mame"],
                env={**os.environ, "DISPLAY": display},
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
                check=False,
            )
            if r.returncode != 0:
                return None
            wid = (r.stdout or "").splitlines()[0].strip()
            return wid or None
        except (OSError, subprocess.TimeoutExpired, IndexError):
            return None

    def _x11_grab_available(display_target: str) -> bool:
        """Return True when ffmpeg can capture at least one frame from display."""
        if not display_target or not _ffmpeg_available():
            return False
        try:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "x11grab", "-video_size", "16x16",
                "-i", display_target,
                "-frames:v", "1",
                "-f", "null", "-",
            ]
            r = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
            return r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _video_filter_chain(effect: str, brightness: float) -> str:
        """Build ffmpeg -vf chain for browser preview CRT effects.

        This is a fallback visual path for the embedded video panel when
        MAME's Lua UI overlay is not visible in the captured output.
        """
        # Global brightness scale from CRT/PSU model.
        filters: list[str] = []
        b = max(0.0, min(1.2, brightness))
        if abs(b - 1.0) > 0.01:
            # ffmpeg eq brightness is additive in [-1,1].
            filters.append(f"eq=brightness={max(-1.0, min(1.0, b - 1.0)):.3f}")

        if effect == "no_hv":
            filters.append("eq=brightness=-1:saturation=0")
        elif effect == "vertical_collapse":
            filters.append("scale=iw:ih*0.08:flags=neighbor,pad=iw:ih:(ow-iw)/2:(oh-ih)/2:black")
        elif effect == "horizontal_collapse":
            filters.append("scale=iw*0.08:ih:flags=neighbor,pad=iw:ih:(ow-iw)/2:(oh-ih)/2:black")
        elif effect == "dim_picture":
            filters.append("eq=brightness=-0.35")
        elif effect == "weak_focus":
            filters.append("gblur=sigma=1.2")
        elif effect == "ringing_ghosting":
            filters.append("tblend=all_mode=average")
        elif effect == "sync_lock_failure":
            # Cheap approximation: slight jitter via horizontal shear.
            filters.append("shear=xh=0.05")

        # Always scale to a stable panel size matching capture dimensions.
        filters.append(f"scale={_capture_size().replace('x', ':')}:flags=neighbor")
        return ",".join(filters)

    @app.route("/api/mame/video/available")
    def api_mame_video_available():
        """Quick probe: is the video stream available?"""
        display = _resolve_mame_display()
        display_target = _normalize_x11_display(display)
        window_id = _find_mame_window_id(display)
        ffmpeg_ok = _ffmpeg_available()
        grab_ok = _x11_grab_available(display_target) if display and ffmpeg_ok else False
        return jsonify({
            "available": bool(display) and ffmpeg_ok and grab_ok,
            "display": display_target or None,
            "window_id": window_id,
            "ffmpeg": ffmpeg_ok,
            "grab": grab_ok,
        })

    @app.route("/api/crt/apply", methods=["POST"])
    def api_crt_apply():
        """Push the current CRT fault state into MAME's UI overlay.

        Reads the CRT peripheral state (respecting PSU coupling) and sends a
        set_crt_fault command to the MAME plugin so the game framebuffer
        shows the matching visual effect immediately.

        Optionally accepts {effect, brightness} in the request body to
        override the peripheral state (useful for scenario direct-apply).
        """
        body = request.get_json(silent=True) or {}
        if "effect" in body:
            effect = str(body["effect"])
            brightness = float(body.get("brightness", 1.0))
        else:
            crt_state = peripherals.crt.state()
            effect = crt_state["shader_effect"].replace("crt_", "")
            if effect == "normal":
                effect = "normal"
            brightness = crt_state["effective_brightness"]
        try:
            reply = mame.set_crt_fault(effect, brightness)
            return jsonify({"available": True, "effect": effect,
                            "brightness": brightness, "mame": reply})
        except ConnectionError as e:
            return jsonify({"available": False, "effect": effect,
                            "brightness": brightness, "error": str(e)}), 503

    # ------------------------------------------------------------------
    # PSU fault propagation
    # A background thread watches the PSU rail and pushes CRT + stuck-byte
    # updates into MAME whenever the 5 V rail deviates from nominal.
    # ------------------------------------------------------------------

    _psu_watcher_stop = threading.Event()

    def _psu_watcher_loop():
        """Push PSU-coupled CRT state to MAME once per second."""
        prev_fault = None
        prev_brightness = None
        # Centipede work-RAM range used to inject transient errors on low 5 V.
        TRANSIENT_ADDR = 0x0700  # scratch RAM, typically zeroed by game init
        transient_armed = False
        while not _psu_watcher_stop.wait(timeout=1.0):
            try:
                crt_state = peripherals.crt.state()
                effect = crt_state["shader_effect"].replace("crt_", "")
                if effect == "normal":
                    effect = "normal"
                brightness = crt_state["effective_brightness"]
                rail_5v = peripherals.psu.state()["rails"]["5V"]

                # Only push to MAME when state changes, to avoid spamming.
                if effect != prev_fault or abs(brightness - (prev_brightness or 0)) > 0.02:
                    prev_fault = effect
                    prev_brightness = brightness
                    try:
                        mame.set_crt_fault(effect, brightness)
                    except ConnectionError:
                        pass  # MAME not running yet; silently skip

                # Arm a transient stuck byte when 5 V sags below 4.7 V.
                if rail_5v < 4.7 and not transient_armed:
                    try:
                        mame.stuck_byte(TRANSIENT_ADDR, 0xFF)
                        transient_armed = True
                    except ConnectionError:
                        pass
                elif rail_5v >= 4.7 and transient_armed:
                    try:
                        mame.stuck_byte(TRANSIENT_ADDR, None)
                        transient_armed = False
                    except ConnectionError:
                        pass
            except Exception:  # noqa: BLE001
                pass  # never crash the watcher; log silently

    _watcher_thread = threading.Thread(
        target=_psu_watcher_loop, daemon=True, name="psu_watcher"
    )
    _watcher_thread.start()

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    # Load all scenarios at startup so we can serve the list immediately.
    load_scenarios = (
        scenario_loader if scenario_loader is not None
        else _scenario_runner.load_all_scenarios
    )
    _scenarios: list[dict] = load_scenarios()
    _scenario_index: dict[str, dict] = {s["id"]: s for s in _scenarios}

    @app.route("/api/scenarios")
    def api_scenarios_list():
        """Return metadata for all available scenarios."""
        return jsonify({
            "scenarios": [_scenario_runner.scenario_metadata(s) for s in _scenarios]
        })

    @app.route("/api/scenarios/<scenario_id>/apply", methods=["POST"])
    def api_scenario_apply(scenario_id: str):
        """Apply all faults in the named scenario.

        Peripheral faults are applied in-process (no HTTP round-trip).
        MAME-level faults (stuck_byte, clear_stuck, crt_overlay) are forwarded
        to the MAME plugin; they return {available: false} gracefully if MAME
        isn't running.
        """
        scenario = _scenario_index.get(scenario_id)
        if scenario is None:
            return jsonify({"error": f"unknown scenario: {scenario_id!r}"}), 404
        mame_pre = _ensure_mame_running()
        results = _apply_scenario_faults(scenario["faults"])
        return jsonify({"id": scenario_id, "applied": True, "faults": results, "mame": mame_pre})

    @app.route("/api/scenarios/<scenario_id>/clear", methods=["POST"])
    def api_scenario_clear(scenario_id: str):
        """Clear all faults from the named scenario."""
        scenario = _scenario_index.get(scenario_id)
        if scenario is None:
            return jsonify({"error": f"unknown scenario: {scenario_id!r}"}), 404
        mame_pre = _ensure_mame_running()
        results = _apply_scenario_faults(scenario.get("clear_faults", []))
        return jsonify({"id": scenario_id, "cleared": True, "faults": results, "mame": mame_pre})

    def _ensure_mame_running() -> dict:
        """Best-effort: if MAME is paused, try to resume before applying faults."""
        try:
            st = mame.get_state()
            was_paused = bool(st.get("paused"))
            resumed = False
            if was_paused:
                try:
                    mame.resume()
                    resumed = True
                except ConnectionError:
                    resumed = False
            return {"available": True, "was_paused": was_paused, "resume_attempted": was_paused, "resumed": resumed}
        except ConnectionError as e:
            return {"available": False, "error": str(e)}

    def _apply_scenario_faults(fault_list: list) -> list:
        """Apply a list of fault dicts in-process. Returns per-fault outcomes."""
        results = []
        for fault in fault_list:
            fault_type = fault.get("type", "peripheral")
            try:
                if fault_type == "peripheral":
                    peripherals.apply_fault(fault["target"], fault["fault"])
                    result: dict = {"type": fault_type, "target": fault["target"], "ok": True}
                    if fault["target"].startswith("CRT"):
                        reached = _push_crt_to_mame()
                        result["mame_available"] = reached
                        if not reached:
                            result["warning"] = "CRT state updated but MAME is not connected"
                    results.append(result)

                elif fault_type == "mame_stuck_byte":
                    raw_addr = fault["addr"]
                    addr = int(raw_addr, 0) if isinstance(raw_addr, str) else int(raw_addr)
                    try:
                        mame.stuck_byte(addr, int(fault["value"]))
                        results.append({"type": fault_type, "addr": raw_addr,
                                        "ok": True})
                    except ConnectionError as e:
                        results.append({"type": fault_type, "addr": raw_addr,
                                        "ok": False, "available": False,
                                        "error": str(e)})

                elif fault_type == "mame_clear_stuck":
                    try:
                        mame.clear_stuck()
                        results.append({"type": fault_type, "ok": True})
                    except ConnectionError as e:
                        results.append({"type": fault_type, "ok": False,
                                        "available": False, "error": str(e)})

                elif fault_type == "crt_overlay":
                    effect = fault.get("effect", "normal")
                    brightness = float(fault.get("brightness", 1.0))
                    try:
                        mame.set_crt_fault(effect, brightness)
                        results.append({"type": fault_type, "effect": effect,
                                        "ok": True})
                    except ConnectionError as e:
                        results.append({"type": fault_type, "effect": effect,
                                        "ok": False, "available": False,
                                        "error": str(e)})
                else:
                    results.append({"type": fault_type, "ok": False,
                                    "error": f"unknown fault type: {fault_type!r}"})
            except (ValueError, KeyError) as e:
                results.append({"type": fault_type, "ok": False, "error": str(e)})
        return results

    def _push_crt_to_mame() -> bool:
        """Push the current CRT peripheral state to MAME.  Returns True if MAME was reached."""
        try:
            crt_state = peripherals.crt.state()
            effect = crt_state["shader_effect"].replace("crt_", "")
            mame.set_crt_fault(effect, crt_state["effective_brightness"])
            return True
        except ConnectionError:
            return False

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
    parser.add_argument("--board-package", type=Path, default=None)
    parser.add_argument("--kicad-netlist", type=Path, default=None)
    parser.add_argument(
        "--tauri-sidecar",
        action="store_true",
        help=(
            "Sidecar mode for Tauri desktop app: bind on a random available port "
            "and write 'PORT=<n>' to stdout so the Tauri shell can discover it."
        ),
    )
    args = parser.parse_args(argv)

    if args.tauri_sidecar:
        import socket as _socket
        with _socket.socket() as _s:
            _s.bind(("127.0.0.1", 0))
            args.port = _s.getsockname()[1]
        # Write the port to stdout so Tauri's sidecar API can read it.
        print(f"PORT={args.port}", flush=True)

    app = create_app(
        board_package_path=args.board_package,
        kicad_netlist_path=args.kicad_netlist,
    )
    if not args.tauri_sidecar:
        print(f"Cabinet bus listening on http://{args.host}:{args.port}",
              file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    # subprocess imported for type-only use above.
    import subprocess  # noqa: F401
    main()
