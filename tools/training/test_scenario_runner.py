#!/usr/bin/env python3
# license:CC0-1.0
"""
Unit tests for tools/training/scenario_runner.py.

Runs without a live server — all HTTP calls are mocked.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the repo root is on sys.path so relative imports work.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.training.scenario_runner as sr


SCENARIOS_DIR = REPO_ROOT / "tests" / "scenarios"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation(unittest.TestCase):
    """Every .json file in tests/scenarios/ must have required fields."""

    def _scenario_files(self):
        return sorted(SCENARIOS_DIR.glob("*.json"))

    def test_scenario_files_exist(self):
        files = self._scenario_files()
        self.assertGreaterEqual(len(files), 12, "expected at least 12 scenario files")

    def test_all_scenarios_load(self):
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                self.assertIn("id", scenario)
                self.assertIn("title", scenario)
                self.assertIn("faults", scenario)
                self.assertIn("clear_faults", scenario)
                self.assertIn("coverage", scenario)

    def test_required_metadata_fields(self):
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                self.assertIsInstance(scenario["id"], str)
                self.assertTrue(scenario["id"], "id must be non-empty")
                self.assertIsInstance(scenario["title"], str)
                self.assertTrue(scenario["title"], "title must be non-empty")
                self.assertIsInstance(scenario["faults"], list)
                self.assertIsInstance(scenario["clear_faults"], list)
                self.assertIsInstance(scenario["coverage"], list)
                self.assertGreater(len(scenario["coverage"]), 0)

    def test_coverage_entries_are_non_empty_strings(self):
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                for entry in scenario["coverage"]:
                    self.assertIsInstance(entry, str)
                    self.assertTrue(entry.strip())

    def test_difficulty_range(self):
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                difficulty = scenario.get("difficulty", 1)
                self.assertIn(difficulty, range(1, 6),
                              f"difficulty {difficulty} out of range 1-5")

    def test_fault_types_valid(self):
        valid_types = {"peripheral", "mame_stuck_byte", "mame_clear_stuck", "crt_overlay"}
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                for fault in scenario["faults"] + scenario["clear_faults"]:
                    ftype = fault.get("type", "peripheral")
                    self.assertIn(ftype, valid_types,
                                  f"unknown fault type {ftype!r} in {path.name}")

    def test_subsystems_list(self):
        for path in self._scenario_files():
            with self.subTest(file=path.name):
                scenario = sr.load_scenario(path)
                subs = scenario.get("subsystems", [])
                self.assertIsInstance(subs, list)

    def test_all_12_scenario_ids_present(self):
        scenarios = sr.load_all_scenarios()
        ids = {s["id"] for s in scenarios}
        expected = {
            "dim-psu-5v",
            "vertical-collapse",
            "dead-trackball-x",
            "reversed-trackball",
            "sprite-ram-glitch",
            "address-decoder-rom",
            "hum-amp",
            "dead-amp",
            "sync-lock",
            "ringing-ghosting",
            "weak-focus",
            "multi-fault",
        }
        for eid in expected:
            with self.subTest(id=eid):
                self.assertIn(eid, ids)


# ---------------------------------------------------------------------------
# scenario_metadata
# ---------------------------------------------------------------------------

class TestScenarioMetadata(unittest.TestCase):
    def _load_first(self):
        return sr.load_all_scenarios()[0]

    def test_metadata_keys(self):
        scenario = self._load_first()
        meta = sr.scenario_metadata(scenario)
        for key in ("id", "title", "difficulty", "subsystems", "coverage", "backstory"):
            self.assertIn(key, meta)

    def test_metadata_omits_faults(self):
        scenario = self._load_first()
        meta = sr.scenario_metadata(scenario)
        self.assertNotIn("faults", meta)
        self.assertNotIn("clear_faults", meta)


# ---------------------------------------------------------------------------
# load_all_scenarios
# ---------------------------------------------------------------------------

class TestLoadAllScenarios(unittest.TestCase):
    def test_sorted_order(self):
        scenarios = sr.load_all_scenarios()
        filenames = sorted(SCENARIOS_DIR.glob("*.json"))
        self.assertEqual(len(scenarios), len(filenames))

    def test_empty_directory(self, tmp_path=None):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            result = sr.load_all_scenarios(Path(d))
            self.assertEqual(result, [])

    def test_skips_invalid_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text("{not valid json}")
            result = sr.load_all_scenarios(Path(d))
            self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# apply_scenario / clear_scenario (mocked HTTP)
# ---------------------------------------------------------------------------

def _mock_response(status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"ok": True}
    return r


class TestApplyScenario(unittest.TestCase):
    """apply_scenario calls _apply_fault for each fault; clear_scenario for clear_faults."""

    def _first_scenario_with_type(self, fault_type):
        for s in sr.load_all_scenarios():
            if any(f.get("type", "peripheral") == fault_type for f in s["faults"]):
                return s
        return None

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_returns_id_and_applied(self, mock_post):
        mock_post.return_value = _mock_response(200)
        scenario = sr.load_all_scenarios()[0]
        result = sr.apply_scenario(scenario)
        self.assertEqual(result["id"], scenario["id"])
        self.assertTrue(result["applied"])
        self.assertIsInstance(result["faults"], list)

    @patch("tools.training.scenario_runner.requests.post")
    def test_clear_returns_id_and_cleared(self, mock_post):
        mock_post.return_value = _mock_response(200)
        scenario = sr.load_all_scenarios()[0]
        result = sr.clear_scenario(scenario)
        self.assertEqual(result["id"], scenario["id"])
        self.assertTrue(result["cleared"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_peripheral_fault(self, mock_post):
        mock_post.return_value = _mock_response(200)
        fault = {"type": "peripheral", "target": "PSU1", "fault": "sagging_mains"}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertEqual(result["type"], "peripheral")
        self.assertEqual(result["target"], "PSU1")
        self.assertTrue(result["ok"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_mame_stuck_byte(self, mock_post):
        mock_post.return_value = _mock_response(200)
        fault = {"type": "mame_stuck_byte", "addr": "0x0540", "value": 255}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertEqual(result["type"], "mame_stuck_byte")
        self.assertTrue(result["ok"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_mame_clear_stuck(self, mock_post):
        mock_post.return_value = _mock_response(200)
        fault = {"type": "mame_clear_stuck"}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertEqual(result["type"], "mame_clear_stuck")
        self.assertTrue(result["ok"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_crt_overlay(self, mock_post):
        mock_post.return_value = _mock_response(200)
        fault = {"type": "crt_overlay", "effect": "dim_picture", "brightness": 0.4}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertEqual(result["type"], "crt_overlay")
        self.assertTrue(result["ok"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_http_error_marked_not_ok(self, mock_post):
        mock_post.return_value = _mock_response(500)
        fault = {"type": "peripheral", "target": "PSU1", "fault": "sagging_mains"}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertFalse(result["ok"])

    @patch("tools.training.scenario_runner.requests.post")
    def test_connection_error_handled(self, mock_post):
        import requests as _req
        mock_post.side_effect = _req.ConnectionError("refused")
        fault = {"type": "peripheral", "target": "PSU1", "fault": "sagging_mains"}
        result = sr._apply_fault(fault, "http://127.0.0.1:5050")
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    @patch("tools.training.scenario_runner.requests.post")
    def test_apply_all_scenarios_no_crash(self, mock_post):
        """Smoke test: apply+clear every scenario without raising."""
        mock_post.return_value = _mock_response(200)
        for scenario in sr.load_all_scenarios():
            with self.subTest(id=scenario["id"]):
                sr.apply_scenario(scenario)
                sr.clear_scenario(scenario)


if __name__ == "__main__":
    unittest.main(verbosity=2)
