#!/usr/bin/env python3
# license:CC0-1.0
"""Stage 0 truth audit: does each legacy fault change the running game?

For every fault in the inventory this starts headless MAME with the plugin a
fresh checkout builds (patches/0002), pauses the game on a fixed frame,
applies the fault through the legacy server exactly as the app would
(worker.py), resumes, and compares what the game shows and holds with a
baseline run that got the same treatment minus the fault.

Determinism check: the baseline runs twice. If the two disagree on any frame,
the audit stops, because no comparison would mean anything.

Usage (from the repo root):
  git worktree add ../acs-legacy legacy-tauri
  python tools/audit/run_audit.py --legacy-root ../acs-legacy \\
      --mame vendor/mame/mame --nltool vendor/mame/nltool --rompath roms \\
      --romset centiped3 --out evidence/stage0
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as inventory_mod  # noqa: E402

PAUSE_FRAME = 600            # about 10 s into attract mode
END_FRAME = 1200             # 10 s after injection
CHECKPOINTS = (600, 660, 900, 1200)
RAM_REGIONS = {              # centiped_base_map in MAME's centiped.cpp
    "work_ram_0000_03ff": (0x0000, 0x0400),
    "playfield_0400_07bf": (0x0400, 0x07C0),
    "sprite_ram_07c0_07ff": (0x07C0, 0x0800),
}
# Plugin commands that can change the machine. ping/get_state only read.
ACTING_COMMANDS = {
    "pause", "resume", "soft_reset", "poke_ram", "stuck_byte", "clear_stuck",
    "set_crt_fault", "trackball_delta", "press_button", "release_button",
    "clear_buttons", "set_dip_switch",
}


@dataclass
class Capture:
    hashes: dict[int, str] = field(default_factory=dict)
    ram: dict[int, bytes] = field(default_factory=dict)
    frames: dict[int, tuple[int, int, bytes]] = field(default_factory=dict)
    resets: list[str] = field(default_factory=list)
    finished: bool = False
    paused_frame: int | None = None
    worker: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------- comparison

def _command_key(entry: dict) -> str:
    cmd = dict(entry["cmd"])
    return json.dumps(cmd, sort_keys=True)


def is_reset(cmd: dict) -> bool:
    """Clean-up the legacy server sends around every fault: disarming stuck
    bytes (value null), clear_stuck, clear_buttons and set_crt_fault "normal".
    They can't carry a fault, so they don't count as the fault's commands."""
    name = cmd.get("cmd")
    if name in ("clear_stuck", "clear_buttons"):
        return True
    if name == "stuck_byte" and cmd.get("value") is None:
        return True
    if name == "set_crt_fault" and cmd.get("effect") == "normal" and float(cmd.get("brightness", 1.0)) == 1.0:
        return True
    return False


def fault_commands(run_log: dict, baseline_log: dict) -> list[dict]:
    """Acting plugin commands the faulted run sent that the baseline didn't,
    leaving out held resumes and reset traffic (is_reset)."""
    remaining: dict[str, int] = {}
    for e in baseline_log.get("plugin", []):
        k = _command_key(e)
        remaining[k] = remaining.get(k, 0) + 1
    extra = []
    for e in run_log.get("plugin", []):
        if e["cmd"].get("cmd") not in ACTING_COMMANDS or e.get("held_by_audit") or is_reset(e["cmd"]):
            continue
        k = _command_key(e)
        if remaining.get(k, 0) > 0:
            remaining[k] -= 1
            continue
        extra.append(e)
    return extra


def _accepted(entry: dict) -> bool:
    reply = entry.get("reply")
    return isinstance(reply, dict) and reply.get("ok") is True


def injected_addresses(cmds: list[dict]) -> set[int]:
    """RAM cells the plugin itself writes for this fault (accepted stuck_byte
    and poke_ram). The legacy plugin re-writes stuck cells in the frame
    notifier, just before the probe samples RAM, so a difference at these
    addresses shows the injection itself, not something the game did."""
    out = set()
    for e in cmds:
        c = e["cmd"]
        if c.get("cmd") in ("stuck_byte", "poke_ram") and _accepted(e) and c.get("value") is not None:
            out.add(int(c["addr"]))
    return out


