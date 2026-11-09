# license:CC0-1.0
"""Effect tests: does a fault change the running game, and does repair undo it?

A test is one YAML file (format: tools/cabsim/README.md). The runner builds
two plans for the cabsim plugin's timeline mode, a baseline and a faulted
run, which share every event except the fault itself and its clearing. Both
runs perform the same repair action on the same frame, so after a repair the
faulted run must match the baseline frame for frame.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import asserts, images
from .mame import MameConfig, RunResult, run_plan

REPAIR_ACTIONS = {
    "clear": None,
    "clear_and_soft_reset": "soft",
    "clear_and_hard_reset": "hard",
}


@dataclass
class Outcome:
    test_id: str
    status: str                      # pass | fail | skip | error
    checks: list[dict] = field(default_factory=list)
    reason: str = ""
    evidence: str = ""


def load(path: Path) -> dict:
    test = yaml.safe_load(path.read_text())
    for key in ("id", "romset", "run"):
        if key not in test:
            raise ValueError(f"{path}: missing '{key}'")
    test["_path"] = str(path)
    return test


def build_plan(test: dict, faulted: bool) -> dict:
    run = test["run"]
    events = [dict(e) for e in run.get("events", [])]
    inj = test.get("inject")
    if faulted and inj:
        events.append({"frame": inj["at_frame"], "type": "apply", "primitive": inj["primitive"],
                       "params": inj.get("params", {}), "label": "fault"})
    rep = test.get("repair")
    if rep:
        action = rep.get("action", "clear")
        if action not in REPAIR_ACTIONS:
            raise ValueError(f"unknown repair action {action!r}")
        if faulted:
            events.append({"frame": rep["at_frame"], "type": "clear_all"})
        kind = REPAIR_ACTIONS[action]
        if kind:
            events.append({"frame": rep["at_frame"], "type": "reset", "kind": kind})
    events.sort(key=lambda e: e["frame"])  # stable: same-frame events keep their order
    return {
        "end_frame": run["end_frame"],
        "checkpoints": run.get("checkpoints", []),
        "ram": run.get("ram", []),
        "events": events,
    }


def _check(spec: dict, base: RunResult, fault: RunResult, phase: str) -> dict:
    (name, args), = spec.items()
    args = args or {}
    if name == "snapshot":
        return {"phase": phase, "check": name, "args": args, "passed": True, "details": {}}
    fn = asserts.ASSERTIONS.get(name)
    if fn is None:
        return {"phase": phase, "check": name, "args": args, "passed": False, "details": {"error": "unknown assertion"}}
    try:
        passed, details = fn(args, base, fault)
    except Exception as e:  # noqa: BLE001
        passed, details = False, {"error": f"{type(e).__name__}: {e}"}
    return {"phase": phase, "check": name, "args": args, "passed": bool(passed), "details": details}


def _slug(test_id: str) -> str:
    return test_id.replace("/", "__")


class Runner:
    def __init__(self, cfg: MameConfig, out: Path, romset_override: str | None = None):
        self.cfg = cfg
        self.out = out
        self.romset_override = romset_override
        self._baselines: dict[str, RunResult] = {}
        self._romsets: dict[str, bool] = {}

    def romset_available(self, romset: str) -> bool:
        if romset not in self._romsets:
            proc = subprocess.run([str(self.cfg.mame), "-rompath", str(self.cfg.rompath), "-verifyroms", romset],
                                  capture_output=True, text=True)
            # "is good" or "is best available"; a set with only wrong checksums (the test ROM) reports "is bad"
            ok = proc.returncode == 0 or " is bad" in proc.stdout and "NOT FOUND" not in proc.stdout
            self._romsets[romset] = ok
        return self._romsets[romset]

    def _run(self, romset: str, plan: dict) -> RunResult:
        cfg = MameConfig(self.cfg.mame, self.cfg.rompath, romset, self.cfg.tmp, self.cfg.timeout_s)
        return run_plan(cfg, plan)

    def baseline(self, romset: str, plan: dict) -> RunResult:
        key = romset + json.dumps(plan, sort_keys=True)
        if key not in self._baselines:
            self._baselines[key] = self._run(romset, plan)
        return self._baselines[key]

    def run_test(self, test: dict) -> Outcome:
        romset = self.romset_override or test["romset"]
        if not self.romset_available(romset):
            return Outcome(test["id"], "skip", reason=f"romset {romset} not found in {self.cfg.rompath}")
        base = self.baseline(romset, build_plan(test, faulted=False))
        fault = self._run(romset, build_plan(test, faulted=True))
        if not base.finished:
            return Outcome(test["id"], "error", reason="baseline run did not finish: " + base.log_tail[-500:])

        checks = [_check(s, base, fault, "fault") for s in test.get("expect", [])]
        checks += [_check(s, base, fault, "repair") for s in test.get("expect_after_repair", [])]
        status = "pass" if checks and all(c["passed"] for c in checks) else "fail"

        evdir = self.out / _slug(test["id"])
        evdir.mkdir(parents=True, exist_ok=True)
        rotate = int(test.get("display", {}).get("rotate", 0))
        shots = []
        for c in checks:
            if c["check"] == "snapshot":
                at = int(c["args"]["at"])
                if at in base.frames and at in fault.frames:
                    b = evdir / f"baseline_f{at}.png"
                    f = evdir / f"faulted_f{at}.png"
                    images.save_png(base.frames[at], b, rotate)
                    images.save_png(fault.frames[at], f, rotate)
                    z = evdir / f"zoom_f{at}.png"
                    box = images.zoom_diff(b, f, z)
                    shots.append({"frame": at, "baseline": b.name, "faulted": f.name,
                                  "zoom": z.name if box else None, "changed_box": list(box) if box else None})
        checkpoints = sorted(set(base.hashes) & set(test["run"].get("checkpoints", [])))
        result = {
            "id": test["id"],
            "title": test.get("title", ""),
            "status": status,
            "romset": romset,
            "tier": test.get("tier"),
            "symptom": test.get("symptom"),
            "sources": test.get("sources", []),
            "inject": test.get("inject"),
            "repair": test.get("repair"),
            "checks": checks,
            "hashes_at_checkpoints": {str(f): {"baseline": base.hashes.get(f), "faulted": fault.hashes.get(f)}
                                      for f in checkpoints},
            "frames": {"baseline": len(base.hashes), "faulted": len(fault.hashes)},
            "seconds": {"baseline": round(base.seconds, 2), "faulted": round(fault.seconds, 2)},
            "plugin_events_faulted": [" ".join(e) for e in fault.events][:50],
            "snapshots": shots,
            "test_file": Path(test["_path"]).as_posix(),
        }
        (evdir / "result.json").write_text(json.dumps(result, indent=1))
        return Outcome(test["id"], status, checks, evidence=str(evdir))
