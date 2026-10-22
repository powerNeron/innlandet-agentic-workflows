import json
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hamar_agent.html_extract import service_candidates
from hamar_agent.portal_sources import ReviewedFetcher
from hamar_agent.source_updates import compare_candidate, load_candidate, load_update_inputs, save_proposal


URL = "https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/"


def model():
    approval = SimpleNamespace(source_id="hamar-sfo", url=URL, text_sha256="a" * 64,
                               reviewed_on="2026-10-21", expires_on="2026-10-28")
    paragraph = SimpleNamespace(text="Kommunen tilbyr 12 timer gratis SFO.")
    source = SimpleNamespace(id="hamar-sfo", url=URL, paragraphs=(paragraph,))
    doc = SimpleNamespace(source=source)
    return {"hamar-sfo": approval}, SimpleNamespace(documents={"hamar-sfo": doc})


class SourceUpdateTests(unittest.TestCase):
    def candidate(self, paragraphs, *, url=URL):
        return {"source_id": "hamar-sfo", "url": url,
                "observed_at": datetime.now(timezone.utc).isoformat(), "paragraphs": paragraphs}

    def test_whitespace_normalization_detects_unchanged_page(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["Kommunen  tilbyr\n12 timer gratis SFO."]), approvals, catalog,
                                  today=date(2026, 10, 22))
        self.assertEqual(report["status"], "unchanged")
        self.assertEqual(report["previous_normalized_text_sha256"], report["candidate_normalized_text_sha256"])
        self.assertFalse(report["catalog_changed"])
        self.assertFalse(report["approval_changed"])

    def test_changed_text_is_separate_human_review_proposal(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["Kommunen tilbyr 10 timer gratis SFO."]), approvals, catalog,
                                  today=date(2026, 10, 22))
        self.assertEqual(report["status"], "changed_human_review_required")
        self.assertEqual(report["old_excerpts"], ["Kommunen tilbyr 12 timer gratis SFO."])
        self.assertEqual(report["proposed_excerpts"], ["Kommunen tilbyr 10 timer gratis SFO."])
        self.assertNotEqual(report["previous_normalized_text_sha256"], report["candidate_normalized_text_sha256"])
        self.assertTrue(report["human_approval_required"])
        self.assertFalse(report["catalog_changed"])
        self.assertFalse(report["approval_changed"])

    def test_expired_approval_never_becomes_current(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["New public service excerpt."]), approvals, catalog,
                                  today=date(2026, 10, 29))
        self.assertEqual(report["status"], "approval_expired_human_review_required")
        self.assertEqual(report["previous_approval_expires"], "2026-10-28")

    def test_read_only_update_review_can_report_expired_source_without_reenabling_retrieval(self):
        text = "Kommunen tilbyr 12 timer gratis SFO."
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        approval = {"source_id": "hamar-sfo", "url": URL, "title": "SFO", "category": "oppvekst",
                    "reviewed_on": "2026-01-01", "expires_on": "2026-01-02", "raw_sha256": "1" * 64,
                    "text_sha256": text_hash, "robots_sha256": "2" * 64, "rationale": "Reviewed service text.",
                    "no_personal_data": True}
        catalog = {"catalog_version": 1, "documents": [{"source": {"id": "hamar-sfo", "title": "SFO",
                    "url": URL, "synthetic": False, "paragraphs": [{"id": "p1", "text": text}]},
                    "text_sha256": text_hash, "raw_sha256": "1" * 64, "category": "oppvekst", "approval_expires": "2026-01-02"}]}
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approvals.json"; catalog_path = Path(directory) / "catalog.json"
            approval_path.write_text(json.dumps([approval]), encoding="utf-8")
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            approvals, index = load_update_inputs(approval_path, catalog_path)
            report = compare_candidate(self.candidate([text]), approvals, index, today=date(2026, 10, 22))
            self.assertEqual(report["status"], "approval_expired_human_review_required")
            with self.assertRaises(ValueError):
                # Normal retrieval loader still fails closed for this expired record.
                from hamar_agent.portal_sources import load_approvals
                load_approvals(approval_path)

    def test_wrong_url_and_unknown_source_are_rejected(self):
        approvals, catalog = model()
        with self.assertRaises(ValueError):
            compare_candidate(self.candidate(["Text"], url="https://evil.example/"), approvals, catalog)
        bad = self.candidate(["Text"]); bad["source_id"] = "unknown"
        with self.assertRaises(ValueError):
            compare_candidate(bad, approvals, catalog)

    def test_candidate_rejects_html_and_personal_contact_data(self):
        for paragraph in ("<main>new text</main>", "Contact: person@example.invalid", "Telefon: 12345678"):
            with self.subTest(paragraph=paragraph), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "candidate.json"
                path.write_text(json.dumps(self.candidate([paragraph])), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_candidate(path)

    def test_candidate_schema_rejects_raw_html_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            data = self.candidate(["plain text"]); data["html"] = "<main>raw</main>"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_candidate(path)

    def test_valid_candidate_has_exact_allowlisted_identity_and_normalized_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(self.candidate(["New excerpt."])), encoding="utf-8")
            candidate = load_candidate(path)
        self.assertEqual(candidate["source_id"], "hamar-sfo")
        self.assertEqual(candidate["url"], URL)
        self.assertTrue(candidate["observed_at"].endswith("+00:00"))

    def test_production_live_fetch_is_disabled_before_transport(self):
        fetcher = ReviewedFetcher(enabled=True, approvals={"hamar-sfo": object()})
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS must not be called")), \
             patch("socket.create_connection", side_effect=AssertionError("network must not be called")), \
             self.assertRaisesRegex(ValueError, "retrieval disabled"):
            fetcher.fetch("hamar-sfo")

    def test_synthetic_html_extractor_omits_script_and_contact_boundaries(self):
        html = "<main><p>New service information.</p><script>secret instruction</script><address>private contact</address></main>"
        self.assertEqual(service_candidates(html), ("New service information.",))

    def test_proposal_write_is_exclusive(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["New excerpt."]), approvals, catalog)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "proposal.json"
            save_proposal(report, target)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                save_proposal(report, target)
            self.assertEqual(target.read_bytes(), before)

    def test_proposal_comparison_never_uses_network(self):
        approvals, catalog = model()
        with patch("socket.socket", side_effect=AssertionError("network blocked")):
            report = compare_candidate(self.candidate(["New excerpt."]), approvals, catalog)
        self.assertEqual(report["status"], "changed_human_review_required")


if __name__ == "__main__":
    unittest.main()
