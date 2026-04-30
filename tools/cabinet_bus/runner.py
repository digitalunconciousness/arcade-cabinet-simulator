#!/usr/bin/env python3
# license:CC0-1.0
"""
Cabinet-bus nltool runner.

Given an instrumented netlist file and a fault dict
(`{"FB_V_LO_QC": 2, ...}`), this module:
  1. Generates a scenario netlist by appending `PARAM(FB_*.MODE, ...)`
     lines just before the closing `}` of the netlist body.
  2. Runs `nltool --cmd=run --time_to_run=... -l net1 -l net2 ...` against
     the scenario.
  3. Parses the per-net log files into time-series JSON.

The resulting JSON is what the UI plots. The runner is deliberately
stateless and pure-function-ish so it can be unit-tested without Flask.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


@dataclasses.dataclass
class RunSpec:
    """A single nltool run request."""
    template_path: Path        # the instrumented netlist .cpp
    nltool_path: Path          # /home/jackie/arcade-sim/vendor/mame/nltool
    log_nets: list[str]        # nets to log (e.g., ["HSYNC_n", "VSYNC_n"])
    faults: dict[str, int]     # {"FB_V_LO_QC": 2, ...}; missing = NORMAL
    duration_s: float = 0.001  # simulated seconds


@dataclasses.dataclass
class RunResult:
    """Output of a single run."""
    waveforms: dict[str, list[tuple[float, float]]]  # net -> [(t, v), ...]
    stderr: str
    duration_s: float
    fault_mode_count: int   # how many non-NORMAL faults were active


# Mode integer -> human label, for diagnostics.
MODE_LABELS = {0: "NORMAL", 1: "STUCK_HI", 2: "STUCK_LO", 3: "OPEN"}


# Lines of the form "0.000000000e+00 4.000000e+00\n" in the log file.
LOG_LINE_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$"
)


def build_scenario(template: str, faults: dict[str, int]) -> str:
    """Insert PARAM lines for non-NORMAL faults just before the closing brace.

    The instrumented netlist ends with a `NETLIST_START(main) { ... }` block.
    We find the LAST `}` in the file and inject our PARAM block before it.
    """
    if not faults:
        return template

    param_lines = []
    for fault_device, mode in faults.items():
        if mode == 0:  # NORMAL is the default; skip
            continue
        if not _is_safe_identifier(fault_device):
            raise ValueError(f"unsafe fault device name: {fault_device!r}")
        if mode not in MODE_LABELS:
            raise ValueError(f"unknown fault mode: {mode!r}")
        param_lines.append(
            f"\tPARAM({fault_device}.MODE, {mode})  // injected: {MODE_LABELS[mode]}"
        )

    if not param_lines:
        return template

    # Find the last closing brace at column zero or after a tab — the end of
    # the NETLIST_START body. Inject above it.
    last_brace = template.rfind("}")
    if last_brace == -1:
        raise ValueError("template has no closing brace; not a netlist body")
    inject = "\n\t// === Cabinet-bus injected faults ===\n" + "\n".join(param_lines) + "\n"
    return template[:last_brace] + inject + template[last_brace:]


def _is_safe_identifier(name: str) -> bool:
    """Reject anything not a plain C identifier; defends the scenario writer
    against shell or netlist-syntax injection via the fault dict."""
    return bool(re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", name))


def run(spec: RunSpec) -> RunResult:
    """Generate the scenario, invoke nltool, parse logs, return result."""
    template = spec.template_path.read_text()
    scenario = build_scenario(template, spec.faults)
    fault_count = sum(1 for m in spec.faults.values() if m != 0)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        scenario_path = td_path / "scenario.cpp"
        scenario_path.write_text(scenario)

        cmd = [
            str(spec.nltool_path),
            "--cmd=run",
            f"--time_to_run={spec.duration_s}",
        ]
        for net in spec.log_nets:
            if not _is_safe_identifier(net):
                raise ValueError(f"unsafe log net: {net!r}")
            cmd += ["-l", net]
        cmd.append(str(scenario_path))

        proc = subprocess.run(
            cmd,
            cwd=td_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        waveforms: dict[str, list[tuple[float, float]]] = {}
        for net in spec.log_nets:
            log_path = td_path / f"log_{net}.log"
            if log_path.exists():
                waveforms[net] = _parse_log(log_path)
            else:
                waveforms[net] = []

    return RunResult(
        waveforms=waveforms,
        stderr=proc.stderr,
        duration_s=spec.duration_s,
        fault_mode_count=fault_count,
    )


def _parse_log(path: Path) -> list[tuple[float, float]]:
    """Parse nltool's `log_<net>.log` into a list of (time, value) tuples."""
    out: list[tuple[float, float]] = []
    for line in path.read_text().splitlines():
        m = LOG_LINE_RE.match(line)
        if m:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def waveforms_to_json(waveforms: dict[str, list[tuple[float, float]]]) -> dict:
    """Convert tuples to plain lists for JSON serialization."""
    return {net: [[t, v] for t, v in samples] for net, samples in waveforms.items()}


__all__ = [
    "RunSpec",
    "RunResult",
    "MODE_LABELS",
    "build_scenario",
    "run",
    "waveforms_to_json",
]
