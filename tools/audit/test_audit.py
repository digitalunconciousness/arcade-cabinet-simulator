# license:CC0-1.0
"""Tests for the audit's comparison and verdict logic. No MAME needed."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_audit as ra  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _cap(hashes: dict[int, str], ram: dict[int, bytes] | None = None, resets=None) -> ra.Capture:
    return ra.Capture(hashes=hashes, ram=ram or {}, resets=resets or [])


def _cmd(cmd: dict, ok: bool = True) -> dict:
    reply = {"ok": True} if ok else {"ok": False, "error": f"unknown command: {cmd['cmd']}"}
    return {"cmd": cmd, "reply": reply}


ZERO = bytes(0x800)


class CompareTests(unittest.TestCase):
    def test_identical_runs_have_no_difference(self):
        base = _cap({1: "a", 2: "b", 3: "c"}, {3: ZERO})
        diff = ra.compare(base, _cap({1: "a", 2: "b", 3: "c"}, {3: ZERO}), pause_frame=1)
        self.assertEqual(diff["frames_compared"], 2)
        self.assertEqual(diff["frames_differing"], 0)
        self.assertEqual(ra.verdict(diff, []), "not-sent")

    def test_frames_before_injection_are_ignored(self):
        base = _cap({1: "a", 2: "b"})
        diff = ra.compare(base, _cap({1: "X", 2: "b"}), pause_frame=1)
        self.assertEqual(diff["frames_differing"], 0)

    def test_screen_difference_is_a_change(self):
        base = _cap({1: "a", 2: "b", 3: "c"})
        diff = ra.compare(base, _cap({1: "a", 2: "B", 3: "c"}), pause_frame=1)
        self.assertEqual(diff["first_differing_frame"], 2)
        self.assertEqual(ra.verdict(diff, [_cmd({"cmd": "stuck_byte", "addr": 5, "value": 1})]),
                         "changes-game-output")

    def test_missing_frames_count_as_a_change(self):
        diff = ra.compare(_cap({1: "a", 2: "b", 3: "c"}), _cap({1: "a", 2: "b"}), pause_frame=1)
        self.assertEqual(diff["frames_missing"], 1)
        self.assertEqual(ra.verdict(diff, []), "changes-game-output")

    def test_only_injected_cells_differ(self):
        run_ram = bytearray(ZERO)
        run_ram[0x590] = 0xFF
        cmds = [_cmd({"cmd": "stuck_byte", "addr": 0x590, "value": 255})]
        diff = ra.compare(_cap({1: "a", 2: "b"}, {2: ZERO}), _cap({1: "a", 2: "b"}, {2: bytes(run_ram)}),
                          pause_frame=1, injected=ra.injected_addresses(cmds))
        self.assertEqual(diff["ram_bytes_differing"]["2"]["playfield_0400_07bf"], 1)
        self.assertEqual(diff["consequence_ram_bytes"]["2"]["playfield_0400_07bf"], 0)
        self.assertEqual(ra.verdict(diff, cmds), "injected-cells-only")

    def test_other_ram_changes_are_consequences(self):
        run_ram = bytearray(ZERO)
        run_ram[0x590] = 0xFF
        run_ram[0x0010] = 0x01
        cmds = [_cmd({"cmd": "stuck_byte", "addr": 0x590, "value": 255})]
        diff = ra.compare(_cap({2: "b"}, {2: ZERO}), _cap({2: "b"}, {2: bytes(run_ram)}),
                          pause_frame=1, injected=ra.injected_addresses(cmds))
        self.assertEqual(diff["consequence_ram_bytes"]["2"]["work_ram_0000_03ff"], 1)
        self.assertEqual(ra.verdict(diff, cmds), "changes-game-output")

    def test_reset_difference_is_a_change(self):
        diff = ra.compare(_cap({2: "b"}), _cap({2: "b"}, resets=["reset 700"]), pause_frame=1)
        self.assertEqual(ra.verdict(diff, []), "changes-game-output")

    def test_rejected_and_accepted_commands(self):
        diff = ra.compare(_cap({2: "b"}), _cap({2: "b"}), pause_frame=1)
        rejected = [_cmd({"cmd": "set_crt_fault", "effect": "dim"}, ok=False)]
        self.assertEqual(ra.verdict(diff, rejected), "rejected-by-plugin")
        accepted = [_cmd({"cmd": "stuck_byte", "addr": 1, "value": None})]
        self.assertEqual(ra.verdict(diff, accepted), "no-change")


class FaultCommandTests(unittest.TestCase):
    def test_baseline_commands_cancel_out(self):
        stim = _cmd({"cmd": "press_button", "name": "P1 Button 1"}, ok=False)
        base_log = {"plugin": [stim]}
        run_log = {"plugin": [stim, _cmd({"cmd": "get_state"}),
                              _cmd({"cmd": "set_crt_fault", "effect": "dim"}, ok=False)]}
        extra = ra.fault_commands(run_log, base_log)
        self.assertEqual([e["cmd"]["cmd"] for e in extra], ["set_crt_fault"])

    def test_repeated_commands_are_counted(self):
        tb = _cmd({"cmd": "trackball_delta", "dx": 8, "dy": 0}, ok=False)
        extra = ra.fault_commands({"plugin": [tb, tb, tb]}, {"plugin": [tb, tb]})
        self.assertEqual(len(extra), 1)

    def test_held_resume_is_not_a_fault_command(self):
        held = {"cmd": {"cmd": "resume"}, "held_by_audit": True}
        self.assertEqual(ra.fault_commands({"plugin": [held]}, {"plugin": []}), [])


class InventoryTests(unittest.TestCase):
    def test_inventory_covers_every_source(self):
        inv = ra.inventory_mod.build_inventory(REPO)
        kinds = {}
        for e in inv:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        ids = [e["id"] for e in inv]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(kinds["scenario"], len(list((REPO / "tests/scenarios").glob("*.json"))))
        self.assertEqual(kinds["schematic"], 2 * 3 * 10)
        self.assertGreater(kinds["peripheral"], 40)


if __name__ == "__main__":
    unittest.main()
