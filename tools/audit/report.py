#!/usr/bin/env python3
# license:CC0-1.0
"""Render the per-fault tables of docs/FAULT_AUDIT.md from results.json.

Replaces everything between the BEGIN/END markers in the target file, so the
hand-written summary above them stays as it is and the numbers can't drift
from the evidence.

  python tools/audit/report.py evidence/stage0 docs/FAULT_AUDIT.md
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BEGIN = "<!-- BEGIN GENERATED: tools/audit/report.py -->"
END = "<!-- END GENERATED -->"

KIND_TITLES = {
    "peripheral": "Peripheral faults (tools/peripherals, applied with POST /api/peripherals/fault)",
    "schematic": "Schematic pin faults (boards/centipede/fault_map.json, POST /api/schematic/fault/apply)",
    "scenario": "Training scenarios (tests/scenarios, POST /api/scenarios/<id>/apply)",
    "raw": "Raw RAM commands (POST /api/mame/stuck_byte, /api/mame/poke_ram)",
    "netlist": "Netlist waveform path (/api/run on build/instrumented/sync_generator.cpp)",
}


def _what_reached_mame(r: dict) -> str:
    cmds = r.get("plugin_commands") or []
    if not cmds:
        apply = r.get("http_apply") or {}
        status = apply.get("status")
        if status and status >= 400:
            err = (apply.get("response") or {}).get("error", "")
            return f"nothing (HTTP {status}: {err})"
        return "nothing"
    seen = Counter()
    for c in cmds:
        name = c["cmd"].get("cmd")
        ok = isinstance(c.get("reply"), dict) and c["reply"].get("ok") is True
        seen[(name, "accepted" if ok else "rejected")] += 1
    return ", ".join(f"`{n}` ×{k} {state}" if k > 1 else f"`{n}` {state}" for (n, state), k in sorted(seen.items()))


def _effect(r: dict) -> str:
    d = r.get("diff")
    if not d:
        return r.get("error", "")
    parts = [f"screen {d['frames_differing']}/{d['frames_compared']} frames"]
    last_cp = max(d["consequence_ram_bytes"], key=int) if d["consequence_ram_bytes"] else None
    if last_cp:
        game = sum(d["consequence_ram_bytes"][last_cp].values())
        inj = sum(d["ram_bytes_differing"][last_cp].values()) - game
        parts.append(f"game RAM {game} B")
        if inj:
            parts.append(f"injected cells {inj} B")
    if d["resets_run"] != d["resets_baseline"]:
        parts.append(f"resets {len(d['resets_run'])} (baseline {len(d['resets_baseline'])})")
    return ", ".join(parts)


def _netlist_effect(r: dict) -> str:
    waves = r.get("waveforms") or {}
    return ", ".join(f"{n}: {w.get('falling_edges')}↓/{w.get('rising_edges')}↑" for n, w in waves.items())


def render(results: dict) -> str:
    rows = defaultdict(list)
    for r in results["results"]:
        rows[r["kind"]].append(r)
    totals = Counter(r["verdict"] for r in results["results"])
    out = [BEGIN, ""]
    out.append(f"Run: {results['mame']}, romset `{results['romset']}`, fault applied at frame "
               f"{results['pause_frame']}, compared to frame {results['end_frame']}. Baseline determinism: "
               f"{results['determinism']['frames']} frames, {results['determinism']['frames_differing']} differing "
               f"between two baseline runs, RAM identical: {results['determinism']['ram_identical']}.")
    out.append("")
    out.append("| verdict | count |")
    out.append("|---|---|")
    for v, n in sorted(totals.items(), key=lambda kv: -kv[1]):
        out.append(f"| `{v}` | {n} |")
    out.append("")
    for kind, title in KIND_TITLES.items():
        if kind not in rows:
            continue
        out.append(f"### {title}")
        out.append("")
        if kind == "netlist":
            out.append("| fault | verdict | waveform changed vs normal | HSYNC/VSYNC edges (falling/rising) |")
            out.append("|---|---|---|---|")
            for r in rows[kind]:
                out.append(f"| `{r['id']}` | `{r['verdict']}` | {'yes' if r.get('standalone_waveform_changed') else 'no'}"
                           f" | {_netlist_effect(r)} |")
        else:
            out.append("| fault | verdict | what reached MAME | effect after injection | evidence |")
            out.append("|---|---|---|---|---|")
            for r in rows[kind]:
                ev = f"[run]({r['evidence']})"
                if r.get("images"):
                    ev += f", [before]({r['images']['baseline']}) / [after]({r['images']['faulted']})"
                    if r["images"].get("zoom"):
                        ev += f" / [zoom]({r['images']['zoom']})"
                out.append(f"| `{r['id']}` | `{r['verdict']}` | {_what_reached_mame(r)} | {_effect(r)} | {ev} |")
        out.append("")
    out.append(END)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    evidence, target = Path(argv[0]), Path(argv[1])
    results = json.loads((evidence / "results.json").read_text())
    block = render(results)
    # Links in the table are relative to the evidence folder; rewrite them for the doc's location.
    rel = Path(*([".."] * (len(target.parent.parts)))) / evidence if not target.parent == Path(".") else evidence
    block = block.replace("](runs/", f"]({rel.as_posix()}/runs/").replace("](images/", f"]({rel.as_posix()}/images/")
    text = target.read_text() if target.exists() else f"{BEGIN}\n{END}\n"
    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    target.write_text(head + block + tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
