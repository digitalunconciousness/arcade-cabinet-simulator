"""Allow `python -m tools.cabinet_bus` to launch the server.

This is also the PyInstaller entry point for the desktop sidecar bundle.
When frozen by PyInstaller, relative imports are unavailable because the
module runs as __main__ without a package context; fall back to absolute.
"""
try:
    from .server import main  # normal: python -m tools.cabinet_bus
except ImportError:
    from tools.cabinet_bus.server import main  # PyInstaller frozen

main()
