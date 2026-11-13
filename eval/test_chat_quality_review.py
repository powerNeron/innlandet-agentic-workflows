"""Offline tests for synthetic, human-scored chat-quality review files."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from harness.chat_quality_eval import CASES
from harness.chat_quality_review import CRITERIA, load_run, make_template, summarize_reviews


class ChatQualityReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.run_dir = self.folder / "run"
        self.run_dir.mkdir()
        dataset = hashlib.sha256(json.dumps(CASES, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        summary = {
            "suite": "primary", "dataset_sha256": dataset,
            "system_sha256": "c" * 64, "context_system_sha256": "d" * 64,
            "source_sha256": {"chat.py": "e" * 64},
            "runtime": {"provider": "ollama", "model": "fixture-model", "version": "fixture-1",
                        "digest": "b" * 64, "temperature": 0, "seed": 0, "num_predict": 512},
            "case_count": len(CASES), "executed": len(CASES),
        }
        (self.run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        for case in CASES:
            row = {"case": case, "text": "synthetic answer", "http_status": 200}
            (self.run_dir / f"{case['id']}.json").write_text(json.dumps(row), encoding="utf-8")
        self.run = load_run(self.run_dir)
        self.template = make_template(self.run)

    def tearDown(self):
        self.temp.cleanup()

    def submission(self, reviewer, accuracy):
        data = copy.deepcopy(self.template)
        data["reviewer_code"] = reviewer
        data["reviewed_at"] = "2026-11-13"
        for item in data["reviews"]:
            item["scores"] = {criterion: 2 for criterion in CRITERIA}
            item["scores"]["accuracy"] = accuracy
        return data

    def test_template_binds_review_to_run_without_copying_answer_text(self):
        self.assertEqual(self.template["run"]["dataset_sha256"], self.run["dataset_sha256"])
        self.assertEqual({item["case_id"] for item in self.template["reviews"]}, set(self.run["case_ids"]))
        self.assertNotIn("synthetic answer", json.dumps(self.template))
        self.assertEqual(self.template["run"]["system_sha256"], "c" * 64)

    def test_summary_keeps_reviewers_separate_and_exposes_disagreement(self):
        result = summarize_reviews(self.run, [self.submission("rater_a", 2), self.submission("rater_b", 0)])
        self.assertEqual(result["reviewer_count"], 2)
        self.assertEqual(result["review_count"], 2 * len(CASES))
        self.assertEqual(result["reviewer_summaries"][0]["mean_by_criterion"]["accuracy"], 2.0)
        self.assertEqual(result["case_summaries"][0]["score_range_by_criterion"]["accuracy"], 2)

    def test_rejects_incomplete_or_mismatched_reviews(self):
        incomplete = self.submission("rater_a", 2)
        incomplete["reviews"].pop()
        with self.assertRaisesRegex(ValueError, "every case"):
            summarize_reviews(self.run, [incomplete])
        mismatch = self.submission("rater_a", 2)
        mismatch["run"]["dataset_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            summarize_reviews(self.run, [mismatch])

    def test_rejects_malformed_scores_cases_tags_and_extra_fields(self):
        mutations = (
            lambda data: data["reviews"][0]["scores"].update(accuracy=True),
            lambda data: data["reviews"].append(copy.deepcopy(data["reviews"][0])),
            lambda data: data["reviews"][0].update(tags=["arbitrary text"]),
            lambda data: data["reviews"][0].update(tags=[{}]),
            lambda data: data["reviews"][0].update(case_id={}),
            lambda data: data.update(notes="not allowed"),
            lambda data: data["reviews"][0].update(notes="not allowed"),
        )
        for mutate in mutations:
            data = self.submission("rater_a", 2)
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                summarize_reviews(self.run, [data])

    def test_rejects_changed_synthetic_case_even_with_a_digest_string(self):
        path = self.run_dir / f"{CASES[0]['id']}.json"
        row = json.loads(path.read_text(encoding="utf-8"))
        row["case"]["message"] = "changed"
        path.write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fixed synthetic definition"):
            load_run(self.run_dir)

    def test_rejects_duplicate_reviewers_in_one_report(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            summarize_reviews(self.run, [self.submission("same", 2), self.submission("same", 1)])


if __name__ == "__main__":
    unittest.main()
