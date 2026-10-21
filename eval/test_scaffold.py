"""Offline contract tests; no network or model services required."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hamar_agent.__main__ import load_fixture, main
from hamar_agent.schemas import Claim, EvidenceStatus, Paragraph, Result, Source
from hamar_agent.summarize import MockSummarizer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "water-synthetic.json"


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.source = load_fixture(FIXTURE)
        self.claims = MockSummarizer().summarize(self.source)

    def test_fixture_is_explicitly_synthetic(self):
        self.assertTrue(self.source.synthetic)
        self.assertIn("SYNTHETIC", self.source.title)
        self.assertIsNone(self.source.url)

    def test_mock_claims_cite_existing_paragraphs(self):
        self.assertEqual(len(self.claims), 2)
        for claim, paragraph in zip(self.claims, self.source.paragraphs):
            self.assertEqual(claim.paragraph_id, paragraph.id)
            self.assertEqual(claim.evidence_quote, paragraph.text)
            self.assertEqual(claim.evidence_status, EvidenceStatus.NOT_CHECKED)

    def test_repeatable_unicode_json(self):
        result = Result(self.source, self.claims)
        self.assertEqual(result.to_json(), Result(self.source, self.claims).to_json())
        data = json.loads(result.to_json())
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["claims"][0]["evidence_status"], "not_checked")
        self.assertIn("Eksempelsjøen", result.to_json())
        self.assertTrue(any("not semantic fact-checking" in w for w in data["warnings"]))

    def test_invalid_records_rejected(self):
        cases = [
            lambda: Paragraph("", "text"),
            lambda: Paragraph("p1", " "),
            lambda: replace(self.source, synthetic="true"),
            lambda: replace(self.source, paragraphs=()),
            lambda: replace(self.source, paragraphs=(Paragraph("p1", "a"), Paragraph("p1", "b"))),
            lambda: Claim("c1", "text", "", "quote"),
            lambda: Claim("c1", "text", "p1", "quote", "verified"),
            lambda: Result(self.source, ()),
            lambda: Result(self.source, (self.claims[0], self.claims[0])),
            lambda: Result(self.source, self.claims, schema_version="2.0"),
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    case()

    def test_mock_rejects_non_synthetic_source(self):
        with self.assertRaises(ValueError):
            MockSummarizer().summarize(replace(self.source, synthetic=False))

    def test_loader_rejects_unlabeled_and_live_fixtures(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for change in ({"synthetic": False}, {"synthetic": "true"}, {"url": "https://example.invalid"}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"
                path.write_text(json.dumps(original | change), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_fixture(path)

    def test_cli_outputs_json_without_network_or_provider_calls(self):
        output = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--fixture", str(FIXTURE)]), 0)
        self.assertEqual(json.loads(output.getvalue())["provider"], "mock")

    def test_injected_mock_response_is_not_promoted_to_verified(self):
        fabricated = Claim("c1", "An unsupported claim", "p999", "Invented excerpt")
        output = io.StringIO()
        with patch.object(MockSummarizer, "summarize", return_value=(fabricated,)):
            with contextlib.redirect_stdout(output):
                main(["--fixture", str(FIXTURE)])
        self.assertEqual(json.loads(output.getvalue())["claims"][0]["evidence_status"], "not_checked")

    def test_cli_invalid_json_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{", encoding="utf-8")
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                main(["--fixture", str(path)])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("Invalid synthetic fixture", error.getvalue())


if __name__ == "__main__":
    unittest.main()