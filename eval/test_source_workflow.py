"""Tests for powerNeron's approval, loading and orchestration components."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent.__main__ import main
from hamar_agent.schemas import Claim, EvidenceStatus
from hamar_agent.sources import APPROVED_SOURCES, MAX_FIXTURE_BYTES, SourceApproval, load_fixture, load_source
from hamar_agent.workflow import run_workflow

SOURCE_ID = "synthetic-water-demo"
FIXTURE = APPROVED_SOURCES[SOURCE_ID].path


class SourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.source = load_source(SOURCE_ID)

    def temporary_approval(self, directory, raw):
        path = Path(directory) / "fixture.json"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        return {SOURCE_ID: SourceApproval(SOURCE_ID, path, digest, "Synthetic test only")}

    def test_default_registry_allows_only_reviewed_fixture(self):
        self.assertEqual(set(APPROVED_SOURCES), {SOURCE_ID, "synthetic-verification-demo"})
        self.assertEqual(load_fixture(FIXTURE), self.source)
        with self.assertRaises(TypeError):
            APPROVED_SOURCES["extra"] = APPROVED_SOURCES[SOURCE_ID]

    def test_unknown_source_rejected_before_open(self):
        with patch.object(Path, "open", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "not approved"):
                load_source("unknown")

    def test_unknown_path_rejected_before_open(self):
        with patch.object(Path, "open", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "not approved"):
                load_fixture(Path("unknown.json"))

    def test_changed_content_requires_reapproval(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.temporary_approval(directory, b"{}")
            registry[SOURCE_ID].path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "content changed"):
                load_source(SOURCE_ID, registry=registry)

    def test_line_endings_are_portable(self):
        raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
        with tempfile.TemporaryDirectory() as directory:
            registry = self.temporary_approval(directory, raw)
            registry[SOURCE_ID].path.write_bytes(raw.replace(b"\n", b"\r\n"))
            self.assertEqual(load_source(SOURCE_ID, registry=registry), self.source)

    def test_malformed_reviewed_fixtures_rejected(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8"))
        values = [[], original | {"synthetic": False}, original | {"synthetic": "true"},
                  original | {"url": "https://example.invalid"}, original | {"id": "other"},
                  original | {"paragraphs": {}}, original | {"paragraphs": []},
                  original | {"paragraphs": [{"id": "p1"}]}]
        raws = [b"{", b"\xff"] + [json.dumps(value).encode() for value in values]
        for raw in raws:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                registry = self.temporary_approval(directory, raw)
                with self.assertRaises((ValueError, TypeError, KeyError)):
                    load_source(SOURCE_ID, registry=registry)

    def test_oversized_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.temporary_approval(directory, b" " * (MAX_FIXTURE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                load_source(SOURCE_ID, registry=registry)

    def test_missing_approved_file_propagates_error(self):
        registry = {SOURCE_ID: replace(APPROVED_SOURCES[SOURCE_ID], path=Path("missing-fixture.json"))}
        with self.assertRaises(OSError):
            load_source(SOURCE_ID, registry=registry)

    def test_registry_id_mismatch_rejected_before_open(self):
        registry = {SOURCE_ID: replace(APPROVED_SOURCES[SOURCE_ID], source_id="other")}
        with patch.object(Path, "open", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "ID mismatch"):
                load_source(SOURCE_ID, registry=registry)

    def test_injected_summarizer_preserves_response_and_provider(self):
        claims = (Claim("c1", "Synthetic response", "p999", "Unknown excerpt"),)
        summarizer = Mock()
        summarizer.summarize.return_value = claims
        result = run_workflow(SOURCE_ID, summarizer, provider="test-double")
        summarizer.summarize.assert_called_once_with(self.source)
        self.assertEqual(result.claims, claims)
        self.assertEqual(result.provider, "test-double")
        self.assertEqual(result.claims[0].evidence_status, EvidenceStatus.NOT_CHECKED)

    def test_approval_failure_never_calls_summarizer(self):
        summarizer = Mock()
        with self.assertRaises(ValueError):
            run_workflow("unknown", summarizer, provider="test-double")
        summarizer.summarize.assert_not_called()

    def test_injected_loader_validated_before_summarizer(self):
        for source in (None, replace(self.source, id="other"), replace(self.source, synthetic=False)):
            with self.subTest(source=source):
                summarizer = Mock()
                with self.assertRaises(ValueError):
                    run_workflow(SOURCE_ID, summarizer, provider="test", loader=lambda _: source)
                summarizer.summarize.assert_not_called()

    def test_provider_failure_propagates(self):
        summarizer = Mock()
        summarizer.summarize.side_effect = RuntimeError("synthetic provider failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic provider failure"):
            run_workflow(SOURCE_ID, summarizer, provider="test")

    def test_invalid_response_rejected_by_existing_schema(self):
        for claims in ((), [Claim("c1", "text", "p1", "quote")], ("invalid",)):
            with self.subTest(claims=claims):
                summarizer = Mock()
                summarizer.summarize.return_value = claims
                with self.assertRaises(ValueError):
                    run_workflow(SOURCE_ID, summarizer, provider="test")

    def test_cli_provider_failure_outputs_no_partial_json(self):
        output, error = io.StringIO(), io.StringIO()
        with patch("hamar_agent.__main__.MockSummarizer") as provider:
            provider.return_value.summarize.side_effect = RuntimeError("synthetic failure")
            with redirect_stdout(output), redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                main(["--fixture", str(FIXTURE)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.getvalue(), "")

    def test_cli_remains_offline_and_json_compatible(self):
        output = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), redirect_stdout(output):
            self.assertEqual(main(["--fixture", str(FIXTURE)]), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["source"]["id"], SOURCE_ID)
        self.assertEqual(data["provider"], "mock")
        self.assertEqual(data["schema_version"], "1.0")