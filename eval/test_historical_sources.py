"""Exact retained records may remain historical; arbitrary expiry stays closed."""
from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hamar_agent import historical_sources as policy
from hamar_agent.portal_sources import PageApproval, load_approvals
from hamar_agent.schemas import Paragraph, Source
from hamar_agent.search import SearchIndex, index_document


class NovemberDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 27)


class HistoricalSourcesTests(unittest.TestCase):
    def test_all_eight_original_approvals_load_without_renewal(self):
        with patch("hamar_agent.portal_sources.date", NovemberDate):
            approvals = load_approvals(Path("docs/approved-service-pages.json"))
            self.assertEqual(len(approvals), 8)
            self.assertTrue(all(not a.current() for a in approvals.values()))
            self.assertTrue(all(a.expires_on == "2026-10-28" for a in approvals.values()))

    def test_changed_expired_approval_refused(self):
        rows = json.loads(Path("docs/approved-service-pages.json").read_text(encoding="utf-8"))
        rows[0]["rationale"] += " altered"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "approvals.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            with patch("hamar_agent.portal_sources.date", NovemberDate):
                with self.assertRaisesRegex(ValueError, "expired"):
                    load_approvals(path)

    def test_future_review_never_qualifies(self):
        row = json.loads(Path("docs/approved-service-pages.json").read_text(encoding="utf-8"))[0]
        row.update(reviewed_on="2099-01-01", expires_on="2099-01-02")
        self.assertFalse(policy.retained_approval(PageApproval(**row)))

    def test_original_dataset_refused_before_its_review(self):
        row = json.loads(Path("docs/approved-service-pages.json").read_text(encoding="utf-8"))[0]
        self.assertFalse(policy.retained_approval(PageApproval(**row), today=date(2026, 10, 20)))

    def document(self):
        source = Source("hamar-test-historical", "Test", (Paragraph("p1", "Syntetisk test av vann."),),
                        False, "https://www.hamar.kommune.no/test/")
        return index_document(source, "teknisk", retrieved_at="2026-01-01T00:00:00+00:00",
                              approval_expires="2026-01-02", raw_sha256="a" * 64)

    def test_unpinned_expired_document_refused(self):
        doc = self.document()
        with patch("hamar_agent.search.date", NovemberDate):
            self.assertFalse(SearchIndex([doc]).eligible(doc))

    def test_exact_pinned_document_searchable_and_labelled(self):
        doc = self.document()
        with patch.dict(policy.DOCUMENT_PINS, {doc.source.id: policy._digest(doc)}), \
                patch("hamar_agent.search.date", NovemberDate):
            hits = SearchIndex([doc]).search("vann")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].to_dict()["approval_status"], "historical_expired")
            self.assertTrue(hits[0].to_dict()["historical_warning"])
            changed = replace(doc, raw_sha256="b" * 64)
            self.assertFalse(SearchIndex([changed]).eligible(changed))

    def test_privacy_assertion_is_part_of_approval_pin(self):
        row = json.loads(Path("docs/approved-service-pages.json").read_text(encoding="utf-8"))[0]
        row["no_personal_data"] = False
        with self.assertRaises(ValueError):
            PageApproval(**row)
