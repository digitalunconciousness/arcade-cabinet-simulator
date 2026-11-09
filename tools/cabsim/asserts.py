# license:CC0-1.0
"""Effect-test assertions.

Each assertion takes its YAML arguments, the baseline run and the faulted
run, and returns (passed, details). details holds the numbers the verdict
rests on, so the evidence shows why a test passed or failed.
"""

from __future__ import annotations

from typing import Callable

from .mame import RunResult


def _window(args: dict, run: RunResult) -> list[int]:
    lo = int(args.get("from", 0))
    hi = int(args.get("to", max(run.hashes) if run.hashes else 0))
    return [f for f in range(lo, hi + 1)]


def _ram(run: RunResult, args: dict) -> bytes:
    key = (args["ram"], int(args["at"]))
    if key not in run.ram:
        raise KeyError(f"no RAM dump {key[0]} at frame {key[1]} (add it to run.ram and run.checkpoints)")
    return run.ram[key]


def frame_hash_differs(args, base, fault):
    frames = _window(args, base)
    differ = sum(1 for f in frames if fault.hashes.get(f) != base.hashes.get(f))
    frac = differ / len(frames) if frames else 0.0
    need = float(args.get("min_fraction", 0.5))
    return frac >= need, {"frames": len(frames), "differing": differ, "fraction": round(frac, 4), "min_fraction": need}


def frame_hash_matches_baseline(args, base, fault):
    frames = _window(args, base)
    bad = [f for f in frames if fault.hashes.get(f) != base.hashes.get(f)]
    return not bad, {"frames": len(frames), "differing": len(bad), "first_differing": bad[0] if bad else None}


def screen_frozen(args, base, fault):
    """The faulted screen stops changing in the window (at most max_distinct
    different pictures, default 1), while the baseline keeps changing."""
    frames = _window(args, base)
    fault_distinct = len({fault.hashes.get(f) for f in frames})
    base_distinct = len({base.hashes.get(f) for f in frames})
    most = int(args.get("max_distinct", 1))
    return fault_distinct <= most and base_distinct > most, {
        "frames": len(frames), "distinct_faulted": fault_distinct, "distinct_baseline": base_distinct,
        "max_distinct": most}


def repeated_frames(args, base, fault):
    """More consecutive identical frames than the baseline: the game updates the screen less often."""
    frames = _window(args, base)

    def repeats(run):
        return sum(1 for f in frames[1:] if run.hashes.get(f) == run.hashes.get(f - 1))

    b, x = repeats(base), repeats(fault)
    n = max(1, len(frames) - 1)
    need = float(args.get("min_extra_fraction", 0.2))
    return (x - b) / n >= need, {"frames": n, "repeats_baseline": b, "repeats_faulted": x,
                                 "extra_fraction": round((x - b) / n, 4), "min_extra_fraction": need}


def region_bits(args, base, fault):
    data = _ram(fault, args)
    mask = 1 << int(args["bit"])
    want = int(args["level"])
    wrong = sum(1 for b in data if bool(b & mask) != bool(want))
    before = _ram(base, args)
    natural = sum(1 for b in before if bool(b & mask) != bool(want))
    return wrong == 0 and natural > 0, {"bytes": len(data), "bytes_not_at_level": wrong,
                                        "baseline_bytes_not_at_level": natural}


def region_diff(args, base, fault):
    a, b = _ram(base, args), _ram(fault, args)
    n = sum(1 for x, y in zip(a, b) if x != y)
    need = int(args.get("min_bytes", 1))
    return n >= need, {"bytes_differing": n, "min_bytes": need}


def ram_value(args, base, fault):
    data = _ram(fault, args)
    off = int(args["offset"])
    mask = int(args.get("mask", 0xFF))
    want = int(args["value"]) & mask
    got = data[off] & mask
    return got == want, {"offset": off, "value": got, "expected": want, "baseline": _ram(base, args)[off] & mask}


def all_bytes(args, base, fault):
    """Every byte of a RAM dump equals one value (e.g. a dead chip reading as open bus)."""
    data = _ram(fault, args)
    want = int(args["value"])
    wrong = sum(1 for b in data if b != want)
    return wrong == 0, {"bytes": len(data), "bytes_not_equal": wrong, "value": want}


