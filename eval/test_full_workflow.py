"""powerNeron's full-system integration tests; providers/HTTP are offline doubles."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from datetime import date
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent.__main__ import main
from hamar_agent.application import WorkflowService
from hamar_agent.retrieval import HTTP_APPROVALS, HttpApproval
from hamar_agent.schemas import Claim, EvidenceStatus, Result
from hamar_agent.sources import load_source
from hamar_agent.storage import save_result
from hamar_agent.summarize import MockScenario, MockSummarizer
from hamar_agent.workflow import WorkflowResult, run_workflow
from hamar_agent.verify import verify_claims

SOURCE_ID = "synthetic-verification-demo"


class FullWorkflowTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("network/paid APIs forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.source = load_source(SOURCE_ID)

    def run_scenario(self, scenario=MockScenario.VALID, **kwargs):
        return run_workflow(SOURCE_ID, MockSummarizer(scenario), provider="mock", **kwargs)

    def test_default_pipeline_verifies_and_retains_legacy_result_fields(self):
        result = self.run_scenario()
        self.assertIsInstance(result, Result)
        self.assertIsInstance(result, WorkflowResult)
        data = json.loads(result.to_json())
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["workflow_version"], "1.0")
        self.assertFalse(data["verification"]["findings"])
        self.assertEqual(data["claims"], data["verification"]["claims"])
        self.assertTrue(all(c["evidence_status"] == "exact_match" for c in data["claims"]))
        self.assertTrue(any("not semantic fact-checking" in w for w in data["warnings"]))

    def test_invalid_references_recompute_untrusted_exact_match_status(self):
        provider = Mock()
        provider.summarize.return_value = (Claim("c1", "Synthetic", "p999", "Invented", EvidenceStatus.EXACT_MATCH),)
        result = run_workflow(SOURCE_ID, provider, provider="test-double")
        self.assertEqual(result.claims[0].evidence_status, EvidenceStatus.MISSING)
        self.assertEqual(result.verification.findings[0].code.value, "invalid_paragraph_id")
        self.assertIn("Review required", " ".join(result.warnings))

    def test_numbers_fabrication_and_conflicts_survive_json(self):
        cases = [(MockScenario.CHANGED_NUMBER, "unsupported_number"),
                 (MockScenario.FABRICATED_QUOTE, "fabricated_evidence"),
                 (MockScenario.CONFLICTING_CLAIMS, "conflicting_claims")]
        for scenario, code in cases:
            with self.subTest(scenario=scenario):
                data = json.loads(self.run_scenario(scenario).to_json())
                self.assertIn(code, {f["code"] for f in data["verification"]["findings"]})
                self.assertEqual(data["correction"]["status"], "not_configured")
                self.assertTrue(data["correction"]["initial_findings"])

    def test_exact_excerpt_and_unsupported_number_are_distinct(self):
        result = self.run_scenario(MockScenario.CHANGED_NUMBER)
        self.assertEqual(result.claims[0].evidence_status, EvidenceStatus.EXACT_MATCH)
        self.assertTrue(result.verification.has_findings)

    def test_one_correction_is_reverified_and_history_retained(self):
        corrector = Mock(return_value=MockSummarizer().summarize(self.source))
        result = self.run_scenario(MockScenario.CHANGED_NUMBER, corrector=corrector)
        corrector.assert_called_once()
        source, request = corrector.call_args.args
        self.assertEqual(source, self.source)
        self.assertEqual(request.attempt, 1)
        self.assertEqual(request.source_id, SOURCE_ID)
        self.assertFalse(result.verification.has_findings)
        self.assertEqual(result.correction.attempts, 1)
        self.assertTrue(result.correction.initial_findings)
        self.assertTrue(result.correction.initial_claims)

    def test_unresolved_correction_never_loops(self):
        wrong = MockSummarizer(MockScenario.INVALID_PARAGRAPH).summarize(self.source)
        corrector = Mock(return_value=wrong)
        result = self.run_scenario(MockScenario.CHANGED_NUMBER, corrector=corrector)
        corrector.assert_called_once()
        self.assertEqual(result.correction.status, "completed")
        self.assertTrue(result.verification.has_findings)
        self.assertEqual(result.claims[0].evidence_status, EvidenceStatus.MISSING)

    def test_corrector_failure_or_invalid_return_retains_original(self):
        for response in ((), ["wrong"], RuntimeError("secret provider detail")):
            with self.subTest(response=response):
                corrector = Mock()
                if isinstance(response, Exception):
                    corrector.side_effect = response
                else:
                    corrector.return_value = response
                result = self.run_scenario(MockScenario.CHANGED_NUMBER, corrector=corrector)
                self.assertEqual(result.correction.status, "failed")
                self.assertEqual(result.correction.attempts, 1)
                self.assertTrue(result.verification.has_findings)
                self.assertNotIn("secret provider detail", result.to_json())
                corrector.assert_called_once()

    def test_initial_verifier_failure_produces_no_workflow_result(self):
        with patch("hamar_agent.workflow.verify_claims", side_effect=RuntimeError("synthetic verifier failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic verifier failure"):
                self.run_scenario()

    def test_reverification_failure_retains_initial_findings_and_fails_closed(self):
        bad_claims = MockSummarizer(MockScenario.CHANGED_NUMBER).summarize(self.source)
        initial = verify_claims(self.source, bad_claims)
        corrector = Mock(return_value=MockSummarizer().summarize(self.source))
        with patch("hamar_agent.workflow.verify_claims", side_effect=[initial, RuntimeError("synthetic recheck failure")]):
            result = self.run_scenario(MockScenario.CHANGED_NUMBER, corrector=corrector)
        self.assertEqual(result.correction.status, "failed")
        self.assertEqual(result.correction.attempts, 1)
        self.assertEqual(result.verification, initial)

    def test_clean_response_never_calls_corrector(self):
        corrector = Mock(side_effect=AssertionError("not needed"))
        self.run_scenario(corrector=corrector)
        corrector.assert_not_called()

    def test_malformed_summary_rejected_without_fabricating_claims(self):
        for scenario in (MockScenario.MALFORMED_OUTPUT, MockScenario.MISSING_CITATION):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                self.run_scenario(scenario)

    def test_unknown_source_fails_before_provider(self):
        provider = Mock()
        with self.assertRaises(ValueError):
            run_workflow("unknown", provider, provider="test")
        provider.summarize.assert_not_called()

    def test_existing_storage_saves_full_verification_report_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            result = self.run_scenario(MockScenario.CHANGED_NUMBER)
            save_result(result, path)
            raw = path.read_bytes()
            self.assertEqual(json.loads(raw)["verification"]["findings"][0]["code"], "unsupported_number")
            with self.assertRaises(FileExistsError):
                save_result(result, path)
            self.assertEqual(path.read_bytes(), raw)

    def test_cli_source_option_and_saving_use_verifier(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with redirect_stdout(output):
                self.assertEqual(main(["--source", SOURCE_ID, "--output", str(path)]), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["claims"][0]["evidence_status"], "exact_match")

    def test_cli_bad_source_and_malformed_provider_fail_cleanly(self):
        for args in (["--source", "unapproved"], ["--source", SOURCE_ID, "--fixture", "unknown"]):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(output.getvalue(), "")

    def test_cli_invalid_claim_findings_are_serialized(self):
        claims = MockSummarizer(MockScenario.CHANGED_NUMBER).summarize(self.source)
        with patch.object(MockSummarizer, "summarize", return_value=claims), redirect_stdout(io.StringIO()) as output:
            main(["--source", SOURCE_ID])
        self.assertEqual(json.loads(output.getvalue())["verification"]["findings"][0]["code"], "unsupported_number")

    def test_http_disabled_by_default_even_with_injected_approval(self):
        service = WorkflowService()
        with patch("hamar_agent.application.fetch_document") as fetch:
            with self.assertRaises(ValueError):
                service.run("https://example.invalid/a.txt")
            fetch.assert_not_called()
        self.assertEqual(dict(HTTP_APPROVALS), {})

    def test_explicit_http_approval_connects_real_transport_with_mocked_response(self):
        approval = HttpApproval("http-test", "https://example.invalid/a.txt", "Synthetic HTTP test", date.today(), date.today())
        provider = Mock()
        provider.summarize.side_effect = lambda source: (Claim("c1", source.paragraphs[0].text, "p1", source.paragraphs[0].text),)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.geturl.return_value = approval.url
        response.headers = Message()
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        response.read.side_effect = io.BytesIO(b"Fictional service text.").read
        with patch("hamar_agent.retrieval.build_opener") as opener:
            opener.return_value.open.return_value = response
            service = WorkflowService(summarizer=provider, provider="test-double", enable_http=True,
                                      http_registry={"http-test": approval})
            result = service.run("http-test")
            self.assertFalse(result.source.synthetic)
            self.assertEqual(result.source.url, approval.url)
            self.assertFalse(result.verification.has_findings)
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 10)
        self.assertEqual(dict(HTTP_APPROVALS), {})

    def test_enabled_http_still_rejects_unregistered_id_before_network(self):
        with patch("hamar_agent.retrieval.build_opener") as opener:
            with self.assertRaises(ValueError):
                WorkflowService(enable_http=True).run("unapproved")
            opener.assert_not_called()

    def test_cli_accepts_injected_service_without_assuming_provider_api(self):
        service = WorkflowService(summarizer=MockSummarizer(MockScenario.CHANGED_NUMBER), provider="injected-test-double")
        with redirect_stdout(io.StringIO()) as output:
            main(["--source", SOURCE_ID], service=service)
        data = json.loads(output.getvalue())
        self.assertEqual(data["provider"], "injected-test-double")
        self.assertEqual(data["verification"]["findings"][0]["code"], "unsupported_number")
