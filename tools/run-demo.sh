#!/usr/bin/env bash
# Arcade Cabinet Fault Simulator — unified launcher.
#
# Starts MAME running Centipede with the cabinet_bus plugin loaded, AND
# starts the Flask cabinet-bus server hosting the UI. Ctrl-C in this
# terminal kills both.
#
# After both are up, open http://127.0.0.1:5050 in a browser. The MAME
# window also pops up; the cabinet_bus plugin opens a TCP listener on
# 127.0.0.1:5051 that the Flask server talks to.
#
# To inject a stuck-pixel fault into the live MAME frame, see
# tools/demo-stuck-pixel.sh, or hit /api/mame/stuck_byte directly with
# curl. See the README for the full list of fault primitives.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
VENV="$REPO_ROOT/.venv"
MAME_DIR="$REPO_ROOT/vendor/mame"
ROM_DIR="$REPO_ROOT/roms"
ROM_NAME="${ROM_NAME:-centiped3}"
SERVER_PORT="${SERVER_PORT:-5050}"
MAME_PORT="${MAME_PORT:-5051}"

# Sanity checks.
if [[ ! -x "$MAME_DIR/mame" ]]; then
    echo "error: MAME not built at $MAME_DIR/mame" >&2
    echo "       run 'make -j3 SOURCES=src/mame/atari/centiped.cpp TOOLS=1' in $MAME_DIR" >&2
    exit 1
fi
if [[ ! -f "$ROM_DIR/${ROM_NAME}.zip" ]]; then
    echo "error: ROM not found at $ROM_DIR/${ROM_NAME}.zip" >&2
    exit 1
fi
if [[ ! -d "$VENV" ]]; then
    echo "error: Python venv not found at $VENV — see README.md bootstrap section" >&2
    exit 1
fi
if ss -ltn 2>/dev/null | grep -qE "[: ]$MAME_PORT[ ]"; then
    echo "warning: port $MAME_PORT already in use; MAME plugin will likely fail to bind" >&2
fi
if ss -ltn 2>/dev/null | grep -qE "[: ]$SERVER_PORT[ ]"; then
    echo "warning: port $SERVER_PORT already in use; Flask server will fail to bind" >&2
fi

MAME_PID=""
SERVER_PID=""
cleanup() {
    if [[ -n "$MAME_PID" ]] && kill -0 "$MAME_PID" 2>/dev/null; then
        echo "" >&2
        echo "==> stopping MAME (pid $MAME_PID)" >&2
        kill "$MAME_PID" 2>/dev/null || true
        wait "$MAME_PID" 2>/dev/null || true
    fi
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "==> starting MAME ($ROM_NAME with cabinet_bus plugin)"
(
    cd "$MAME_DIR"
    exec ./mame \
        -rompath "$ROM_DIR" \
        -plugin cabinet_bus \
        "$ROM_NAME"
) &
MAME_PID=$!

# Wait briefly for MAME's TCP listener to come up. The plugin opens its
# socket inside startplugin(), which fires after the machine is booted —
# usually within a couple of seconds, but can be longer the first time
# MAME compiles its discrete sound chains.
echo "==> waiting for cabinet_bus plugin on 127.0.0.1:$MAME_PORT (up to 30s)"
for i in $(seq 1 60); do
    if ss -ltn 2>/dev/null | grep -qE "[: ]$MAME_PORT[ ]"; then
        echo "    ok"
        break
    fi
    if ! kill -0 "$MAME_PID" 2>/dev/null; then
        echo "error: MAME exited before opening the listener" >&2
        exit 1
    fi
    sleep 0.5
done

echo "==> starting cabinet bus server on http://127.0.0.1:$SERVER_PORT"
echo "    UI:           http://127.0.0.1:$SERVER_PORT"
echo "    MAME state:   curl -s http://127.0.0.1:$SERVER_PORT/api/mame/state | jq"
echo "    Stuck pixel:  $HERE/demo-stuck-pixel.sh"
echo "    Ctrl-C to stop both."
echo ""

cd "$REPO_ROOT"
"$VENV/bin/python" -m tools.cabinet_bus.server --host 127.0.0.1 --port "$SERVER_PORT" &
SERVER_PID=$!

wait "$SERVER_PID"
