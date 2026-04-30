#!/usr/bin/env bash
# Activate the venv and start the cabinet-bus server.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
VENV="$REPO_ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
    echo "error: venv not found at $VENV — see README.md bootstrap section" >&2
    exit 1
fi
cd "$REPO_ROOT"
exec "$VENV/bin/python" -m tools.cabinet_bus.server "$@"
