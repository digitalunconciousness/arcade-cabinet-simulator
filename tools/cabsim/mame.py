# license:CC0-1.0
"""Run MAME headless with the cabsim plugin executing one timeline plan."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugin"


@dataclass
class RunResult:
    hashes: dict[int, str] = field(default_factory=dict)
    ram: dict[tuple[str, int], bytes] = field(default_factory=dict)
    frames: dict[int, tuple[int, int, bytes]] = field(default_factory=dict)
    events: list[list[str]] = field(default_factory=list)
    reads: dict[int, int] = field(default_factory=dict)
    finished: bool = False
    seconds: float = 0.0
    log_tail: str = ""

    def errors(self) -> list[list[str]]:
        return [e for e in self.events if e and e[0] == "error"]

    def resets_after(self, frame: int) -> int:
        return sum(1 for e in self.events if e[0] == "reset" and int(e[1]) > frame)


@dataclass
class MameConfig:
    mame: Path
    rompath: Path
    romset: str
    tmp: Path | None = None
    timeout_s: int = 600

    @property
    def mame_plugins(self) -> Path:
        return self.mame.parent / "plugins"


def _read(out: Path) -> RunResult:
    r = RunResult()
    h = out / "hashes.txt"
    if h.exists():
        for line in h.read_text().splitlines():
            if line.strip():
                f, v = line.split()
                r.hashes[int(f)] = v
    for p in out.glob("ram_*.bin"):
        name, frame = p.stem[4:].rsplit("_", 1)
        r.ram[(name, int(frame))] = p.read_bytes()
    for p in out.glob("frame_*.json"):
        f = int(p.stem.split("_")[1])
        meta = json.loads(p.read_text())
        r.frames[f] = (meta["width"], meta["height"], (out / f"frame_{f}.rgba").read_bytes())
    ev = out / "events.txt"
    if ev.exists():
        r.events = [line.split(" ", 3) for line in ev.read_text().splitlines() if line.strip()]
    rd = out / "reads.txt"
    if rd.exists():
        for line in rd.read_text().splitlines():
            a, n = line.split()
            r.reads[int(a, 16)] = int(n)
    r.finished = (out / "done.json").exists()
    return r


def run_plan(cfg: MameConfig, plan: dict, keep: Path | None = None) -> RunResult:
    """Run one plan and return what the plugin recorded."""
    import time

    work = Path(tempfile.mkdtemp(prefix="cabsim-", dir=cfg.tmp))
    out = work / "out"
    out.mkdir()
    (work / "plan.json").write_text(json.dumps(plan))
    env = dict(os.environ)
    env.update({
        "CABSIM_SCRIPT": str(work / "plan.json"),
        "CABSIM_OUT": str(out),
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
    })
    env.pop("CABSIM_PORT", None)
    cmd = [
        str(cfg.mame), cfg.romset,
        "-rompath", str(cfg.rompath),
        # MAME takes ';' between search paths on every platform
        "-pluginspath", f"{cfg.mame_plugins};{PLUGIN_DIR}",
        "-plugin", "cabsim",
        "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo",
        "-noreadconfig",
        "-cfg_directory", str(work / "cfg"), "-nvram_directory", str(work / "nvram"),
        "-homepath", str(work / "home"), "-state_directory", str(work / "sta"),
        "-snapshot_directory", str(work / "snap"),
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=cfg.timeout_s)
        log = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        log = f"MAME timed out after {cfg.timeout_s}s"
    result = _read(out)
    result.seconds = time.monotonic() - started
    result.log_tail = "\n".join(l for l in log.splitlines() if "ALSA" not in l)[-3000:]
    if keep is not None:
        if keep.exists():
            shutil.rmtree(keep)
        shutil.copytree(work, keep)
    shutil.rmtree(work, ignore_errors=True)
    return result
