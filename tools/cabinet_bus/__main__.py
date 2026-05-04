"""Allow `python -m tools.cabinet_bus` to launch the server.

This is also the PyInstaller entry point for the desktop sidecar bundle.
"""
from .server import main

main()
