"""Synthetic temporary renewal packages only; no municipal retrieval or models."""
from copy import deepcopy
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent import source_renewal as renewal
from hamar_agent.source_admin import main
from hamar_agent.portal_sources import load_approvals, load_catalog
from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
from hamar_agent.real_sources import create_municipal_service, RealSourceError
from hamar_agent.portal import PortalService


NOW = datetime(2026, 10, 27, 14, tzinfo=timezone.utc)


@contextmanager
def runtime_date(day):
    """Test-only scoped clock; never changes system time or production config."""
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return cls.fromisoformat(day)
    with patch("hamar_agent.portal_sources.date", FrozenDate), patch("hamar_agent.search.date", FrozenDate):
        yield


class SourceRenewalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.approvals = self.root / "approvals.json"
        self.selection = self.root / "selection.json"
        self.catalog = self.root / "catalog.json"
        self.owner = self.root / "owner.json"
        self.reviews = self.root / "reviews.json"
        self.transaction = self.root / "transaction"
        approvals, selection, documents = [], [], []
        for number in (1, 2):
            source_id = f"hamar-test-{number}"
            text = f"Fictional non-personal SFO test service number {number}."
            paragraph_hash = hashlib.sha256(text.encode()).hexdigest()
            approval = {"source_id": source_id, "url": f"https://www.hamar.kommune.no/test-{number}/",
                        "title": "Fictional test service", "category": "oppvekst",
                        "reviewed_on": "2026-10-21", "expires_on": "2026-10-28",
                        "raw_sha256": "a" * 64, "text_sha256": paragraph_hash,
                        "robots_sha256": "b" * 64, "rationale": "Synthetic test approval only.",
                        "no_personal_data": True, "content_type": "text/html",
                        "content_tag": "main", "review_scope": "service_excerpts",
                        "paragraph_sha256": [paragraph_hash]}
            approvals.append(approval)
            selection.append({k: approval[k] for k in ("source_id", "url", "title", "category",
                                                       "reviewed_on", "expires_on", "paragraph_sha256")})
            documents.append({"source": {"id": source_id, "url": approval["url"],
                              "title": approval["title"], "synthetic": False,
                              "paragraphs": [{"id": "p1", "text": text}]},
                              "category": approval["category"], "text_sha256": paragraph_hash,
                              "raw_sha256": approval["raw_sha256"], "approval_expires": "2026-10-28",
                              "retrieved_at": "2026-10-21T10:00:00+00:00",
                              "indexed_at": "2026-10-21T10:01:00+00:00"})
        self.put(self.approvals, approvals)
        self.put(self.selection, selection)
        self.put(self.catalog, {"catalog_version": 1, "documents": documents})
        self.put(self.owner, {
            "record_type": "project_owner_conditional_renewal_authorization_and_technical_review",
            "record_version": 1, "authorization": {"actor_role": "project_owner",
            "subject_to_mandatory_source_provenance_and_privacy_checks": True,
            "source_ids": [a["source_id"] for a in approvals],
            "scope": ["municipal_search", "real_source_ollama_workflow"],
            "decision_date": "2026-10-27", "requested_expiry": "2026-11-27"}})
        self.make_reviews()
        self.originals = self.bytes()

    def put(self, path, value):
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def get(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def bytes(self):
        return [p.read_bytes() for p in (self.approvals, self.selection, self.catalog)]

    def make_reviews(self):
        draft = renewal.prepare_review(self.owner, self.approvals, self.selection, self.catalog, now=NOW)
        for row in draft["sources"]:
            binding = {k: row[k] for k in ("source_id", "url", "paragraph_ids", "paragraph_sha256",
                                          "raw_sha256", "text_sha256", "robots_sha256")}
            evidence = {**binding, "record_type": "source_renewal_provenance", "record_version": 1,
                        "observed_at": "2026-10-27T13:50:00+00:00",
                        "input_boundary": "authorized_non_personal_material",
                        "checks": {key: True for key in renewal.PROVENANCE_CHECKS}}
            path = self.root / (row["source_id"] + ".json")
            self.put(path, evidence)
            row.update({"decision": "approve", "reviewer": "test-owner", "reviewer_role": "project-owner",
                        "reviewed_at": "2026-10-27T13:55:00+00:00",
                        "checks": {key: True for key in renewal.CHECKS},
                        "provenance_file": path.name, "provenance_sha256": renewal.digest(path.read_bytes())})
        self.put(self.reviews, draft)

    def activate(self, **overrides):
        options = {"confirm": "renew 2026-11-27", "application_stopped": True, "now": NOW}
        options.update(overrides)
        return renewal.activate_renewal(self.owner, self.reviews, self.approvals,
                                       self.selection, self.catalog, self.transaction, **options)

    def check(self):
        return renewal.check_renewal(self.owner, self.reviews, self.approvals,
                                     self.selection, self.catalog, now=NOW)[0]

    def test_authorized_renewal_updates_all_three_and_preserves_original_fields(self):
        result = self.activate()
        self.assertEqual(result["activation"], "activated")
        self.assertEqual(len(result["reviews"]), 2)
        for index, key in enumerate(renewal.LABELS):
            self.assertEqual((self.transaction / (key + ".before.json")).read_bytes(), self.originals[index])
        self.assertTrue((self.transaction / "COMMITTED.json").is_file())
        old_approvals, old_selection, old_catalog = map(json.loads, self.originals)
        for old, new in zip(old_approvals, self.get(self.approvals)):
            old["expires_on"] = "2026-11-27"
            self.assertEqual(old, new)
        for old, new in zip(old_selection, self.get(self.selection)):
            old["expires_on"] = "2026-11-27"
            self.assertEqual(old, new)
        for doc in old_catalog["documents"]:
            doc["approval_expires"] = "2026-11-27"
        self.assertEqual(old_catalog, self.get(self.catalog))
        self.assertEqual(len(load_catalog(self.catalog, load_approvals(self.approvals)).documents), 2)

    def test_preparation_never_fabricates_reviews(self):
        draft = renewal.prepare_review(self.owner, self.approvals, self.selection, self.catalog, now=NOW)
        self.assertTrue(all(row["decision"] == "pending" and row["reviewed_at"] is None
                            and not any(row["checks"].values()) for row in draft["sources"]))
        self.assertEqual(self.bytes(), self.originals)

    def test_missing_source_review_is_reported_without_partial_activation(self):
        draft = self.get(self.reviews); draft["sources"].pop(); self.put(self.reviews, draft)
        result = self.activate()
        self.assertEqual(result["activation"], "blocked")
        self.assertEqual(result["errors"][0]["source_id"], "hamar-test-2")
        self.assertEqual(self.bytes(), self.originals)
        self.assertFalse(self.transaction.exists())

    def test_missing_every_review_lists_each_source(self):
        draft = self.get(self.reviews); draft["sources"] = []; self.put(self.reviews, draft)
        self.assertEqual(len(self.check()["errors"]), 2)

    def test_rejected_privacy_and_incomplete_review_fail_closed(self):
        for key in renewal.CHECKS:
            with self.subTest(check=key):
                self.make_reviews(); draft = self.get(self.reviews)
                draft["sources"][0]["checks"][key] = False; self.put(self.reviews, draft)
                result = self.activate()
                self.assertEqual(result["activation"], "blocked")
                self.assertIn(key, result["errors"][0]["reason"])
                self.assertEqual(self.bytes(), self.originals)

    def test_rejected_decision_is_never_activated(self):
        draft = self.get(self.reviews); draft["sources"][0]["decision"] = "reject"
        self.put(self.reviews, draft)
        self.assertEqual(self.activate()["activation"], "blocked")

    def test_owner_role_scope_and_source_set_are_required(self):
        owner = self.get(self.owner)
        for change in ({"actor_role": "source-reviewer"}, {"scope": []},
                       {"source_ids": ["hamar-test-1"]},
                       {"subject_to_mandatory_source_provenance_and_privacy_checks": False}):
            with self.subTest(change=change):
                changed = deepcopy(owner); changed["authorization"].update(change); self.put(self.owner, changed)
                with self.assertRaises(ValueError): self.activate()
                self.assertEqual(self.bytes(), self.originals)

    def test_missing_authorization_refuses_without_writes(self):
        self.owner.unlink()
        with self.assertRaises(OSError): self.activate()
        self.assertEqual(self.bytes(), self.originals)

    def test_changed_authorization_or_input_invalidates_review_binding(self):
        owner = self.get(self.owner); owner["new_context"] = "changed"; self.put(self.owner, owner)
        with self.assertRaisesRegex(ValueError, "bind"): self.activate()
        self.assertEqual(self.bytes(), self.originals)

    def test_target_cannot_exceed_or_differ_from_owner_authorization(self):
        draft = self.get(self.reviews); draft["target_expiry"] = "2026-12-01"; self.put(self.reviews, draft)
        with self.assertRaisesRegex(ValueError, "bind"): self.activate()

    def test_forged_paragraph_or_source_hash_is_refused(self):
        for key, value in (("url", "https://www.hamar.kommune.no/other/"),
                           ("paragraph_ids", ["invented"]), ("raw_sha256", "c" * 64),
                           ("text_sha256", "c" * 64), ("robots_sha256", "c" * 64)):
            with self.subTest(key=key):
                self.make_reviews(); draft = self.get(self.reviews); draft["sources"][0][key] = value
                self.put(self.reviews, draft); self.assertEqual(self.activate()["activation"], "blocked")

    def test_missing_or_changed_provenance_is_refused(self):
        evidence = self.root / self.get(self.reviews)["sources"][0]["provenance_file"]
        evidence.write_text("{}", encoding="utf-8")
        self.assertEqual(self.activate()["activation"], "blocked")
        evidence.unlink()
        self.assertEqual(self.activate()["activation"], "blocked")

    def test_hash_bound_but_invalid_provenance_is_refused(self):
        for change in ({"raw_sha256": "d" * 64}, {"input_boundary": "raw_html"},
                       {"observed_at": "2026-10-21T10:00:00+00:00"},
                       {"checks": {key: False for key in renewal.PROVENANCE_CHECKS}}):
            with self.subTest(change=change):
                self.make_reviews(); draft = self.get(self.reviews); row = draft["sources"][0]
                path = self.root / row["provenance_file"]; value = self.get(path); value.update(change)
                self.put(path, value); row["provenance_sha256"] = renewal.digest(path.read_bytes())
                self.put(self.reviews, draft); self.assertEqual(self.activate()["activation"], "blocked")

    def test_old_future_or_naive_reviews_are_refused(self):
        for when in ("2026-10-26T13:55:00+00:00", "2026-10-27T15:00:00+00:00", "2026-10-27T13:55:00"):
            self.make_reviews(); draft = self.get(self.reviews); draft["sources"][0]["reviewed_at"] = when
            self.put(self.reviews, draft); self.assertEqual(self.activate()["activation"], "blocked")

    def test_provenance_path_traversal_and_absolute_paths_are_refused(self):
        for name in ("../private.json", str(self.owner), "https://example.invalid/file.json"):
            self.make_reviews(); draft = self.get(self.reviews); draft["sources"][0]["provenance_file"] = name
            self.put(self.reviews, draft); self.assertEqual(self.activate()["activation"], "blocked")

    def test_stale_catalog_or_selection_is_refused_before_mutation(self):
        selected = self.get(self.selection); selected[0]["paragraph_sha256"] = ["f" * 64]
        self.put(self.selection, selected); before = self.bytes()
        with self.assertRaises(ValueError): self.activate()
        self.assertEqual(self.bytes(), before)

    def test_duplicate_review_is_refused(self):
        draft = self.get(self.reviews); draft["sources"].append(draft["sources"][0]); self.put(self.reviews, draft)
        with self.assertRaises(ValueError): self.activate()

    def test_expired_inputs_can_only_be_renewed_after_complete_new_review(self):
        for path in (self.approvals, self.selection):
            values = self.get(path)
            for row in values: row["expires_on"] = "2026-10-26"
            self.put(path, values)
        values = self.get(self.catalog)
        for row in values["documents"]: row["approval_expires"] = "2026-10-26"
        self.put(self.catalog, values)
        with self.assertRaises(ValueError): load_approvals(self.approvals)
        self.make_reviews()
        self.assertEqual(self.activate()["activation"], "activated")
        self.assertEqual(len(load_approvals(self.approvals)), 2)

    def test_replay_after_success_is_refused(self):
        self.activate(); after = self.bytes()
        self.transaction = self.root / "replay-transaction"
        with self.assertRaisesRegex(ValueError, "replay"): self.activate()
        self.assertEqual(self.bytes(), after)

    def test_explicit_stop_and_confirmation_are_required(self):
        for options in ({"application_stopped": False}, {"confirm": "yes"}):
            with self.assertRaises(ValueError): self.activate(**options)
            self.assertEqual(self.bytes(), self.originals)

    def test_existing_transaction_or_lock_is_not_overwritten(self):
        self.transaction.mkdir()
        with self.assertRaises(ValueError): self.activate()
        self.transaction.rmdir()
        lock = self.approvals.with_name(self.approvals.name + ".renewal.lock")
        lock.write_text("existing lock", encoding="utf-8")
        with self.assertRaises(OSError): self.activate()
        self.assertEqual(lock.read_text(), "existing lock")

    def test_each_destination_failure_restores_original_bytes(self):
        actual_replace = renewal._replace
        for number, target in enumerate((self.catalog, self.selection, self.approvals)):
            with self.subTest(target=target.name):
                self.transaction = self.root / f"failed-{number}"
                failed = []
                def fail_once(path, data):
                    if path == target and not failed:
                        failed.append(True); raise OSError("synthetic write failure")
                    actual_replace(path, data)
                with patch.object(renewal, "_replace", side_effect=fail_once):
                    with self.assertRaises(OSError): self.activate()
                self.assertEqual(self.bytes(), self.originals)
                self.assertTrue((self.transaction / "ROLLED_BACK.json").exists())
                self.assertFalse((self.transaction / "COMMITTED.json").exists())

    def test_commit_audit_failure_rolls_back_instead_of_claiming_success(self):
        actual_exclusive = renewal._exclusive
        def fail_commit(path, data):
            if Path(path).name == "COMMITTED.json": raise OSError("synthetic audit failure")
            actual_exclusive(path, data)
        with patch.object(renewal, "_exclusive", side_effect=fail_commit):
            with self.assertRaises(OSError): self.activate()
        self.assertEqual(self.bytes(), self.originals)
        self.assertTrue((self.transaction / "ROLLED_BACK.json").exists())

    def test_rollback_failure_keeps_lock_and_supports_verified_recovery(self):
        actual_replace = renewal._replace; writes = []
        def fail_partial(path, data):
            if path == self.selection or (path == self.catalog and writes):
                raise OSError("synthetic partial failure")
            actual_replace(path, data); writes.append(path)
        with patch.object(renewal, "_replace", side_effect=fail_partial):
            with self.assertRaises(OSError): self.activate()
        lock = self.approvals.with_name(self.approvals.name + ".renewal.lock")
        self.assertTrue(lock.exists())
        self.assertTrue((self.transaction / "RECOVERY_REQUIRED.json").exists())
        result = renewal.recover_renewal(self.transaction, self.approvals, self.selection,
                                         self.catalog, application_stopped=True)
        self.assertEqual(result["activation"], "recovered_originals")
        self.assertEqual(self.bytes(), self.originals)
        self.assertFalse(lock.exists())

    def test_recovery_refuses_completed_transactions(self):
        self.activate()
        with self.assertRaises(ValueError):
            renewal.recover_renewal(self.transaction, self.approvals, self.selection,
                                    self.catalog, application_stopped=True)

    def test_concurrent_input_change_is_not_clobbered_or_reported_rolled_back(self):
        actual_replace = renewal._replace
        changed = b'[]\n'
        def alter_during_commit(path, data):
            actual_replace(path, data)
            if path == self.catalog and data != self.originals[2]:
                self.selection.write_bytes(changed)
        with patch.object(renewal, "_replace", side_effect=alter_during_commit):
            with self.assertRaises(ValueError): self.activate()
        self.assertEqual(self.selection.read_bytes(), changed)
        self.assertEqual(self.catalog.read_bytes(), self.originals[2])
        self.assertTrue((self.transaction / "RECOVERY_REQUIRED.json").exists())

    def test_snapshot_failure_leaves_all_inputs_untouched(self):
        actual_exclusive = renewal._exclusive
        def fail_snapshot(path, data):
            if Path(path).name == "catalog.before.json": raise OSError("synthetic disk failure")
            actual_exclusive(path, data)
        with patch.object(renewal, "_exclusive", side_effect=fail_snapshot):
            with self.assertRaises(OSError): self.activate()
        self.assertEqual(self.bytes(), self.originals)
        self.assertFalse((self.transaction / "COMMITTED.json").exists())

    def test_expired_or_future_owner_authorization_is_rejected(self):
        for when in (datetime(2026, 10, 26, tzinfo=timezone.utc), datetime(2026, 11, 28, tzinfo=timezone.utc)):
            with self.assertRaises(ValueError): self.activate(now=when)
        self.assertEqual(self.bytes(), self.originals)

    def test_review_flags_must_be_booleans_not_truthy_strings(self):
        for value in (1, "true"):
            draft = self.get(self.reviews)
            draft["sources"][0]["checks"][renewal.CHECKS[0]] = value
            self.put(self.reviews, draft)
            self.assertEqual(self.activate()["activation"], "blocked")

    def test_cli_check_draft_reports_blocked_and_activation_can_succeed(self):
        common = ["--owner-authorization", str(self.owner), "--approvals", str(self.approvals),
                  "--selection", str(self.selection), "--catalog", str(self.catalog)]
        with patch.object(renewal, "_now", side_effect=lambda value=None: value or NOW):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["activate", *common, "--reviews", str(self.reviews),
                                       "--transaction-dir", str(self.transaction), "--confirm", "renew 2026-11-27",
                                       "--application-stopped"]), 0)
        self.assertEqual(len(load_approvals(self.approvals)), 2)

    def test_cli_prepare_and_check_have_no_activation_side_effects(self):
        draft = self.root / "draft.json"
        common = ["--owner-authorization", str(self.owner), "--approvals", str(self.approvals),
                  "--selection", str(self.selection), "--catalog", str(self.catalog)]
        with patch.object(renewal, "_now", side_effect=lambda value=None: value or NOW):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["prepare-renewal", *common, "--output", str(draft)]), 0)
                self.assertEqual(main(["check-renewal", *common, "--reviews", str(draft)]), 3)
        self.assertEqual(self.bytes(), self.originals)

    def test_malformed_cli_review_fails_without_exposing_contents(self):
        self.reviews.write_text('{"secret": "sensitive",', encoding="utf-8")
        error = io.StringIO()
        with redirect_stderr(error):
            code = main(["check-renewal", "--owner-authorization", str(self.owner),
                         "--reviews", str(self.reviews), "--approvals", str(self.approvals),
                         "--selection", str(self.selection), "--catalog", str(self.catalog)])
        self.assertEqual(code, 2)
        self.assertNotIn("sensitive", error.getvalue())
        self.assertEqual(self.bytes(), self.originals)

    def test_technical_completion_fills_metadata_without_creating_human_reviews(self):
        draft = renewal.prepare_review(self.owner, self.approvals, self.selection, self.catalog, now=NOW)
        self.put(self.reviews, draft); before = self.reviews.read_bytes()
        folder = self.root / "technical"
        result = renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                                   self.selection, self.catalog, folder, now=NOW)
        self.assertEqual(result["human_reviews_created"], 0)
        self.assertEqual(result["technical_sources_verified"], 2)
        self.assertEqual((folder / "review.before.json").read_bytes(), before)
        for row in self.get(self.reviews)["sources"]:
            self.assertEqual(row["decision"], "pending")
            self.assertIsNone(row["reviewed_at"])
            self.assertIsNone(row["reviewer"])
            self.assertFalse(any(row["checks"].values()))
            self.assertTrue(all(row["technical_verification"]["checks"].values()))
            evidence_path = self.root / row["provenance_file"]
            self.assertEqual(renewal.digest(evidence_path.read_bytes()), row["provenance_sha256"])
            self.assertIsNone(self.get(evidence_path)["observed_at"])
            self.assertFalse(any(self.get(evidence_path)["checks"].values()))
        self.assertEqual(len(self.check()["errors"]), 2)
        self.assertEqual(self.bytes(), self.originals)
        self.assertEqual(len(self.get(folder / "owner-review-items.json")["sources"]), 2)

    def test_technical_completion_preserves_preexisting_real_review_fields(self):
        before = self.get(self.reviews)
        renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                         self.selection, self.catalog, self.root / "technical", now=NOW)
        after = self.get(self.reviews)
        for old, new in zip(before["sources"], after["sources"]):
            for key in ("decision", "reviewer", "reviewer_role", "reviewed_at", "checks",
                        "provenance_file", "provenance_sha256"):
                self.assertEqual(old[key], new[key])
        self.assertEqual(self.check()["activation"], "eligible_not_activated")

    def test_technical_completion_refuses_stale_binding_without_mutation(self):
        draft = self.get(self.reviews); draft["input_sha256"]["catalog"] = "c" * 64
        self.put(self.reviews, draft); before = self.reviews.read_bytes()
        with self.assertRaises(ValueError):
            renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                             self.selection, self.catalog, self.root / "technical", now=NOW)
        self.assertEqual(self.reviews.read_bytes(), before)
        self.assertEqual(self.bytes(), self.originals)

    def test_technical_completion_refuses_changed_provenance_instead_of_rebinding(self):
        draft = self.get(self.reviews); before = self.reviews.read_bytes()
        path = self.root / draft["sources"][0]["provenance_file"]
        evidence = self.get(path); evidence["observed_at"] = "2026-10-27T13:45:00+00:00"
        self.put(path, evidence)
        with self.assertRaisesRegex(ValueError, "silently rebind"):
            renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                             self.selection, self.catalog, self.root / "technical", now=NOW)
        self.assertEqual(self.reviews.read_bytes(), before)

    def test_technical_completion_write_failure_preserves_draft_and_backup(self):
        before = self.reviews.read_bytes(); folder = self.root / "technical"
        with patch.object(renewal, "_replace", side_effect=OSError("synthetic write failure")):
            with self.assertRaises(OSError):
                renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                                 self.selection, self.catalog, folder, now=NOW)
        self.assertEqual(self.reviews.read_bytes(), before)
        self.assertEqual((folder / "review.before.json").read_bytes(), before)
        self.assertEqual(self.bytes(), self.originals)

    def test_technical_completion_cli_requires_new_local_evidence_directory(self):
        common = ["--owner-authorization", str(self.owner), "--approvals", str(self.approvals),
                  "--selection", str(self.selection), "--catalog", str(self.catalog),
                  "--reviews", str(self.reviews)]
        folder = self.root / "technical"
        with patch.object(renewal, "_now", side_effect=lambda value=None: value or NOW):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["complete-renewal-technical", *common, "--output-dir", str(folder)]), 0)
        before = self.reviews.read_bytes()
        with self.assertRaises(ValueError):
            renewal.complete_technical_review(self.owner, self.reviews, self.approvals,
                                             self.selection, self.catalog, folder, now=NOW)
        self.assertEqual(self.reviews.read_bytes(), before)

    def dated_service(self):
        def transport(url, headers, body, timeout, limit):
            payload = json.loads(body)
            prompt = payload["messages"][0]["content"]
            paragraphs = json.loads(prompt.split("SOURCE_PARAGRAPHS=", 1)[1].splitlines()[0])
            p = paragraphs[0]
            claim = {"id": "c1", "text": p["text"], "paragraph_id": p["id"], "evidence_quote": p["text"]}
            return json.dumps({"message": {"content": json.dumps({"claims": [claim]})}}).encode()
        calls = Mock(side_effect=transport)
        client = OllamaClient(OllamaConfig(model="llama3.2:3b"), transport=calls)
        service = create_municipal_service([self.catalog], self.approvals, client=client)
        return service, calls

    def test_original_october_approval_blocks_november_20_before_model_access(self):
        with runtime_date("2026-11-20"), patch("hamar_agent.provider_registry.require_installed_ollama_model") as model:
            with self.assertRaisesRegex(ValueError, "expired"):
                create_municipal_service([self.catalog], self.approvals, model="llama3.2:3b")
            model.assert_not_called()
        self.assertEqual(self.bytes(), self.originals)

    def test_authorized_synthetic_renewal_loads_searches_and_answers_on_november_20(self):
        self.activate()
        with runtime_date("2026-11-20"):
            service, calls = self.dated_service()
            portal = PortalService(service)
            self.assertEqual(portal.overview()["documents"], 2)
            self.assertTrue(portal.search("SFO")["results"])
            answer = portal.answer("SFO")
            self.assertEqual(answer["answer_status"], "evidence_checked")
            self.assertFalse(answer["result"]["verification"]["findings"])
            self.assertTrue(all(c["text"] == c["evidence_quote"] for c in answer["result"]["claims"]))
            calls.assert_called_once()

    def test_authorized_expiry_is_inclusive_on_november_27(self):
        self.activate()
        with runtime_date("2026-11-27"):
            approvals = load_approvals(self.approvals)
            self.assertTrue(all(a.current() for a in approvals.values()))
            service, calls = self.dated_service()
            result = service.run("hamar-test-1")
            self.assertFalse(result.verification.has_findings)
            calls.assert_called_once()

    def test_november_28_refuses_new_startup_without_contacting_model(self):
        self.activate()
        with runtime_date("2026-11-28"), patch("hamar_agent.provider_registry.require_installed_ollama_model") as model:
            with self.assertRaisesRegex(ValueError, "expired"):
                create_municipal_service([self.catalog], self.approvals, model="llama3.2:3b")
            model.assert_not_called()

    def test_already_running_service_drops_expired_search_and_AI_on_november_28(self):
        self.activate()
        with runtime_date("2026-11-20"):
            service, calls = self.dated_service()
            portal = PortalService(service)
            self.assertTrue(portal.search("SFO")["results"])
        with runtime_date("2026-11-28"):
            self.assertEqual(portal.overview()["documents"], 0)
            self.assertFalse(portal.search("SFO")["results"])
            self.assertEqual(portal.answer("SFO")["answer_status"], "insufficient_evidence")
            with self.assertRaises(RealSourceError): service.run("hamar-test-1")
            calls.assert_not_called()

    def test_clock_simulation_does_not_change_real_time_or_any_input(self):
        import hamar_agent.portal_sources as sources
        import hamar_agent.search as search
        real_sources_date, real_search_date = sources.date, search.date
        today = date.today()
        for day in ("2026-11-20", "2026-11-28"):
            with runtime_date(day):
                self.assertEqual(sources.date.today().isoformat(), day)
                self.assertEqual(search.date.today().isoformat(), day)
                with self.assertRaises(ValueError): load_approvals(self.approvals)
        self.assertIs(sources.date, real_sources_date)
        self.assertIs(search.date, real_search_date)
        self.assertEqual(date.today(), today)
        self.assertEqual(self.bytes(), self.originals)


if __name__ == "__main__":
    unittest.main()
