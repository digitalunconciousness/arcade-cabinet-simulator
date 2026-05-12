# -*- mode: python ; coding: utf-8 -*-
# build/pyinstaller/server.spec
#
# PyInstaller spec for the arcade-sim sidecar binary.
#
# Build with:  bash build/pyinstaller/build.sh
# Output:      dist/arcade-sim-server   (Linux ELF)
#              dist/arcade-sim-server.exe  (Windows PE)
#
# The binary is later declared as an externalBin in src-tauri/tauri.conf.json.

import sys
from pathlib import Path

# Absolute repo root (two levels above this spec file).
REPO = Path(SPECPATH).resolve().parent.parent  # noqa: F821

a = Analysis(
    [str(REPO / "tools" / "cabinet_bus" / "__main__.py")],
    pathex=[
        str(REPO),  # makes `tools.cabinet_bus.server` importable when frozen
        str(REPO / "tools" / "cabinet_bus"),
        str(REPO / "tools" / "peripherals"),
        str(REPO / "tools" / "schematic"),
        str(REPO / "tools" / "training"),
    ],
    binaries=[],
    datas=[
        # Board definitions
        (str(REPO / "boards"),                           "boards"),
        # Fault scenarios
        (str(REPO / "tests" / "scenarios"),              "tests/scenarios"),
        # Web UI (HTML, JS, CSS, GLSL shaders)
        (str(REPO / "ui"),                               "ui"),
        # Schematic helpers (board_package, kicad_netlist, …)
        (str(REPO / "tools" / "schematic"),              "tools/schematic"),
        # Training / scenario runner
        (str(REPO / "tools" / "training"),               "tools/training"),
        # Instrumented netlists (needed by the nltool fault-simulation path)
        (str(REPO / "build" / "instrumented"),           "build/instrumented"),
        # MAME cabinet_bus Lua plugin (init.lua + plugin.json)
        (str(REPO / "vendor" / "mame" / "plugins" / "cabinet_bus"),
                                                         "mame_plugins/cabinet_bus"),
    ],
    hiddenimports=[
        # Flask internals that PyInstaller sometimes misses
        "flask",
        "flask.templating",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.routing",
        "werkzeug.exceptions",
        "werkzeug.middleware.proxy_fix",
        # jsonschema is imported lazily in board_package / kicad_netlist
        "jsonschema",
        "jsonschema.validators",
        "jsonschema._format",
        # requests is used by mame_client
        "requests",
        "requests.adapters",
        "urllib3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle small — none of these are needed at runtime.
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "IPython",
        "notebook",
        "pytest",
        "sphinx",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="arcade-sim-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # sidecar: stdout/stderr must be visible to the Tauri shell
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
