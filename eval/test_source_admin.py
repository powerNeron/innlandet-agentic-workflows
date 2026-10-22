"""Proposal administration tests; no network or active approval writes."""
from datetime import datetime, timezone
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from hamar_agent.source_admin import (blocked_activation, load_proposal,
    main, make_decision, save_exclusive, validate_current_source)


def digest(values):
    return hashlib.sha256("\n\n".join(" ".join(x.split()) for x in values).encode()).hexdigest()


def proposal():
    old = ["Hamar kommune tilbyr 12 timer gratis SFO."]
    new = ["Hamar kommune tilbyr 12 timer gratis SFO for 1.-3. trinn."]
    return {
        "report_version": 1, "source_id": "hamar-sfo",
        "url": "https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/",
        "checked_at": "2026-10-22T12:00:00+00:00", "previous_reviewed_on": "2026-10-21",
        "previous_approval_expires": "2026-10-28", "previous_text_sha256": "a" * 64,
        "previous_normalized_text_sha256": digest(old),
        "candidate_normalized_text_sha256": digest(new),
        "status": "changed_human_review_required", "human_approval_required": True,
        "old_excerpts": old, "proposed_excerpts": new,
        "approval_changed": False, "catalog_changed": False,
    }


class SourceAdminTests(unittest.TestCase):
    def write_proposal(self, folder, value=None):
        path = folder / "proposal.json"
        path.write_text(json.dumps(value or proposal(), ensure_ascii=False), encoding="utf-8")
        return path

    def test_review_loader_validates_exact_provenance_hashes_and_official_https(self):
        with tempfile.TemporaryDirectory() as tmp:
            value, sha = load_proposal(self.write_proposal(Path(tmp)))
        self.assertEqual(value["source_id"], "hamar-sfo")
        self.assertEqual(len(sha), 64)

    def test_review_binds_old_text_and_expiry_to_active_local_approval(self):
        value = proposal()
        old_text = value["old_excerpts"][0]
        text_hash = hashlib.sha256(old_text.encode()).hexdigest()
        value["previous_text_sha256"] = text_hash
        approval = {"source_id": value["source_id"], "url": value["url"], "title": "SFO",
            "category": "oppvekst", "reviewed_on": value["previous_reviewed_on"],
            "expires_on": value["previous_approval_expires"], "raw_sha256": "1" * 64,
            "text_sha256": text_hash, "robots_sha256": "2" * 64,
            "rationale": "Reviewed service text.", "no_personal_data": True}
        catalog = {"catalog_version": 1, "documents": [{"source": {"id": value["source_id"],
            "title": "SFO", "url": value["url"], "synthetic": False,
            "paragraphs": [{"id": "p1", "text": old_text}]}, "text_sha256": text_hash,
            "raw_sha256": "1" * 64, "category": "oppvekst",
            "approval_expires": value["previous_approval_expires"]}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); approvals_path = root / "approvals.json"; catalog_path = root / "catalog.json"
            approvals_path.write_text(json.dumps([approval]), encoding="utf-8")
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            validate_current_source(value, approvals_path, catalog_path)
            altered = json.loads(json.dumps(value)); altered["old_excerpts"] = ["Unrelated text."]
            altered["previous_normalized_text_sha256"] = digest(altered["old_excerpts"])
            with self.assertRaisesRegex(ValueError, "old excerpts"):
                validate_current_source(altered, approvals_path, catalog_path)

    def test_rejects_tampered_excerpt_or_nonmunicipal_url(self):
        for change in ({"proposed_excerpts": ["changed content"]},
                       {"url": "https://www.hamar.kommune.no.evil.example/path"},
                       {"url": "https://www.hamar.kommune.no/path?token=x"}):
            value = proposal(); value.update(change)
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    load_proposal(self.write_proposal(Path(tmp), value))

    def test_approval_requires_both_review_roles_and_all_three_review_checks(self):
        value = proposal()
        with self.assertRaises(ValueError):
            make_decision(value, "b" * 64, decision="approve", reviewer_role="source-reviewer",
                privacy_reviewer_role="privacy-reviewer", source_checked=True, privacy_checked=False,
                service_facts_checked=True)
        record = make_decision(value, "b" * 64, decision="approve", reviewer_role="source-reviewer",
            privacy_reviewer_role="privacy-reviewer", source_checked=True, privacy_checked=True,
            service_facts_checked=True, decided_at=datetime(2026, 10, 22, tzinfo=timezone.utc))
        self.assertEqual(record["decision_status"], "approved_pending_activation_review")
        self.assertEqual(record["activation"], "not_activated")
        self.assertIn("not independently authenticated", record["identity_assurance"])

    def test_expired_approval_cannot_be_renewed_by_proposal_decision(self):
        value = proposal(); value["status"] = "approval_expired_human_review_required"
        with self.assertRaisesRegex(ValueError, "cannot be renewed"):
            make_decision(value, "b" * 64, decision="approve", reviewer_role="source-reviewer",
                privacy_reviewer_role="privacy-reviewer", source_checked=True, privacy_checked=True,
                service_facts_checked=True)

    def test_reject_decision_is_recordable_without_claiming_activation(self):
        record = make_decision(proposal(), "c" * 64, decision="reject", reviewer_role="source-reviewer",
            privacy_reviewer_role="privacy-reviewer", source_checked=False, privacy_checked=False,
            service_facts_checked=False)
        self.assertEqual(record["decision_status"], "rejected")
        self.assertEqual(record["activation"], "not_activated")

    def test_activation_is_fail_closed_and_does_not_change_approval_catalog(self):
        decision = make_decision(proposal(), "c" * 64, decision="approve", reviewer_role="source-reviewer",
            privacy_reviewer_role="privacy-reviewer", source_checked=True, privacy_checked=True,
            service_facts_checked=True)
        blocked = blocked_activation(decision, attempted_at=datetime(2026, 10, 22, tzinfo=timezone.utc))
        self.assertEqual(blocked["activation"], "blocked")
        self.assertIn("Raw HTML", blocked["reason"])
        self.assertFalse(blocked["catalog_changed"])
        self.assertFalse(blocked["approval_changed"])
        with self.assertRaises(ValueError):
            blocked_activation({"record_version": 1, "decision": "reject"})

    def test_audit_record_uses_exclusive_create(self):
        record = make_decision(proposal(), "c" * 64, decision="reject", reviewer_role="source-reviewer",
            privacy_reviewer_role="privacy-reviewer", source_checked=False, privacy_checked=False,
            service_facts_checked=False)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decision.json"
            save_exclusive(record, target)
            old = target.read_bytes()
            with self.assertRaises(FileExistsError):
                save_exclusive(record, target)
            self.assertEqual(target.read_bytes(), old)

    def test_cli_activation_writes_blocked_audit_and_exits_nonzero(self):
        approved = make_decision(proposal(), "c" * 64, decision="approve", reviewer_role="source-reviewer",
            privacy_reviewer_role="privacy-reviewer", source_checked=True, privacy_checked=True,
            service_facts_checked=True)
        with tempfile.TemporaryDirectory() as tmp:
            decision_path = Path(tmp) / "decision.json"
            activation_path = Path(tmp) / "activation.json"
            decision_path.write_text(json.dumps(approved), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                exit_code = main(["activate", "--decision-record", str(decision_path), "--output", str(activation_path)])
            self.assertEqual(exit_code, 3)
            result = json.loads(activation_path.read_text(encoding="utf-8"))
            self.assertEqual(result["activation"], "blocked")
            self.assertFalse(result["approval_changed"])


if __name__ == "__main__":
    unittest.main()
