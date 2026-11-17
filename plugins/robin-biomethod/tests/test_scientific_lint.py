"""Offline checks for candidate-plan/SOP lint."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from biomethod.scientific_lint import lint_candidate, lint_goal, save_job_lint

GOAL = {
    "target": {"metric": "degree of substitution", "tolerance": 5},
    "available_equipment": ["temperature control"],
    "constraints": [{"id": "C1", "kind": "hard", "description": "available equipment"}],
}
METHOD = {
    "status": "candidate_unvalidated",
    "candidate_methods": [{"id": "M1", "steps": [{"action": "mix", "parameters": [
        {"name": "temperature", "value": 25, "unit": "deg C", "origin": "reported"},
        {"name": "pH", "value": 7.5, "unit": "", "origin": "proposed"},
    ]}]}],
    "constraint_assessments": [{"id": "C1", "status": "compatible"}],
    "validation_experiments": [{"id": "E1", "independent_batches": 3,
        "readouts": [{"metric": "degree of substitution"}]}],
}


class ScientificLintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "task/source").mkdir(parents=True)
        self.source = self.root / "task/source"
        self.artifact = self.root / "method.json"
        (self.source / "goal.json").write_text(json.dumps(GOAL))
        (self.source / "profile.json").write_text(json.dumps({"checks": ["Confirm lot identity"]}))
        self.artifact.write_text(json.dumps(METHOD))
        self.assessment = patch("biomethod.scientific_lint.assess", return_value={"valid": True, "errors": []})
        self.assessment.start()
        self.addCleanup(self.assessment.stop)

    def write_method(self, data):
        self.artifact.write_text(json.dumps(data))

    def test_clear_candidate_never_claims_lab_approval(self):
        result = lint_candidate(self.source, self.artifact)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "candidate_for_human_review")
        self.assertFalse(result["laboratory_authorized"])
        self.assertIn("Confirm lot identity", result["human_review_questions"])

    def test_unit_missing_is_warning_not_chemistry_verdict(self):
        method = copy.deepcopy(METHOD)
        method["candidate_methods"][0]["steps"][0]["parameters"][0]["unit"] = ""
        self.write_method(method)
        result = lint_candidate(self.source, self.artifact)
        self.assertTrue(result["valid"])
        self.assertIn("SOP-002", [x["id"] for x in result["findings"]])

    def test_nonfinite_number_is_blocker(self):
        method = copy.deepcopy(METHOD)
        method["candidate_methods"][0]["steps"][0]["parameters"][0]["value"] = math.inf
        self.write_method(method)
        result = lint_candidate(self.source, self.artifact)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "machine_check_failed")
        self.assertIn("SOP-001", [x["id"] for x in result["findings"]])

    def test_unknown_parameter_is_unresolved_draft(self):
        method = copy.deepcopy(METHOD)
        method["candidate_methods"][0]["steps"][0]["parameters"][0].update(value=None, origin="unknown")
        self.write_method(method)
        result = lint_candidate(self.source, self.artifact)
        self.assertEqual(result["status"], "unresolved_draft")
        self.assertTrue(result["unresolved_critical_prerequisites"])

    def test_hard_constraint_unresolved(self):
        method = copy.deepcopy(METHOD)
        method["constraint_assessments"][0]["status"] = "unknown"
        self.write_method(method)
        result = lint_candidate(self.source, self.artifact)
        self.assertIn("PLAN-001", [x["id"] for x in result["findings"]])
        self.assertEqual(result["status"], "unresolved_draft")

    def test_batch_one_warns_but_does_not_refuse_pilot(self):
        method = copy.deepcopy(METHOD)
        method["validation_experiments"][0]["independent_batches"] = 1
        self.write_method(method)
        result = lint_candidate(self.source, self.artifact)
        self.assertIn("PLAN-002", [x["id"] for x in result["findings"]])
        self.assertTrue(result["valid"])

    def test_intake_warnings_are_nonblocking(self):
        result = lint_goal({"target": {"tolerance": None}, "available_equipment": [], "constraints": []})
        self.assertEqual(len(result["warnings"]), 3)
        self.assertFalse(result["laboratory_authorized"])

    def test_job_write_requires_verified_proof(self):
        with self.assertRaises(ValueError):
            save_job_lint(self.root, {"verified": False, "delivery_artifact": str(self.artifact)})
        result = save_job_lint(self.root, {"verified": True, "delivery_artifact": str(self.artifact)})
        self.assertTrue((self.root / "scientific-lint.json").is_file())
        self.assertEqual(result["status"], "candidate_for_human_review")


if __name__ == "__main__":
    unittest.main()
