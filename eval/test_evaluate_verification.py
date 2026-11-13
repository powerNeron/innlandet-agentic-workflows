"""Tests for the synthetic verifier evaluation report."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.evaluate_verification import EXPECTED, evaluate
from hamar_agent.sources import load_source


class VerificationEvaluationTests(unittest.TestCase):
    def test_known_synthetic_issues_are_detected_and_clean_control_passes(self):
        source = load_source("synthetic-verification-demo")
        report = evaluate(source)
        self.assertEqual(report["known_issue_cases"], len(EXPECTED))
        self.assertEqual(report["detected_expected_findings"], len(EXPECTED))
        self.assertEqual(report["missed_expected_findings"], 0)
        self.assertEqual(report["recall"], 1.0)
        self.assertTrue(report["clean_control"]["passed"])
        self.assertTrue(all("actual_findings" in case for case in report["cases"]))


if __name__ == "__main__":
    unittest.main()
