#!/usr/bin/env python3
# license:CC0-1.0
"""Run the standalone nltool harnesses the wiki cites, on the pinned build.

These netlists (tests/netlist/) are where FAULT_BUFFER and BAD_RAM_CELL
faults actually act. No path connects them to the running game, so this only
shows whether each harness still runs and whether its fault changes its own
waveform. Output: one JSON summary (edge counts per logged net).

  python tools/audit/netlist_standalone.py --nltool vendor/mame/nltool \\
      --out evidence/stage0/runs/netlist_standalone.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker import _summarise_wave  # noqa: E402

LOG_LINE = __import__("re").compile(r"^\s*(\S+)\s+(\S+)\s*$")

# (id, netlist, nets to log, -D defines, simulated seconds)
RUNS = [
    *[(f"fault_buffer_test/FAULT_MODE={m}", "tests/netlist/fault_buffer_test.cpp",
       ["FB1.Y"], {"FAULT_MODE": m}, 0.005) for m in range(4)],
    *[(f"ram_region/BAD_RAM_CELL_MODE={m}", "tests/netlist/centiped/ram_region.cpp",
       ["DO"], {"BAD_RAM_CELL_MODE": m}, 0.0001) for m in range(4)],
    ("address_decoder/normal", "tests/netlist/centiped/address_decoder.cpp",
     ["ROM_CSn", "RAM_CSn", "POKEY_CSn", "EAROM_CSn"], {}, 0.0001),
    ("address_decoder/ADDR_CTR.QB-stuck-lo", "tests/netlist/centiped/scenarios/fault_addr_qb_stuck_lo.cpp",
     ["ROM_CSn", "RAM_CSn", "POKEY_CSn", "EAROM_CSn"], {}, 0.0001),
    ("sync_generator/normal", "tests/netlist/centiped/sync_generator.cpp",
     ["HSYNC_n", "VSYNC_n"], {}, 0.001),
    ("sync_generator/V_LO.QC-stuck-lo", "tests/netlist/centiped/scenarios/fault_vsync_qc_stuck_lo.cpp",
     ["HSYNC_n", "VSYNC_n"], {}, 0.001),
]


def _parse(path: Path) -> list[tuple[float, float]]:
    out = []
    for line in path.read_text().splitlines():
        m = LOG_LINE.match(line)
        if m:
            try:
                out.append((float(m.group(1)), float(m.group(2))))
            except ValueError:
                pass
    return out


def run_all(nltool: Path) -> list[dict]:
    results = []
    for run_id, netlist, nets, defines, seconds in RUNS:
        with tempfile.TemporaryDirectory() as td:
            cmd = [str(nltool), "--cmd=run", f"--time_to_run={seconds}"]
            for n in nets:
                cmd += ["-l", n]
            for k, v in defines.items():
                cmd += ["-D", f"{k}={v}"]
            cmd.append(str(REPO / netlist))
            proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, timeout=120)
            waves = {}
            for n in nets:
                log = Path(td) / f"log_{n}.log"
                waves[n] = _summarise_wave(_parse(log)) if log.exists() else {"samples": 0}
        results.append({"id": run_id, "netlist": netlist, "defines": defines, "seconds": seconds,
                        "exit_code": proc.returncode, "stderr_tail": proc.stderr.splitlines()[-3:],
                        "waveforms": waves})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nltool", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    results = run_all(args.nltool.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1))
    for r in results:
        edges = {n: (w.get("falling_edges"), w.get("rising_edges")) for n, w in r["waveforms"].items()}
        print(f"{r['id']:45s} exit={r['exit_code']} edges(fall,rise)={edges}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
