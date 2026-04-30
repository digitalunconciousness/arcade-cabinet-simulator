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

# Local import; runner.py lives next to this file.
sys.path.insert(0, str(Path(__file__).parent))
import runner  # noqa: E402
from mame_client import MameClient  # noqa: E402

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
