#!/usr/bin/env bash
# Arcade Cabinet Fault Simulator — stuck-pixel demo.
#
# Pins one cell of Centipede's video RAM to a fixed tile index so a
# garbage tile shows up in the same on-screen position every frame —
# the textbook "one bad RAM cell" symptom every arcade tech recognizes.
#
# Requires tools/run-demo.sh to be running already (so MAME and the
# cabinet bus are up).
#
# Usage:
#   tools/demo-stuck-pixel.sh                       # default: col 16 row 12, value 0xFF
#   tools/demo-stuck-pixel.sh --col 5 --row 8 --value 65
#   tools/demo-stuck-pixel.sh --clear               # disarm all stuck-byte faults
#   tools/demo-stuck-pixel.sh --addr 0x05D0 --value 0xAA
#
# What it does:
#   POST /api/mame/stuck_byte  with {col, row, value}
# which the cabinet bus translates to a Centipede VRAM address
# (0x0400 + row*32 + col) and the MAME plugin re-writes that byte to
# `value` on every emulator frame.

set -euo pipefail

SERVER_URL="${SERVER_URL:-http://127.0.0.1:5050}"
COL=16
ROW=12
VALUE=255          # 0xFF: a recognizable corrupt tile in Centipede's tilemap
ADDR=""
ACTION="arm"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --col)    COL="$2"; shift 2 ;;
        --row)    ROW="$2"; shift 2 ;;
        --value)  VALUE="$2"; shift 2 ;;
        --addr)   ADDR="$2"; shift 2 ;;
        --clear)  ACTION="clear"; shift ;;
        --url)    SERVER_URL="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,30p' "$0"; exit 0 ;;
        *) echo "unknown flag: $1" >&2; exit 1 ;;
    esac
done

if [[ "$ACTION" == "clear" ]]; then
    curl -s -X POST "$SERVER_URL/api/mame/clear_stuck"; echo
    exit 0
fi

if [[ -n "$ADDR" ]]; then
    BODY=$(printf '{"addr":"%s","value":%s}' "$ADDR" "$VALUE")
else
    BODY=$(printf '{"col":%s,"row":%s,"value":%s}' "$COL" "$ROW" "$VALUE")
fi

echo "==> arming stuck-byte: $BODY"
curl -s -X POST -H "content-type: application/json" \
    "$SERVER_URL/api/mame/stuck_byte" -d "$BODY"; echo
echo ""
echo "Look at the MAME window — a stuck tile should now appear at"
echo "(col=$COL, row=$ROW). To clear it: $0 --clear"
