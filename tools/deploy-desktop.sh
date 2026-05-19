#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="${DEST_DIR:-$HOME/Applications}"

# Prefer the real AppImage bundle produced by `cargo tauri build` (via
# build-release.sh).  Fall back to the raw ELF from `cargo build --release`
# so quick iteration builds still work.
APPIMAGE_BUNDLE=$(find "$ROOT_DIR/src-tauri/target/release/bundle/appimage" \
    -maxdepth 1 -name "*.AppImage" 2>/dev/null | sort -V | tail -1)

if [[ -n "$APPIMAGE_BUNDLE" ]]; then
  APP_SRC="$APPIMAGE_BUNDLE"
else
  APP_SRC="$ROOT_DIR/src-tauri/target/release/arcade-sim"
  echo "warning: no AppImage bundle found, falling back to raw ELF"
  echo "         run 'bash build-release.sh' for a proper AppImage"
fi

# The sidecar ships inside the AppImage bundle but also needs to sit next
# to the installed AppImage so the Tauri sidecar resolver finds it at
# runtime.  Use the copy produced by build/pyinstaller/build.sh (dist/).
SIDECAR_SRC="${ROOT_DIR}/dist/arcade-sim-server"
# Always deploy to a fixed no-spaces filename so the .desktop Exec= line
# never needs quoting (many launchers break on spaces in Exec= paths).
APP_DST="$DEST_DIR/ArcadeFaultSimulator.AppImage"
SIDECAR_DST="$DEST_DIR/arcade-sim-server"

if [[ ! -f "$APP_SRC" ]]; then
  echo "Missing app binary: $APP_SRC"
  echo "Build first: bash build-release.sh"
  exit 1
fi

if [[ ! -f "$SIDECAR_SRC" ]]; then
  echo "Missing sidecar binary: $SIDECAR_SRC"
  echo "Build first: bash build-release.sh   (or: bash build/pyinstaller/build.sh)"
  exit 1
fi

mkdir -p "$DEST_DIR"

# Stop running instances before replacing binaries.
pkill -f "ArcadeFaultSimulator.AppImage|target/release/arcade-sim|arcade-sim-server --tauri-sidecar|Xvfb :99|mame .* -plugin cabinet_bus" 2>/dev/null || true
sleep 1

cp "$APP_SRC" "$APP_DST.new"
cp "$SIDECAR_SRC" "$SIDECAR_DST.new"
chmod +x "$APP_DST.new" "$SIDECAR_DST.new"
mv -f "$APP_DST.new" "$APP_DST"
mv -f "$SIDECAR_DST.new" "$SIDECAR_DST"

# Register / update the .desktop entry so App Center launches from the
# correct working directory and without the APPIMAGE_EXTRACT_AND_RUN flag.
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/arcade-fault-simulator.desktop" <<EOF
[Desktop Entry]
Name=Arcade Fault Simulator
Comment=Arcade cabinet fault simulation and diagnosis
Exec=env WEBKIT_DISABLE_COMPOSITING_MODE=1 LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 $APP_DST
Path=$ROOT_DIR
Icon=applications-games
Terminal=false
Type=Application
Categories=Game;Education;
EOF
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Deployed:"
echo "  $APP_DST"
echo "  $SIDECAR_DST"
echo "  $DESKTOP_DIR/arcade-fault-simulator.desktop (Path=$ROOT_DIR)"

if [[ "${1:-}" == "--launch" ]]; then
  nohup "$APP_DST" >/tmp/arcade-app.log 2>&1 &
  echo "Launched app (log: /tmp/arcade-app.log)"
fi
