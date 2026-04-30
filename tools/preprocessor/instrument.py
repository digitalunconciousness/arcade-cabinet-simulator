#!/usr/bin/env python3
# license:CC0-1.0
"""
Auto-instrumentation preprocessor (Phase 1 scaffold).

Walks a MAME netlist `.cpp` source file and rewrites every `NET_C(net, pin1,
pin2, ...)` connection to route the named signal through a `FAULT_BUFFER`
device. Emits the modified `.cpp` plus a JSON manifest mapping
(reference designator, pin number) -> fault device name so the UI can resolve
clicks to runtime fault targets.

Phase 1 deliverable: scaffold with CLI, manifest schema, and a working
trivial example. NOT YET wired up to handle every Centipede edge case —
multi-bit buses, NET_C with shared nets, .hxx includes, etc. are TODO.

Usage:
    python -m tools.preprocessor.instrument \\
        --input  src/lib/netlist/devices/nld_test.cpp \\
        --output build/instrumented/nld_test.cpp \\
        --manifest build/instrumented/nld_test.manifest.json \\
        [--include-pins R1.1,R1.2]   # whitelist; default = instrument all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Matches: NET_C(arg1, arg2, ..., argN)
# Pins look like REFDES.PIN — REFDES is alphanumeric+underscore, PIN is the same.
NET_C_RE = re.compile(r"NET_C\s*\(\s*([^)]+?)\s*\)")
PIN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\.([A-Za-z_0-9]+)\s*$")


@dataclass
class FaultEntry:
    """One fault-injection point in the manifest."""
    refdes: str
    pin: str
    fault_device: str
    source_line: int
    original_net: str

    def key(self) -> str:
        return f"{self.refdes}.{self.pin}"


@dataclass
class InstrumentResult:
    """Result of instrumenting one .cpp file."""
    instrumented_cpp: str
    manifest: list[FaultEntry] = field(default_factory=list)


def parse_net_c_args(arg_blob: str) -> list[str]:
    """Split the comma-separated NET_C arg list, trimming whitespace."""
    return [a.strip() for a in arg_blob.split(",") if a.strip()]


def is_pin_ref(arg: str) -> bool:
    """True if the argument looks like REFDES.PIN."""
    return PIN_RE.match(arg) is not None


def fault_device_name(refdes: str, pin: str) -> str:
    """Stable, unique name for the FAULT_BUFFER inserted on this pin."""
    return f"FB_{refdes}_{pin}"


def instrument(
    source: str,
    pin_whitelist: set[str] | None = None,
) -> InstrumentResult:
    """Rewrite NET_C(...) lines to route signals through FAULT_BUFFER.

    For each pin reference REFDES.PIN that we choose to instrument:
    - the original connection becomes REFDES.PIN -> FB_<REFDES>_<PIN>.A
    - downstream consumers connect to FB_<REFDES>_<PIN>.Y instead

    Phase 1 scaffold: this only handles the simplest case where NET_C ties
    together exactly one driver pin and one receiver pin. Multi-driver and
    bus-style connections are TODO (Phase 2 of the preprocessor).
    """

    out_lines: list[str] = []
    manifest: list[FaultEntry] = []
    seen_refs: set[str] = set()

    for line_no, line in enumerate(source.splitlines(keepends=True), start=1):
        match = NET_C_RE.search(line)
        if not match:
            out_lines.append(line)
            continue

        args = parse_net_c_args(match.group(1))
        pin_args = [a for a in args if is_pin_ref(a)]

        # Heuristic: only rewrite when there are exactly two pin refs and
        # nothing else (a simple driver -> receiver wire).
        if len(args) != len(pin_args) or len(pin_args) != 2:
            out_lines.append(line)
            continue

        # Apply whitelist if any.
        if pin_whitelist is not None:
            if not any(p in pin_whitelist for p in pin_args):
                out_lines.append(line)
                continue

        driver, receiver = pin_args
        d_ref, d_pin = PIN_RE.match(driver).groups()
        fb = fault_device_name(d_ref, d_pin)

        # Skip if we've already instrumented this driver pin in another NET_C.
        if fb in seen_refs:
            # Just rewrite the receiver to listen to FB.Y.
            new_line = line.replace(driver, f"{fb}.Y")
            out_lines.append(new_line)
            continue

        seen_refs.add(fb)
        indent = re.match(r"^\s*", line).group(0)
        device_decl = f"{indent}FAULT_BUFFER({fb}, {driver})\n"
        new_net_c = f"{indent}NET_C({fb}.Y, {receiver})\n"

        out_lines.append(device_decl)
        out_lines.append(new_net_c)

        manifest.append(
            FaultEntry(
                refdes=d_ref,
                pin=d_pin,
                fault_device=fb,
                source_line=line_no,
                original_net=match.group(0),
            )
        )

    return InstrumentResult(
        instrumented_cpp="".join(out_lines),
        manifest=manifest,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="instrument", description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="Source netlist .cpp")
    parser.add_argument("--output", required=True, type=Path,
                        help="Destination netlist .cpp (instrumented)")
    parser.add_argument("--manifest", required=True, type=Path,
                        help="Destination JSON manifest")
    parser.add_argument("--include-pins", default=None,
                        help="Comma-separated whitelist of REFDES.PIN to "
                             "instrument. Default: all.")
    args = parser.parse_args(argv)

    whitelist: set[str] | None = None
    if args.include_pins:
        whitelist = set(p.strip() for p in args.include_pins.split(",")
                        if p.strip())

    source = args.input.read_text()
    result = instrument(source, pin_whitelist=whitelist)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.instrumented_cpp)
    args.manifest.write_text(json.dumps(
        [asdict(e) for e in result.manifest],
        indent=2,
    ))

    print(f"instrumented {len(result.manifest)} pins -> {args.output}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
