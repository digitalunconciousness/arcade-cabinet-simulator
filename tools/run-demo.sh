#!/usr/bin/env bash
# Arcade Cabinet Fault Simulator — unified launcher.
#
# Starts MAME (Centipede + cabinet_bus plugin) and the Flask UI server.
# Ctrl-C in this terminal stops both processes.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
VENV="$REPO_ROOT/.venv"
MAME_DIR="$REPO_ROOT/vendor/mame"
ROM_DIR="$REPO_ROOT/roms"
ROM_NAME="${ROM_NAME:-centiped3}"
SERVER_PORT="${SERVER_PORT:-5050}"
MAME_PORT="${MAME_PORT:-5051}"
XVFB_GEOMETRY="${XVFB_GEOMETRY:-480x640x24}"

IFS='x' read -r XVFB_W XVFB_H XVFB_D <<< "$XVFB_GEOMETRY"
if [[ -z "${XVFB_W:-}" || -z "${XVFB_H:-}" || -z "${XVFB_D:-}" ]]; then
    echo "error: XVFB_GEOMETRY must be WxHxD (example: 480x640x24)" >&2
    exit 1
fi
MAME_CAPTURE_SIZE="${MAME_CAPTURE_SIZE:-${XVFB_W}x${XVFB_H}}"

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
if ! command -v ffmpeg &>/dev/null; then
    echo "error: ffmpeg not found in PATH" >&2
    echo "       install ffmpeg; /api/mame/video requires it for MJPEG streaming" >&2
    exit 1
fi
if ! command -v Xvfb &>/dev/null; then
    echo "error: Xvfb not found in PATH" >&2
    echo "       install with: sudo pacman -S xorg-server-xvfb" >&2
    exit 1
fi
if ss -ltn 2>/dev/null | grep -qE "[: ]$MAME_PORT[ ]"; then
    echo "error: port $MAME_PORT already in use; stop existing MAME/cabinet_bus first" >&2
    ss -ltnp | grep -E ":$MAME_PORT\\b" || true
    exit 1
fi
if ss -ltn 2>/dev/null | grep -qE "[: ]$SERVER_PORT[ ]"; then
    echo "error: port $SERVER_PORT already in use; stop existing server first" >&2
    ss -ltnp | grep -E ":$SERVER_PORT\\b" || true
    exit 1
fi

XVFB_PID=""
MAME_PID=""
SERVER_PID=""

cleanup() {
    if [[ -n "$XVFB_PID" ]] && kill -0 "$XVFB_PID" 2>/dev/null; then
        kill "$XVFB_PID" 2>/dev/null || true
        wait "$XVFB_PID" 2>/dev/null || true
    fi
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

# Run MAME on a deterministic virtual display so /api/mame/video is reliable.
MAME_DISPLAY=":99"
if pgrep -af "Xvfb :99" >/dev/null; then
    echo "==> restarting existing virtual display :99 to enforce ${XVFB_GEOMETRY}"
    pkill -f "Xvfb :99" || true
    sleep 0.2
elif [[ -e "/tmp/.X99-lock" ]]; then
    echo "error: :99 is locked but not by Xvfb :99" >&2
    echo "       clear stale lock or stop the conflicting X server, then retry" >&2
    exit 1
fi

echo "==> starting virtual display :99 (Xvfb ${XVFB_GEOMETRY})"
Xvfb ":99" -screen 0 "$XVFB_GEOMETRY" -ac >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
sleep 0.5
if ! kill -0 "$XVFB_PID" 2>/dev/null; then
    echo "error: Xvfb failed to start on :99" >&2
    echo "       see /tmp/xvfb.log for details" >&2
    exit 1
fi
echo "    game video stream enabled at /api/mame/video"

export MAME_DISPLAY
export MAME_CAPTURE_SIZE

echo "==> starting MAME ($ROM_NAME with cabinet_bus plugin)"
(
    cd "$MAME_DIR"
    DISPLAY="$MAME_DISPLAY" SDL_VIDEODRIVER=x11 WAYLAND_DISPLAY= exec ./mame \
        -rompath "$ROM_DIR" \
        -plugin cabinet_bus \
        -video soft \
        -window \
        -resolution "$MAME_CAPTURE_SIZE" \
        -nomaximize \
        -background_input \
        -mouse \
        -update_in_pause \
        -skip_gameinfo \
        "$ROM_NAME"
) &
MAME_PID=$!

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
echo "    Scenarios:    curl -s http://127.0.0.1:$SERVER_PORT/api/scenarios | jq"
echo "    Ctrl-C to stop both."
echo ""

cd "$REPO_ROOT"
MAME_DISPLAY="$MAME_DISPLAY" "$VENV/bin/python" -m tools.cabinet_bus.server --host 127.0.0.1 --port "$SERVER_PORT" &
SERVER_PID=$!

sleep 1
if command -v xdg-open &>/dev/null; then
    xdg-open "http://127.0.0.1:$SERVER_PORT" &>/dev/null &
elif command -v open &>/dev/null; then
    open "http://127.0.0.1:$SERVER_PORT" &>/dev/null &
else
    echo "    (open http://127.0.0.1:$SERVER_PORT in your browser)"
fi

wait "$SERVER_PID"
