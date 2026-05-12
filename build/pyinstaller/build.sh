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
DIST_DIR="${DIST_DIR:-${REPO_ROOT}/dist}"
SPEC="$REPO_ROOT/build/pyinstaller/server.spec"

# Support both POSIX venv layout (.venv/bin/python) and Windows layout
# (.venv/Scripts/python.exe) when invoked from Git Bash on CI runners.
if [[ -x "${VENV}/bin/python" ]]; then
    PYTHON="${VENV}/bin/python"
elif [[ -x "${VENV}/Scripts/python.exe" ]]; then
    PYTHON="${VENV}/Scripts/python.exe"
else
    PYTHON=""
fi

# ── pre-flight checks ────────────────────────────────────────────────────────
if [[ ! -x "$PYTHON" ]]; then
    echo "error: venv not found at $VENV" >&2
    echo "       run: python -m venv .venv && pip install -r requirements.txt pyinstaller" >&2
    exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
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

"$PYTHON" -m PyInstaller \
    --distpath "$DIST_DIR" \
    --workpath "$REPO_ROOT/build/pyinstaller/work" \
    --noconfirm \
    "$SPEC"

BINARY="$DIST_DIR/arcade-sim-server"
if [[ ! -f "$BINARY" && ! -f "${BINARY}.exe" ]]; then
    echo "error: expected binary not found at $BINARY" >&2
    exit 1
fi

# Tauri sidecar lookup requires the binary to also exist with the target-triple
# suffix (e.g. arcade-sim-server-x86_64-unknown-linux-gnu).  Copy it now so
# `cargo tauri build` bundles the real ELF rather than the dev stub.
case "$(uname -s)" in
    Linux)
        TARGET_TRIPLE="${BINARY}-x86_64-unknown-linux-gnu"
        cp "$BINARY" "$TARGET_TRIPLE"
        echo "==> copied to $TARGET_TRIPLE"
        ;;
    Darwin)
        cp "$BINARY" "${BINARY}-x86_64-apple-darwin"
        echo "==> copied to ${BINARY}-x86_64-apple-darwin"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        WINDOWS_BINARY="${BINARY}.exe"
        if [[ -f "$WINDOWS_BINARY" ]]; then
            cp "$WINDOWS_BINARY" "${BINARY}-x86_64-pc-windows-msvc.exe"
            echo "==> copied to ${BINARY}-x86_64-pc-windows-msvc.exe"
        fi
        ;;
esac

echo "==> build complete: $BINARY"
echo ""
echo "Quick smoke test:"
echo "  $BINARY --tauri-sidecar &"
echo "  PORT=\$(grep -m1 '^PORT=' /proc/\$!/fd/1 | cut -d= -f2)"
echo "  curl -s http://127.0.0.1:\$PORT/api/health"
