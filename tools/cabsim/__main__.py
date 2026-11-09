# license:CC0-1.0
"""cabsim command line (Stage 1: effect tests only).

  python -m tools.cabsim effect run tests/effect/centipede/*.yaml \\
      --mame vendor/mame/mame --rompath roms --out evidence/stage1

Exit status: 0 when every test passed or was skipped, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .effect import Runner, load
from .mame import MameConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cabsim")
    sub = parser.add_subparsers(dest="group", required=True)
    eff = sub.add_parser("effect").add_subparsers(dest="action", required=True)
    run = eff.add_parser("run", help="run effect tests headless")
    run.add_argument("tests", nargs="+", type=Path, help="test files or folders of them")
    run.add_argument("--mame", type=Path, required=True)
    run.add_argument("--rompath", type=Path, required=True)
    run.add_argument("--romset", default=None, help="run every test against this set instead of its own")
    run.add_argument("--out", type=Path, default=Path("evidence/stage1"))
    run.add_argument("--tmp", type=Path, default=None, help="folder for per-run scratch folders")
    run.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    cfg = MameConfig(args.mame.resolve(), args.rompath.resolve(), "", args.tmp, args.timeout)
    runner = Runner(cfg, args.out, args.romset)
    paths: list[Path] = []
    for p in args.tests:  # a folder means every *.yaml in it (no shell globbing needed on Windows)
        paths.extend(sorted(p.glob("*.yaml")) if p.is_dir() else [p])
    failed = 0
    for path in paths:
        test = load(path)
        outcome = runner.run_test(test)
        print(f"{outcome.status.upper():5s} {outcome.test_id} {outcome.reason}".rstrip())
        for c in outcome.checks:
            mark = "ok " if c["passed"] else "BAD"
            print(f"      {mark} {c['phase']}:{c['check']} {c['details']}")
        if outcome.status in ("fail", "error"):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
