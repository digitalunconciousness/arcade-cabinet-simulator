"""Persistent user configuration for the arcade-sim desktop app.

Config is stored in ``~/.arcade-sim/config.json``.  Env vars always take
precedence over file values so that the Tauri shell can override paths without
mutating the file (e.g. during testing).

Usage::

    from config import load_config, save_config

    cfg = load_config()
    mame_bin = cfg["mame_binary"]   # "" if not configured

    save_config({"mame_binary": "/usr/local/bin/mame"})
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path.home() / ".arcade-sim"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

# Keys recognised in the config file.  Unknown keys written by future versions
# are silently ignored on read so we stay forward-compatible.
_DEFAULTS: dict[str, Any] = {
    "mame_binary": "",
    "rom_path": "",
    "display": "",
}


def load_config() -> dict[str, Any]:
    """Return the current config, merging file values and env var overrides.

    Env vars (set by Tauri before spawning the sidecar):
      ARCADE_SIM_MAME_BINARY — full path to the mame executable
      ARCADE_SIM_ROM_PATH    — directory that contains the ROM zips
      ARCADE_SIM_DISPLAY     — X11 display string, e.g. ``:99``
    """
    cfg: dict[str, Any] = dict(_DEFAULTS)
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text())
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in _DEFAULTS})
    except (OSError, ValueError):
        pass

    # Env var overrides always win over file values.
    if os.environ.get("ARCADE_SIM_MAME_BINARY"):
        cfg["mame_binary"] = os.environ["ARCADE_SIM_MAME_BINARY"].strip()
    if os.environ.get("ARCADE_SIM_ROM_PATH"):
        cfg["rom_path"] = os.environ["ARCADE_SIM_ROM_PATH"].strip()
    if os.environ.get("ARCADE_SIM_DISPLAY"):
        cfg["display"] = os.environ["ARCADE_SIM_DISPLAY"].strip()

    return cfg


def save_config(updates: dict[str, Any]) -> None:
    """Persist *updates* to ``~/.arcade-sim/config.json``.

    Only keys listed in ``_DEFAULTS`` are written; unknown keys are silently
    dropped so callers can't accidentally pollute the file.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Read-merge-write so we don't clobber keys we didn't touch.
    existing: dict[str, Any] = dict(_DEFAULTS)
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text())
            if isinstance(data, dict):
                existing.update({k: v for k, v in data.items() if k in _DEFAULTS})
    except (OSError, ValueError):
        pass
    existing.update({k: v for k, v in updates.items() if k in _DEFAULTS})
    _CONFIG_FILE.write_text(json.dumps(existing, indent=2) + "\n")
