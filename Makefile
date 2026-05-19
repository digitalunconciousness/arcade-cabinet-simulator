# Arcade Fault Simulator — build targets
#
# make            →  build AppImage + .deb, then deploy to ~/Applications/
# make build      →  rebuild + deploy (same as `make`)
# make package    →  build only (no deploy)
# make deploy     →  deploy the most-recent bundle (no rebuild)
# make quick      →  recompile Rust binary only, then deploy (skips PyInstaller
#                    and AppImage bundling — fast iteration when only Rust changed)
# make clean      →  remove Cargo release artifacts (keeps vendor/mame)

.PHONY: all build package deploy quick clean

all: deploy

build:
	bash build-release.sh

package:
	bash build-release.sh --no-deploy

deploy:
	bash build-release.sh

# Quick path: recompile the Rust binary only, then hot-swap it into the
# installed AppImage location via deploy-desktop.sh.
# PyInstaller is NOT re-run, so use `make` (full build) if tools/server.py changed.
quick:
	APPIMAGE_EXTRACT_AND_RUN=1 NO_STRIP=1 cargo tauri build --no-bundle
	bash tools/deploy-desktop.sh

clean:
	cargo clean --manifest-path src-tauri/Cargo.toml