def aliased_pairs(args, base, fault):
    """Every pair of addresses that differ only in one address line holds the same byte."""
    data = _ram(fault, args)
    start = int(args.get("start", 0))
    bit = 1 << int(args["line"])
    pairs = [(a, a | bit) for a in range(len(data)) if not ((a + start) & bit) and (a | bit) < len(data)]
    mismatched = sum(1 for a, b in pairs if data[a] != data[b])
    base_data = _ram(base, args)
    base_mismatched = sum(1 for a, b in pairs if base_data[a] != base_data[b])
    return mismatched == 0 and base_mismatched > 0, {"pairs": len(pairs), "pairs_differing": mismatched,
                                                     "baseline_pairs_differing": base_mismatched}


def count_split(args, base, fault):
    """Count bytes with given values below and above a split offset in a RAM dump.
    expect.empty_side = true: one side has none (and the baseline has both)."""
    values = {int(v) for v in args["values"]}
    split = int(args["split"])

    def count(data):
        low = sum(1 for i, b in enumerate(data) if b in values and i < split)
        high = sum(1 for i, b in enumerate(data) if b in values and i >= split)
        return low, high

    bl, bh = count(_ram(base, args))
    fl, fh = count(_ram(fault, args))
    ok = (min(fl, fh) == 0 and max(fl, fh) > 0 and bl > 0 and bh > 0)
    return ok, {"baseline_low": bl, "baseline_high": bh, "faulted_low": fl, "faulted_high": fh}


def count_values(args, base, fault):
    """How many bytes of a RAM dump hold one of the given values, within
    [min, max] for the faulted run and outside that range for the baseline."""
    values = {int(v) for v in args["values"]}
    lo, hi = int(args.get("min", 0)), int(args.get("max", 10**9))
    f = sum(1 for b in _ram(fault, args) if b in values)
    b = sum(1 for x in _ram(base, args) if x in values)
    return lo <= f <= hi and not (lo <= b <= hi), {"faulted": f, "baseline": b, "min": lo, "max": hi}


def ram_trend(args, base, fault):
    """A RAM byte moves the opposite way to the baseline between two checkpoints."""
    off = int(args["offset"])
    a, b = int(args["from_at"]), int(args["to_at"])

    def delta(run):
        x = run.ram[(args["ram"], a)][off]
        y = run.ram[(args["ram"], b)][off]
        d = (y - x) & 0xFF
        return d - 256 if d >= 128 else d

    db, df = delta(base), delta(fault)
    ok = db != 0 and df != 0 and (db > 0) != (df > 0)
    return ok, {"baseline_delta": db, "faulted_delta": df}


def frame_rows_aliased(args, base, fault):
    """In the faulted exported frame at a checkpoint, every row equals the row
    with one bit of its number forced (a stuck vertical-counter line); the
    baseline frame doesn't."""
    at = int(args["at"])
    bit = 1 << int(args["bit"])
    level = int(args.get("level", 1))

    def mismatches(frame):
        w, h, data = frame
        stride = w * 4
        bad = 0
        for y in range(h):
            src = (y | bit) if level else (y & ~bit)
            if src < h and data[y * stride:(y + 1) * stride] != data[src * stride:(src + 1) * stride]:
                bad += 1
        return bad

    f, b = mismatches(fault.frames[at]), mismatches(base.frames[at])
    return f == 0 and b > 0, {"rows_not_aliased_faulted": f, "rows_not_aliased_baseline": b}


def not_crashed(args, base, fault):
    errs = fault.errors()
    return fault.finished and not errs, {"finished": fault.finished, "plugin_errors": errs[:5]}


def resets(args, base, fault):
    after = int(args.get("after", 0))
    n = fault.resets_after(after)
    nb = base.resets_after(after)
    lo, hi = int(args.get("min", 0)), int(args.get("max", 10**9))
    return lo <= n <= hi, {"resets_faulted": n, "resets_baseline": nb, "min": lo, "max": hi}


def no_plugin_errors(args, base, fault):
    errs = base.errors() + fault.errors()
    return not errs, {"plugin_errors": errs[:5]}


ASSERTIONS: dict[str, Callable] = {
    f.__name__: f for f in (
        frame_hash_differs, frame_hash_matches_baseline, screen_frozen, repeated_frames,
        region_bits, region_diff, ram_value, all_bytes, aliased_pairs, count_split, count_values, ram_trend,
        frame_rows_aliased, not_crashed, resets, no_plugin_errors,
    )
}