def compare(base: Capture, run: Capture, pause_frame: int, injected: set[int] = frozenset()) -> dict:
    """Frame, RAM and reset differences after the injection frame.

    ram_bytes_differing counts every differing byte; consequence_ram_bytes
    leaves out the injected cells, so it counts only what the game changed.
    """
    later = [f for f in sorted(base.hashes) if f > pause_frame]
    differing = [f for f in later if run.hashes.get(f) != base.hashes[f]]
    missing = [f for f in later if f not in run.hashes]
    ram, consequence = {}, {}
    for cp in sorted(base.ram):
        if cp <= pause_frame or cp not in run.ram:
            continue
        per_region, per_region_c = {}, {}
        for name, (lo, hi) in RAM_REGIONS.items():
            diffs = [a for a in range(lo, hi) if base.ram[cp][a] != run.ram[cp][a]]
            per_region[name] = len(diffs)
            per_region_c[name] = sum(1 for a in diffs if a not in injected)
        ram[str(cp)] = per_region
        consequence[str(cp)] = per_region_c
    return {
        "frames_compared": len(later),
        "frames_differing": len(differing),
        "first_differing_frame": differing[0] if differing else None,
        "frames_missing": len(missing),
        "ram_bytes_differing": ram,
        "consequence_ram_bytes": consequence,
        "injected_cells": sorted(injected),
        "resets_baseline": base.resets,
        "resets_run": run.resets,
    }


def verdict(diff: dict, extra_cmds: list[dict]) -> str:
    """changes-game-output: the screen, the game's own RAM or its resets differ.
    injected-cells-only: only the cells the plugin writes differ.
    rejected-by-plugin: every fault command was refused (unknown command).
    not-sent: the fault sent nothing to MAME. no-change: sent, accepted, no effect."""
    changed = (
        diff["frames_differing"] > 0
        or diff["frames_missing"] > 0
        or any(n for region in diff["consequence_ram_bytes"].values() for n in region.values())
        or diff["resets_run"] != diff["resets_baseline"]
    )
    if changed:
        return "changes-game-output"
    if any(n for region in diff["ram_bytes_differing"].values() for n in region.values()):
        return "injected-cells-only"
    if not extra_cmds:
        return "not-sent"
    if not any(_accepted(e) for e in extra_cmds):
        return "rejected-by-plugin"
    return "no-change"


# ------------------------------------------------------------------- running

def _read_capture(probe: Path) -> Capture:
    cap = Capture()
    hashes = probe / "hashes.txt"
    if hashes.exists():
        for line in hashes.read_text().splitlines():
            f, h = line.split()
            cap.hashes[int(f)] = h
    for p in probe.glob("ram_*.bin"):
        cap.ram[int(p.stem.split("_")[1])] = p.read_bytes()
    for p in probe.glob("frame_*.json"):
        f = int(p.stem.split("_")[1])
        meta = json.loads(p.read_text())
        cap.frames[f] = (meta["width"], meta["height"], (probe / f"frame_{f}.rgba").read_bytes())
    events = probe / "events.txt"
    if events.exists():
        cap.resets = [l for l in events.read_text().splitlines() if l.strip()]
    cap.finished = (probe / "done.json").exists()
    paused = probe / "paused.json"
    if paused.exists():
        cap.paused_frame = json.loads(paused.read_text())["frame"]
    return cap


