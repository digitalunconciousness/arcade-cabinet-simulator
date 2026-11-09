# license:CC0-1.0
"""Tests for the effect-test runner: plan building, YAML loading and the
assertion logic. No MAME needed."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.cabsim import asserts  # noqa: E402
from tools.cabsim.effect import build_plan, load  # noqa: E402
from tools.cabsim.mame import RunResult  # noqa: E402


def run(hashes=None, ram=None, events=None, finished=True) -> RunResult:
    return RunResult(hashes=hashes or {}, ram=ram or {}, events=events or [], finished=finished)


TEST = {
    "id": "x/y", "romset": "s",
    "run": {"end_frame": 100, "checkpoints": [50], "ram": [{"name": "r", "start": 0, "end": 3}],
            "events": [{"frame": 70, "type": "button", "port": ":IN1", "field": "Coin 1", "down": True}]},
    "inject": {"at_frame": 40, "primitive": "data_bit_stuck", "params": {"bit": 1}},
    "repair": {"at_frame": 80, "action": "clear_and_hard_reset"},
}


class PlanTests(unittest.TestCase):
    def test_baseline_has_everything_but_the_fault(self):
        base = build_plan(TEST, faulted=False)
        types = [(e["frame"], e["type"]) for e in base["events"]]
        self.assertEqual(types, [(70, "button"), (80, "reset")])
        self.assertEqual(base["events"][1]["kind"], "hard")

    def test_faulted_plan_applies_then_clears_before_the_reset(self):
        fault = build_plan(TEST, faulted=True)
        types = [(e["frame"], e["type"]) for e in fault["events"]]
        self.assertEqual(types, [(40, "apply"), (70, "button"), (80, "clear_all"), (80, "reset")])

    def test_plain_clear_has_no_reset(self):
        t = dict(TEST, repair={"at_frame": 80, "action": "clear"})
        self.assertEqual([e["type"] for e in build_plan(t, faulted=False)["events"]], ["button"])

    def test_every_committed_test_loads_and_builds(self):
        files = sorted((REPO / "tests" / "effect").rglob("*.yaml"))
        self.assertTrue(files)
        for f in files:
            t = load(f)
            for faulted in (False, True):
                plan = build_plan(t, faulted)
                self.assertEqual(plan["end_frame"], t["run"]["end_frame"], f)
            for spec in t.get("expect", []) + t.get("expect_after_repair", []):
                (name, _), = spec.items()
                self.assertTrue(name == "snapshot" or name in asserts.ASSERTIONS, f"{f}: {name}")


class AssertionTests(unittest.TestCase):
    def test_frame_hash_differs_counts_the_window(self):
        b = run({1: "a", 2: "b", 3: "c", 4: "d"})
        f = run({1: "a", 2: "X", 3: "Y", 4: "d"})
        ok, d = asserts.frame_hash_differs({"from": 2, "to": 4, "min_fraction": 0.6}, b, f)
        self.assertTrue(ok)
        self.assertEqual(d["differing"], 2)
        ok, _ = asserts.frame_hash_differs({"from": 2, "to": 4, "min_fraction": 0.7}, b, f)
        self.assertFalse(ok)

    def test_matches_baseline(self):
        b = run({1: "a", 2: "b"})
        self.assertTrue(asserts.frame_hash_matches_baseline({"from": 1, "to": 2}, b, run({1: "a", 2: "b"}))[0])
        self.assertFalse(asserts.frame_hash_matches_baseline({"from": 1, "to": 2}, b, run({1: "a", 2: "c"}))[0])

    def test_screen_frozen_needs_a_moving_baseline(self):
        b = run({1: "a", 2: "b", 3: "c"})
        self.assertTrue(asserts.screen_frozen({"from": 1, "to": 3}, b, run({1: "z", 2: "z", 3: "z"}))[0])
        self.assertFalse(asserts.screen_frozen({"from": 1, "to": 3}, run({1: "a", 2: "a", 3: "a"}),
                                               run({1: "z", 2: "z", 3: "z"}))[0])

    def test_repeated_frames(self):
        b = run({i: str(i) for i in range(1, 11)})
        f = run({i: str(i // 2) for i in range(1, 11)})
        ok, d = asserts.repeated_frames({"from": 1, "to": 10, "min_extra_fraction": 0.3}, b, f)
        self.assertTrue(ok, d)

    def test_region_bits(self):
        b = run(ram={("r", 5): bytes([0x08, 0x00])})
        f = run(ram={("r", 5): bytes([0x00, 0x00])})
        self.assertTrue(asserts.region_bits({"ram": "r", "at": 5, "bit": 3, "level": 0}, b, f)[0])
        self.assertFalse(asserts.region_bits({"ram": "r", "at": 5, "bit": 3, "level": 0}, f, f)[0])

    def test_aliased_pairs(self):
        b = run(ram={("r", 5): bytes([1, 2, 3, 4])})
        f = run(ram={("r", 5): bytes([1, 2, 1, 2])})
        ok, d = asserts.aliased_pairs({"ram": "r", "at": 5, "line": 1}, b, f)
        self.assertTrue(ok, d)
        self.assertEqual(d["pairs"], 2)

    def test_count_split_wants_one_empty_side(self):
        b = run(ram={("r", 5): bytes([0x3F, 0, 0x3F, 0])})
        one_side = run(ram={("r", 5): bytes([0x3F, 0x3F, 0, 0])})
        ok, d = asserts.count_split({"ram": "r", "at": 5, "values": [0x3F], "split": 2}, b, one_side)
        self.assertTrue(ok, d)
        ok, _ = asserts.count_split({"ram": "r", "at": 5, "values": [0x3F], "split": 2}, b, b)
        self.assertFalse(ok)

    def test_ram_trend_wraps_around(self):
        b = run(ram={("r", 1): bytes([250]), ("r", 2): bytes([4])})    # +10 through the wrap
        f = run(ram={("r", 1): bytes([10]), ("r", 2): bytes([2])})     # -8
        ok, d = asserts.ram_trend({"ram": "r", "offset": 0, "from_at": 1, "to_at": 2}, b, f)
        self.assertTrue(ok, d)
        self.assertEqual((d["baseline_delta"], d["faulted_delta"]), (10, -8))

    def test_not_crashed_sees_plugin_errors(self):
        b = run()
        self.assertTrue(asserts.not_crashed({}, b, run(events=[["apply", "1"]]))[0])
        self.assertFalse(asserts.not_crashed({}, b, run(events=[["error", "3", "apply", "boom"]]))[0])
        self.assertFalse(asserts.not_crashed({}, b, run(finished=False))[0])

    def test_resets_counts_after_a_frame(self):
        f = run(events=[["reset", "0"], ["reset", "700"], ["reset", "800"]])
        ok, d = asserts.resets({"after": 600, "min": 2}, run(), f)
        self.assertTrue(ok, d)


if __name__ == "__main__":
    unittest.main()
