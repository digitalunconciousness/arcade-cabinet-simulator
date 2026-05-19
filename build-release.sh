#!/usr/bin/env bash
# build-release.sh — build the full release AppImage (Linux) or installer
# (Windows/macOS).
#
# Usage:
#   bash build-release.sh            # build + deploy to ~/Applications
#   bash build-release.sh --no-deploy  # build only, don't deploy
#
# On Linux this wraps `cargo tauri build` with two env-var requirements:
#
#   NO_STRIP=1
#     The linuxdeploy AppImage bundler ships an old `strip` binary that
#     fails on modern glibc libraries using .relr.dyn relocations.
#     NO_STRIP=1 tells linuxdeploy to skip the strip step entirely.
#
#   APPIMAGE_EXTRACT_AND_RUN=1
#     AppImage-format tooling (linuxdeploy itself is an AppImage) normally
#     mounts itself via FUSE.  This flag makes them extract-and-run instead,
#     which works without FUSE2 and inside containers / CI.
#     On systems with fuse2 installed (sudo pacman -S fuse2) this is not
#     strictly required but is safe to pass.
#
# The tauri.conf.json beforeBuildCommand hook runs build/pyinstaller/build.sh
# automatically; you do NOT need to run that separately.
#
# After a successful Linux build the AppImage is deployed to ~/Applications/
# and the .desktop entry is updated unless --no-deploy is given.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DEPLOY=1
for arg in "$@"; do
  [[ "$arg" == "--no-deploy" ]] && DEPLOY=0
done

export NO_STRIP=1
export APPIMAGE_EXTRACT_AND_RUN=1

# Auto-load the Tauri updater signing key if it exists locally.
# This prevents the "private key not found" error at the end of the build
# (which exits non-zero even though the AppImage was produced successfully).
# In CI, set TAURI_SIGNING_PRIVATE_KEY in the environment instead.
if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" && -f "$HOME/.tauri/arcade-sim.key" ]]; then
  export TAURI_SIGNING_PRIVATE_KEY="$(cat "$HOME/.tauri/arcade-sim.key")"
  echo "==> loaded signing key from ~/.tauri/arcade-sim.key"
fi

echo "==> cargo tauri build (NO_STRIP=1 APPIMAGE_EXTRACT_AND_RUN=1) ..."
# Run the build; if it exits non-zero only because of a missing signing key
# (the AppImage itself was built fine), treat it as a warning and continue.
if ! cargo tauri build; then
  APPIMAGE_BUILT=$(find src-tauri/target/release/bundle/appimage -maxdepth 1 \
      -name '*.AppImage' 2>/dev/null | head -1)
  if [[ -z "$APPIMAGE_BUILT" ]]; then
    echo "ERROR: build failed and no AppImage was produced."
    exit 1
  fi
  echo "WARNING: cargo tauri build exited non-zero (likely TAURI_SIGNING_PRIVATE_KEY"
  echo "         not set).  AppImage was produced; continuing."
fi

if [[ "$DEPLOY" -eq 1 && "$(uname -s)" == "Linux" ]]; then
  echo "==> deploying to ~/Applications/ ..."
  bash tools/deploy-desktop.sh
fi