def run_one(args, entry: dict | None) -> Capture:
    tmp = Path(tempfile.mkdtemp(prefix="audit-", dir=args.tmp))
    probe = tmp / "probe"
    probe.mkdir()
    env = dict(os.environ)
    env.update({
        "AUDIT_OUT": str(probe),
        "AUDIT_PAUSE_FRAME": str(args.pause_frame),
        "AUDIT_END_FRAME": str(args.end_frame),
        "AUDIT_CHECKPOINTS": ",".join(str(c) for c in CHECKPOINTS),
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
    })
    env.pop("CABINET_BOARD_PATH", None)
    cmd = [
        str(args.mame), args.romset,
        "-rompath", str(args.rompath),
        "-pluginspath", str(args.plugins),
        "-plugin", "cabinet_bus",
        "-autoboot_script", str(HERE / "probe.lua"),
        "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo",
        "-cfg_directory", str(tmp / "cfg"), "-nvram_directory", str(tmp / "nvram"),
        "-homepath", str(tmp / "home"), "-state_directory", str(tmp / "sta"),
    ]
    log = open(tmp / "mame.log", "w")
    mame = subprocess.Popen(cmd, cwd=tmp, env=env, stdout=log, stderr=subprocess.STDOUT)
    cap = Capture()
    try:
        deadline = time.monotonic() + 120
        while not (probe / "paused.json").exists():
            if mame.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("MAME never reached the injection frame")
            time.sleep(0.05)
        worker_log = tmp / "worker.json"
        wcmd = [str(args.python), str(HERE / "worker.py"), "mame",
                "--legacy-root", str(args.legacy_root), "--log", str(worker_log)]
        if entry is not None:
            wcmd += ["--entry", json.dumps(entry)]
        w = subprocess.run(wcmd, env=env, capture_output=True, text=True, timeout=120)
        if not worker_log.exists():
            raise RuntimeError(f"worker failed: {w.stderr[-2000:]}")
        mame.wait(timeout=180)
        cap = _read_capture(probe)
        cap.worker = json.loads(worker_log.read_text())
        if not cap.finished:
            cap.error = "MAME exited before the end frame"
    except Exception as e:  # noqa: BLE001
        cap = _read_capture(probe)
        cap.error = f"{type(e).__name__}: {e}"
    finally:
        if mame.poll() is None:
            mame.kill()
            mame.wait()
        log.close()
        if args.keep_tmp:
            print(f"  kept {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return cap


def save_png(frame: tuple[int, int, bytes], path: Path) -> None:
    """MAME's screen bitmap is 32-bit xRGB, little-endian. Centipede's monitor
    is mounted ROT270, so rotate the raw bitmap 90 degrees to stand it up."""
    from PIL import Image
    w, h, data = frame
    Image.frombytes("RGB", (w, h), data, "raw", "BGRX").rotate(90, expand=True).save(path, optimize=True)


def _slug(entry_id: str) -> str:
    return entry_id.replace("/", "__").replace(".", "_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--mame", type=Path, required=True)
    parser.add_argument("--nltool", type=Path, required=True)
    parser.add_argument("--rompath", type=Path, required=True)
    parser.add_argument("--romset", default="centiped3")
    parser.add_argument("--plugins", type=Path, default=None,
                        help="MAME plugins folder (default: next to the mame binary)")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", default="", help="run only entries whose id contains this")
    parser.add_argument("--pause-frame", type=int, default=PAUSE_FRAME)
    parser.add_argument("--end-frame", type=int, default=END_FRAME)
    parser.add_argument("--keep-tmp", action="store_true")
    parser.add_argument("--tmp", type=Path, default=None,
                        help="folder for per-run scratch folders (default: the system temp folder)")
    args = parser.parse_args(argv)
    for name in ("legacy_root", "mame", "nltool", "rompath", "out"):
        setattr(args, name, getattr(args, name).resolve())
    args.plugins = (args.plugins or args.mame.parent / "plugins").resolve()

    out = args.out
    (out / "runs").mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(exist_ok=True)
    inventory = inventory_mod.build_inventory(args.legacy_root)
    (out / "inventory.json").write_text(json.dumps(inventory, indent=1))
    selected = [e for e in inventory if args.only in e["id"]]

    print("baseline (twice) ...", file=sys.stderr)
    base_a = run_one(args, None)
    base_b = run_one(args, None)
    for cap in (base_a, base_b):
        if cap.error:
            print(f"baseline failed: {cap.error}", file=sys.stderr)
            return 1
    determinism = {
        "frames": len(base_a.hashes),
        "frames_differing": sum(1 for f, h in base_a.hashes.items() if base_b.hashes.get(f) != h),
        "ram_identical": base_a.ram == base_b.ram,
    }
    (out / "baseline_hashes.txt").write_text(
        "".join(f"{f} {h}\n" for f, h in sorted(base_a.hashes.items())))
    (out / "runs" / "baseline.json").write_text(json.dumps(base_a.worker, indent=1))
    if determinism["frames_differing"] or not determinism["ram_identical"]:
        print(f"baseline is not deterministic: {determinism}", file=sys.stderr)
        (out / "determinism.json").write_text(json.dumps(determinism, indent=1))
        return 1
    for cp in CHECKPOINTS:
        if cp in base_a.frames:
            save_png(base_a.frames[cp], out / "images" / f"baseline_f{cp}.png")

    results = []
    mame_entries = [e for e in selected if e["kind"] != "netlist"]
    for i, entry in enumerate(mame_entries, 1):
        print(f"[{i}/{len(mame_entries)}] {entry['id']}", file=sys.stderr)
        cap = run_one(args, entry)
        record = {"id": entry["id"], "kind": entry["kind"], "source": entry["source"],
                  "evidence": f"runs/{_slug(entry['id'])}.json"}
        if cap.error and not cap.hashes:
            record.update({"verdict": "harness-error", "error": cap.error})
        else:
            extra = fault_commands(cap.worker or {}, base_a.worker or {})
            diff = compare(base_a, cap, args.pause_frame, injected_addresses(extra))
            record.update({
                "verdict": verdict(diff, extra),
                "diff": diff,
                "plugin_commands": [{"cmd": e["cmd"], "reply": e.get("reply"), "error": e.get("error")}
                                    for e in extra],
                "http_apply": (cap.worker or {}).get("apply"),
            })
            summary = (cap.worker or {}).get("schematic_summary")
            if summary is not None:
                resp = summary.get("response") or {}
                record["schematic_source"] = {"status": summary["status"],
                                              "available": resp.get("available"),
                                              "error": resp.get("error")}
            if cap.error:
                record["error"] = cap.error
            if record["verdict"] == "changes-game-output":
                shown = next((cp for cp in CHECKPOINTS if cp > args.pause_frame and cp in cap.frames
                              and cap.hashes.get(cp) != base_a.hashes.get(cp)), None)
                if shown is not None:
                    img = f"images/{_slug(entry['id'])}_f{shown}.png"
                    save_png(cap.frames[shown], out / img)
                    record["images"] = {"baseline": f"images/baseline_f{shown}.png", "faulted": img}
        (out / record["evidence"]).write_text(json.dumps({"record": record, "worker": cap.worker}, indent=1))
        results.append(record)

    netlist_entries = [e for e in selected if e["kind"] == "netlist"]
    if netlist_entries:
        print(f"netlist path ({len(netlist_entries)} runs) ...", file=sys.stderr)
        nl_log = out / "runs" / "netlist.json"
        subprocess.run([str(args.python), str(HERE / "worker.py"), "netlist",
                        "--legacy-root", str(args.legacy_root), "--nltool", str(args.nltool),
                        "--entry", json.dumps(netlist_entries), "--log", str(nl_log)],
                       check=True, timeout=600)
        nl = json.loads(nl_log.read_text())
        normal = next((r for r in nl if not r["faults"]), None)
        for r in nl:
            if r is normal:
                continue
            changed = normal is not None and r["waveforms"] != normal["waveforms"]
            results.append({
                "id": r["id"], "kind": "netlist", "source": "build/instrumented/sync_generator.cpp via /api/run",
                "verdict": "standalone-only" if r["status"] == 200 else "harness-error",
                "standalone_waveform_changed": changed,
                "waveforms": r["waveforms"], "error": r["error"],
                "evidence": "runs/netlist.json",
            })

    (out / "results.json").write_text(json.dumps({
        "mame": subprocess.run([str(args.mame), "-version"], capture_output=True, text=True).stdout.strip(),
        "romset": args.romset,
        "pause_frame": args.pause_frame,
        "end_frame": args.end_frame,
        "determinism": determinism,
        "results": results,
    }, indent=1))
    import zoom
    zoom.add_zooms(out)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
