#!/usr/bin/env bash
# smoke_sidecar.sh — verify the --tauri-sidecar port-handshake and /api/health endpoint.
# Usage: ./tools/cabinet_bus/smoke_sidecar.sh
# Exit code: 0 on success, 1 on failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
PYTHON="${VENV}/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "error: venv not found at $VENV — run: python -m venv .venv && pip install -r requirements.txt" >&2
    exit 1
fi

echo "==> launching sidecar with --tauri-sidecar ..."
"$PYTHON" -m tools.cabinet_bus --tauri-sidecar > /tmp/arcade_sidecar_smoke.out 2>/tmp/arcade_sidecar_smoke.err &
SIDECAR_PID=$!
trap 'kill "$SIDECAR_PID" 2>/dev/null; wait "$SIDECAR_PID" 2>/dev/null || true' EXIT

# Wait up to 10 s for PORT= line on stdout.
PORT=""
for i in $(seq 1 50); do
    if [[ -s /tmp/arcade_sidecar_smoke.out ]]; then
        PORT=$(grep -m1 '^PORT=' /tmp/arcade_sidecar_smoke.out | cut -d= -f2 | tr -d '[:space:]')
        [[ -n "$PORT" ]] && break
    fi
    sleep 0.2
done

if [[ -z "$PORT" ]]; then
    echo "FAIL: sidecar did not print PORT= within 10 s" >&2
    echo "--- stdout ---" >&2; cat /tmp/arcade_sidecar_smoke.out >&2
    echo "--- stderr ---" >&2; cat /tmp/arcade_sidecar_smoke.err >&2
    exit 1
fi

echo "==> sidecar listening on port $PORT"

# Wait for the server to become ready (another 10 s).
READY=0
for i in $(seq 1 50); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/health" 2>/dev/null || true)
    if [[ "$HTTP_CODE" == "200" ]]; then
        READY=1
        break
    fi
    sleep 0.2
done

if [[ "$READY" -eq 0 ]]; then
    echo "FAIL: /api/health did not return 200 within 10 s (last code: $HTTP_CODE)" >&2
    exit 1
fi

# Validate response body.
BODY=$(curl -s "http://127.0.0.1:${PORT}/api/health")
if ! echo "$BODY" | grep -q '"status".*"ok"'; then
    echo "FAIL: /api/health response missing {\"status\": \"ok\"}: $BODY" >&2
    exit 1
fi

echo "PASS: sidecar handshake and /api/health OK (port=$PORT, body=$BODY)"
