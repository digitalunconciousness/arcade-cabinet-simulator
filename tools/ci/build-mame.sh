#!/usr/bin/env bash
# license:CC0-1.0
# Build MAME at the pinned tag with patches/*.patch, and put the binary and
# its plugins folder in mame-bin/. Used by CI (GitHub and Forgejo) and works
# locally. Runs on Linux, and on Windows from an MSYS2 MINGW64 shell.
#
#   tools/ci/build-mame.sh          # JOBS=<n> to limit parallel compiles
#
# A vendor/mame that already exists is reused as it is: if it's still on the
# pinned tag the patches are applied, otherwise they're assumed applied.
set -euo pipefail

cd "$(dirname "$0")/../.."
read -r tag sha < patches/MAME_VERSION

if [ ! -d vendor/mame/.git ]; then
	git clone --depth=1 --branch "$tag" https://github.com/mamedev/mame.git vendor/mame
fi
head=$(git -C vendor/mame rev-parse HEAD)
if [ "$head" = "$sha" ]; then
	git -C vendor/mame -c user.name=ci -c user.email=ci@invalid am "$PWD"/patches/*.patch
elif ! git -C vendor/mame merge-base --is-ancestor "$sha" "$head"; then
	echo "vendor/mame is not based on $tag ($sha)" >&2
	exit 1
fi

case "$(uname -s)" in
	MINGW* | MSYS*)
		exe=mame.exe
		# what MAME's own Windows CI uses
		export OVERRIDE_AR=llvm-ar OVERRIDE_CC=gcc OVERRIDE_CXX=g++ ARCHOPTS=-fuse-ld=lld
		extra=()
		;;
	*)
		exe=mame
		# headless use only: no PortAudio, PipeWire or PulseAudio needed
		extra=(NO_USE_PORTAUDIO=1 NO_USE_PIPEWIRE=1 NO_USE_PULSEAUDIO=1)
		;;
esac

make -C vendor/mame -j"${JOBS:-$(nproc)}" SOURCES=src/mame/atari/centiped.cpp USE_QTDEBUG=0 SYMBOLS=0 "${extra[@]}"

mkdir -p mame-bin
cp "vendor/mame/$exe" mame-bin/
rm -rf mame-bin/plugins
cp -r vendor/mame/plugins mame-bin/plugins
mame-bin/"$exe" -version
