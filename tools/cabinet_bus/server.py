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
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Local import; runner.py lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
import runner  # noqa: E402
from mame_client import MameClient  # noqa: E402

# Peripherals package lives one level up.
sys.path.insert(0, str(Path(__file__).parent.parent / "peripherals"))
from models import PeripheralRegistry  # noqa: E402

# Training / scenario runner.
sys.path.insert(0, str(Path(__file__).parent.parent / "training"))
import scenario_runner as _scenario_runner  # noqa: E402

from flask import Flask, Response, abort, jsonify, request, send_from_directory  # noqa: E402


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

    @app.route("/api/mame/video")
    def api_mame_video():
        """MJPEG stream of the MAME virtual display.

        Requires MAME_DISPLAY env var pointing at an X11 display (typically
        set by run-demo.sh when Xvfb is available).  Returns 503 JSON when
        the display is not configured.  The stream is per-connection; each
        browser tab that loads the <img> tag gets its own ffmpeg instance.
        """
        display = os.environ.get("MAME_DISPLAY", "")
        display_target = _normalize_x11_display(display)
        if not display:
            return jsonify({
                "error": "MAME video stream not available",
                "hint": "Install xorg-server-xvfb and launch via tools/run-demo.sh",
            }), 503
        if not _ffmpeg_available():
            return jsonify({"error": "ffmpeg not found in PATH"}), 503
        window_id = _find_mame_window_id(display)
        if not window_id:
            return jsonify({
                "error": "MAME window not found on display",
                "hint": "ensure MAME is running and opened on the configured display",
            }), 503
        if not _x11_grab_available(display_target, window_id):
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
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "quiet",
                "-f", "x11grab", "-framerate", "15",
                "-window_id", window_id,
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

    def _normalize_x11_display(display: str) -> str:
        """Normalize ':99' -> ':99.0+0,0' for ffmpeg x11grab."""
        if not display:
            return ""
        if "+" in display:
            return display
        if "." not in display:
            return f"{display}.0+0,0"
        return f"{display}+0,0"

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

    def _x11_grab_available(display_target: str, window_id: Optional[str] = None) -> bool:
        """Return True when ffmpeg can capture at least one frame from display."""
        if not display_target or not _ffmpeg_available():
            return False
        try:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "x11grab",
            ]
            if window_id:
                cmd += ["-window_id", str(window_id)]
            else:
                cmd += ["-video_size", "16x16"]
            cmd += [
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

        # Always scale to a stable panel size.
        filters.append("scale=640:480:flags=neighbor")
        return ",".join(filters)

    @app.route("/api/mame/video/available")
    def api_mame_video_available():
        """Quick probe: is the video stream available?"""
        display = os.environ.get("MAME_DISPLAY", "")
        display_target = _normalize_x11_display(display)
        window_id = _find_mame_window_id(display)
        ffmpeg_ok = _ffmpeg_available()
        grab_ok = _x11_grab_available(display_target, window_id) if display and ffmpeg_ok else False
        return jsonify({
            "available": bool(display) and bool(window_id) and ffmpeg_ok and grab_ok,
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
                # In headless/Xvfb runs MAME may auto-pause on focus loss.
                # Force it back to running so scenario effects are visible.
                try:
                    st = mame.get_state()
                    if bool(st.get("paused")):
                        mame.resume()
                except ConnectionError:
                    pass

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
    _scenarios: list[dict] = _scenario_runner.load_all_scenarios()
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
    args = parser.parse_args(argv)

    app = create_app()
    print(f"Cabinet bus listening on http://{args.host}:{args.port}",
          file=sys.stderr)
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    # subprocess imported for type-only use above.
    import subprocess  # noqa: F401
    main()
