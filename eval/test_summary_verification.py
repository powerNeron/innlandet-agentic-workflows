"""Tests for structured summaries and offline model-response validation."""
from dataclasses import replace
from pathlib import Path
import unittest

from hamar_agent.__main__ import load_fixture
from hamar_agent.revision import OneRevisionGate, RevisionLimitExceeded
from hamar_agent.schemas import Claim
from hamar_agent.summarize import (
    MockScenario,
    MockSummarizer,
    SummaryResponseError,
    parse_claim_response,
)
from hamar_agent.verify import FindingCode, verify_claims, verify_response


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "verification-synthetic.json"


class SummarizerTests(unittest.TestCase):
    def setUp(self):
        self.source = load_fixture(FIXTURE)

    def test_default_mock_returns_structured_norwegian_claims(self):
        claims = MockSummarizer().summarize(self.source)
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(isinstance(claim, Claim) for claim in claims))
        self.assertTrue(all(claim.text for claim in claims))
        self.assertEqual([claim.paragraph_id for claim in claims], ["p1", "p2"])
        self.assertTrue(all(claim.evidence_quote for claim in claims))

    def test_scenario_responses_are_repeatable(self):
        for scenario in (MockScenario.VALID, MockScenario.INVALID_PARAGRAPH, MockScenario.CHANGED_NUMBER):
            with self.subTest(scenario=scenario):
                mock = MockSummarizer(scenario)
                self.assertEqual(mock.summarize(self.source), mock.summarize(self.source))

    def test_parser_rejects_missing_citation_and_malformed_output(self):
        cases = (
            {"claims": [{"id": "c1", "text": "Påstand", "evidence_quote": "Sitat"}]},
            {"claims": "not a list"},
            {"unexpected": []},
            {"claims": [{"id": "c1", "text": " ", "paragraph_id": "p1", "evidence_quote": "Sitat"}]},
            {"claims": [MockSummarizer._claim("c1", "Påstand", "p1", "Sitat")] * 2},
        )
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(SummaryResponseError):
                parse_claim_response(payload)

    def test_mock_can_emit_intentionally_invalid_examples(self):
        cases = (
            MockScenario.MISSING_CITATION,
            MockScenario.INVALID_PARAGRAPH,
            MockScenario.FABRICATED_QUOTE,
            MockScenario.CHANGED_NUMBER,
            MockScenario.UNSUPPORTED_STATEMENT,
            MockScenario.UNCERTAIN_CLAIM,
            MockScenario.CONFLICTING_CLAIMS,
            MockScenario.MALFORMED_OUTPUT,
        )
        for scenario in cases:
            with self.subTest(scenario=scenario):
                if scenario in (MockScenario.MISSING_CITATION, MockScenario.MALFORMED_OUTPUT):
                    with self.assertRaises(SummaryResponseError):
                        MockSummarizer(scenario).summarize(self.source)
                else:
                    claims = MockSummarizer(scenario).summarize(self.source)
                    self.assertTrue(claims)

    def test_invalid_mock_payloads_flow_into_verifier_findings(self):
        expected = {
            MockScenario.MISSING_CITATION: FindingCode.MISSING_CITATION,
            MockScenario.INVALID_PARAGRAPH: FindingCode.INVALID_PARAGRAPH_ID,
            MockScenario.FABRICATED_QUOTE: FindingCode.FABRICATED_EVIDENCE,
            MockScenario.CHANGED_NUMBER: FindingCode.UNSUPPORTED_NUMBER,
            MockScenario.UNSUPPORTED_STATEMENT: FindingCode.POTENTIALLY_UNSUPPORTED,
            MockScenario.UNCERTAIN_CLAIM: FindingCode.UNCERTAIN_CLAIM,
            MockScenario.CONFLICTING_CLAIMS: FindingCode.CONFLICTING_CLAIMS,
            MockScenario.MALFORMED_OUTPUT: FindingCode.MALFORMED_OUTPUT,
        }
        for scenario, code in expected.items():
            with self.subTest(scenario=scenario):
                payload = MockSummarizer(scenario).response_payload(self.source)
                report = verify_response(self.source, payload)
                self.assertIn(code, {finding.code for finding in report.findings})

    def test_mock_rejects_non_synthetic_source(self):
        with self.assertRaises(ValueError):
            MockSummarizer().summarize(replace(self.source, synthetic=False))


class EvidenceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.source = load_fixture(FIXTURE)

    def test_valid_quote_is_traceable_but_not_asserted_true(self):
        claim = Claim(
            "c1",
            "I denne oppdiktede målingen er hardheten 3 °dH.",
            "p1",
            "I denne oppdiktede målingen er hardheten 3 °dH.",
        )

        report = verify_claims(self.source, (claim,))

        self.assertEqual(report.claims[0].evidence_status.value, "exact_match")
        self.assertFalse(report.has_findings)

    def test_unrelated_statement_is_flagged_as_potentially_unsupported(self):
        claim = Claim("c1", "Kommunen stenger skolen i morgen.", "p1", self.source.paragraphs[0].text)

        report = verify_claims(self.source, (claim,))

        self.assertIn(FindingCode.POTENTIALLY_UNSUPPORTED, {finding.code for finding in report.findings})
        self.assertEqual(report.claims[0].evidence_status.value, "exact_match")

    def test_unknown_paragraph_and_fabricated_excerpt_are_flagged(self):
        claims = (
            Claim("c1", "Påstand", "p999", "Sitat"),
            Claim("c2", "Påstand", "p1", "Oppdiktet sitat"),
        )

        report = verify_claims(self.source, claims)

        self.assertEqual(
            {finding.code for finding in report.findings},
            {FindingCode.INVALID_PARAGRAPH_ID, FindingCode.FABRICATED_EVIDENCE},
        )
        self.assertTrue(all(claim.evidence_status.value == "missing" for claim in report.claims))

    def test_missing_citation_and_malformed_output_are_reported(self):
        missing = verify_response(self.source, {
            "claims": [{"id": "c1", "text": "Påstand", "evidence_quote": "sitat"}]
        })
        malformed = verify_response(self.source, {"claims": "not a list"})

        self.assertEqual(missing.findings[0].code, FindingCode.MISSING_CITATION)
        self.assertEqual(malformed.findings[0].code, FindingCode.MALFORMED_OUTPUT)
        self.assertEqual(verify_claims(self.source, ()).findings[0].code, FindingCode.MALFORMED_OUTPUT)

    def test_changed_number_and_conflicting_claims_are_detected(self):
        changed = MockSummarizer(MockScenario.CHANGED_NUMBER).summarize(self.source)
        changed_report = verify_claims(self.source, changed)
        conflict = MockSummarizer(MockScenario.CONFLICTING_CLAIMS).summarize(self.source)
        conflict_report = verify_claims(self.source, conflict)

        self.assertIn(FindingCode.UNSUPPORTED_NUMBER, {finding.code for finding in changed_report.findings})
        self.assertIn(FindingCode.CONFLICTING_CLAIMS, {finding.code for finding in conflict_report.findings})

    def test_conflicting_evidence_does_not_get_promoted_to_truth(self):
        report = verify_claims(self.source, MockSummarizer(MockScenario.CONFLICTING_CLAIMS).summarize(self.source))

        self.assertTrue(all(claim.evidence_status.value == "exact_match" for claim in report.claims))
        self.assertTrue(any(finding.code is FindingCode.CONFLICTING_CLAIMS for finding in report.findings))


class RevisionGateTests(unittest.TestCase):
    def test_gate_allows_exactly_one_revision_request(self):
        source = load_fixture(FIXTURE)
        claims = MockSummarizer().summarize(source)
        finding = verify_claims(
            source,
            (Claim("c-bad", "Målingen er 999.", "p1", source.paragraphs[0].text),),
        ).findings
        gate = OneRevisionGate()

        request = gate.request(source, claims, finding)

        self.assertEqual(request.attempt, 1)
        self.assertEqual(request.source_id, source.id)
        with self.assertRaises(RevisionLimitExceeded):
            gate.request(source, claims, finding)


if __name__ == "__main__":
    unittest.main()
