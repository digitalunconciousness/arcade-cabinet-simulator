# license:CC0-1.0
"""How much do Lua memory taps slow the emulation? (PLAN v0.3, risk 1)

Runs the same stretch of attract mode unthrottled, without frame hashing,
once with no fault and once per tap-based fault, and reports speed as a
multiple of real time (60 frames per emulated second). A fault whose speed
falls below 1.0 on the target machine would have to move into C++.

  python -m tools.cabsim.bench --mame vendor/mame/mame --rompath roms \\
      --romset centiped3 --out evidence/stage1/benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from .mame import MameConfig, run_plan

FRAMES = 3600  # one emulated minute
INJECT = 60

CASES = [
    ("no fault", None, None),
    ("data_bit_stuck on playfield RAM 0x0400-0x07BF", "data_bit_stuck",
     {"space": ":maincpu", "start": 0x0400, "end": 0x07BF, "bit": 3, "level": 0}),
    ("data_bit_stuck on zero page and stack 0x0000-0x01FF (hot)", "data_bit_stuck",
     {"space": ":maincpu", "start": 0x0000, "end": 0x01FF, "bit": 7, "level": 0}),
    ("data_bit_stuck on all RAM 0x0000-0x07FF", "data_bit_stuck",
     {"space": ":maincpu", "start": 0x0000, "end": 0x07FF, "bit": 7, "level": 0}),
    ("addr_line_stuck on playfield RAM (write tap + partner writes)", "addr_line_stuck",
     {"space": ":maincpu", "start": 0x0400, "end": 0x07BF, "line": 5, "level": 1}),
    ("reg_read_override on POKEY RANDOM", "reg_read_override",
     {"space": ":maincpu", "addr": 0x100A, "rule": {"and_mask": 0xFD}}),
]


def _cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mame", type=Path, required=True)
    ap.add_argument("--rompath", type=Path, required=True)
    ap.add_argument("--romset", default="centiped3")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tmp", type=Path, default=None)
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args(argv)
    cfg = MameConfig(args.mame.resolve(), args.rompath.resolve(), args.romset, args.tmp)
    rows = []
    for label, prim, params in CASES:
        events = [] if prim is None else [{"frame": INJECT, "type": "apply", "primitive": prim, "params": params}]
        plan = {"end_frame": FRAMES, "hash": False, "checkpoints": [], "ram": [], "events": events}
        times = []
        for _ in range(args.repeat):
            r = run_plan(cfg, plan)
            if not r.finished:
                print(f"{label}: run did not finish\n{r.log_tail}", file=sys.stderr)
                return 1
            times.append(r.seconds)
        best = min(times)
        rows.append({"case": label, "frames": FRAMES, "wall_seconds_best": round(best, 3),
                     "wall_seconds_all": [round(t, 3) for t in times],
                     "speed_x_realtime": round(FRAMES / 60.0 / best, 2)})
        print(f"{rows[-1]['speed_x_realtime']:7.2f}x  {label}")
    base = rows[0]["wall_seconds_best"]
    for r in rows:
        r["relative_to_no_fault"] = round(base / r["wall_seconds_best"], 3)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "note": "Unthrottled, headless (-video none -sound none), no frame hashing, best of N. Wall time includes MAME start-up.",
        "machine": {"cpu": _cpu_name(), "cpus": os.cpu_count(), "os": platform.platform()},
        "romset": args.romset,
        "results": rows,
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
