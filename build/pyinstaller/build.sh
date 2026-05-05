#!/usr/bin/env bash
# build/pyinstaller/build.sh — build the arcade-sim-server sidecar binary.
#
# Usage:
#   bash build/pyinstaller/build.sh          # default: dist/ at repo root
#   DIST_DIR=/tmp/dist bash build/pyinstaller/build.sh
#
# Output: $DIST_DIR/arcade-sim-server  (Linux) or arcade-sim-server.exe (Windows)
#
# Requires: Python venv at .venv with pyinstaller + all requirements installed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
PYTHON="${VENV}/bin/python"
PYINSTALLER="${VENV}/bin/pyinstaller"
DIST_DIR="${DIST_DIR:-${REPO_ROOT}/dist}"
SPEC="$REPO_ROOT/build/pyinstaller/server.spec"

# ── pre-flight checks ────────────────────────────────────────────────────────
if [[ ! -x "$PYTHON" ]]; then
    echo "error: venv not found at $VENV" >&2
    echo "       run: python -m venv .venv && pip install -r requirements.txt pyinstaller" >&2
    exit 1
fi

if [[ ! -x "$PYINSTALLER" ]]; then
    echo "==> installing pyinstaller into venv ..."
    "$PYTHON" -m pip install --quiet pyinstaller
fi

# Ensure all runtime deps are present (idempotent).
"$PYTHON" -m pip install --quiet -r "$REPO_ROOT/requirements.txt"

# ── build ─────────────────────────────────────────────────────────────────────
echo "==> building sidecar binary ..."
echo "    spec:      $SPEC"
echo "    dist:      $DIST_DIR"
echo "    workpath:  $REPO_ROOT/build/pyinstaller/work"

"$PYINSTALLER" \
    --distpath "$DIST_DIR" \
    --workpath "$REPO_ROOT/build/pyinstaller/work" \
    --noconfirm \
    "$SPEC"

BINARY="$DIST_DIR/arcade-sim-server"
if [[ ! -f "$BINARY" && ! -f "${BINARY}.exe" ]]; then
    echo "error: expected binary not found at $BINARY" >&2
    exit 1
fi

echo "==> build complete: $BINARY"
echo ""
echo "Quick smoke test:"
echo "  $BINARY --tauri-sidecar &"
echo "  PORT=\$(grep -m1 '^PORT=' /proc/\$!/fd/1 | cut -d= -f2)"
echo "  curl -s http://127.0.0.1:\$PORT/api/health"
