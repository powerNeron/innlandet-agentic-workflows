"""Offline, owner-controlled expiry renewal of unchanged reviewed excerpts.

Human attestations are trusted local inputs, not authenticated identities or
proof of factual truth. No network, HTML parser, model or automatic review is
used here. Runtime loaders and their expiry checks are unchanged.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .html_extract import privacy_check
from .portal_sources import PageApproval
from .schemas import Paragraph, Source
from .search import IndexedDocument


CHECKS = (
    "official_url_and_excerpt_reviewed",
    "dates_numbers_fees_and_conditions_reviewed",
    "privacy_review_completed",
    "no_personal_data_in_retained_content",
    "permitted_non_personal_input_boundary_confirmed",
    "source_and_robots_provenance_reviewed",
    "retained_content_current_for_extension",
)
PROVENANCE_CHECKS = (
    "current_service_information_verified", "source_permission_verified",
    "non_personal_input_boundary_verified", "original_hash_provenance_verified",
)
class RenewalError(ValueError):
    """Controlled diagnostic without source text or private paths."""


LABELS = ("approvals", "selection", "catalog")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RenewalError("Duplicate JSON key")
        result[key] = value
    return result


def _decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)


def _path(path):
    path = Path(path).absolute()
    if path.as_posix().startswith("//"):
        raise RenewalError("Renewal inputs must be local, not network shares")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RenewalError("Symlinks are not permitted in renewal paths")
    return path.resolve()


def _read(path, limit=65536):
    path = _path(path)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise RenewalError("Renewal input exceeds its size limit")
    return data


def _now(value=None):
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise RenewalError("Timezone-aware time required")
    return value.astimezone(timezone.utc)


def _timestamp(value):
    if not isinstance(value, str):
        raise RenewalError("Documented review timestamp is missing")
    return _now(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _exclusive(path, data):
    """Publish a complete new file without replacing an existing entry."""
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix=".renewal-audit-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic exclusive publication, same filesystem.
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                # Publication already succeeded or failed independently. A
                # leftover private staging link must not turn a committed
                # audit into a reported write failure and trigger rollback.
                pass


def _replace(path, data):
    """One-file atomic replacement, staged on the destination filesystem."""
    descriptor, name = tempfile.mkstemp(prefix=".renewal-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _state(approvals, selection, catalog):
    paths = dict(zip(LABELS, map(_path, (approvals, selection, catalog))))
    if len(set(paths.values())) != 3:
        raise RenewalError("Renewal destinations must be distinct")
    if any(path.stat().st_nlink != 1 for path in paths.values()):
        raise RenewalError("Hard-linked renewal destinations are not supported")
    originals = {k: _read(p, 16 * 1024 * 1024 if k == "catalog" else 65536)
                 for k, p in paths.items()}
    values = {k: _decode(v) for k, v in originals.items()}
    approved, selected, documents = {}, {}, {}
    if not isinstance(values["approvals"], list) or not 1 <= len(values["approvals"]) <= 200:
        raise RenewalError("Expected a nonempty approval list")
    for row in values["approvals"]:
        approval = PageApproval(**row)
        if approval.review_scope != "service_excerpts":
            raise RenewalError("Only unchanged reviewed service excerpts can be renewed")
        if approval.source_id in approved or any(a.url == approval.url for a in approved.values()):
            raise RenewalError("Duplicate approval identity")
        approved[approval.source_id] = approval
    if not isinstance(values["selection"], list):
        raise RenewalError("Expected a selection list")
    for row in values["selection"]:
        source_id = row["source_id"]
        if source_id in selected or source_id not in approved:
            raise RenewalError("Duplicate or unknown selection")
        approval = approved[source_id]
        for key in ("source_id", "url", "title", "category", "reviewed_on", "expires_on"):
            if row[key] != getattr(approval, key):
                raise RenewalError("Selection identity/provenance mismatch")
        if tuple(row["paragraph_sha256"]) != approval.paragraph_sha256:
            raise RenewalError("Selection paragraph scope mismatch")
        selected[source_id] = row
    catalog_value = values["catalog"]
    if not isinstance(catalog_value, dict) or catalog_value.get("catalog_version") != 1:
        raise RenewalError("Unsupported catalog")
    for entry in catalog_value["documents"]:
        raw_source = dict(entry["source"])
        raw_source["paragraphs"] = tuple(Paragraph(**p) for p in raw_source["paragraphs"])
        source = Source(**raw_source)
        fields = {k: v for k, v in entry.items() if k != "source"}
        document = IndexedDocument(source=source, **fields)
        approval = approved.get(source.id)
        if source.id in documents or approval is None or source.synthetic:
            raise RenewalError("Duplicate, unknown or synthetic catalog source")
        if (source.url != approval.url or source.title != approval.title
                or document.category != approval.category
                or document.text_sha256 != approval.text_sha256
                or document.raw_sha256 != approval.raw_sha256
                or document.approval_expires != approval.expires_on):
            raise RenewalError("Catalog identity/provenance mismatch")
        hashes = tuple(digest(p.text.encode("utf-8")) for p in source.paragraphs)
        if hashes != approval.paragraph_sha256:
            raise RenewalError("Catalog paragraph hashes do not match approval")
        privacy_check(source.title)
        for paragraph in source.paragraphs:
            privacy_check(paragraph.text)
        documents[source.id] = document
    if set(approved) != set(selected) or set(approved) != set(documents):
        raise RenewalError("All three inputs must cover exactly the same sources")
    return paths, originals, values, approved, documents


def _authorization(path, approved, now):
    raw = _read(path)
    record = _decode(raw)
    if (record.get("record_type") != "project_owner_conditional_renewal_authorization_and_technical_review"
            or record.get("record_version") != 1):
        raise RenewalError("Recorded project-owner authorization required")
    owner = record["authorization"]
    source_ids = owner["source_ids"]
    if (owner.get("actor_role") != "project_owner"
            or owner.get("subject_to_mandatory_source_provenance_and_privacy_checks") is not True
            or not isinstance(source_ids, list) or len(source_ids) != len(set(source_ids))
            or set(source_ids) != set(approved)
            or not {"municipal_search", "real_source_ollama_workflow"}.issubset(owner["scope"])):
        raise RenewalError("Owner authorization role, scope or source set is invalid")
    authorized_on = date.fromisoformat(owner["decision_date"])
    target = date.fromisoformat(owner["requested_expiry"])
    if authorized_on > now.date() or not authorized_on <= now.date() <= target:
        raise RenewalError("Owner authorization is future-dated or no longer eligible")
    if any(not date.fromisoformat(a.reviewed_on) <= authorized_on
           or target <= date.fromisoformat(a.expires_on) for a in approved.values()):
        raise RenewalError("Renewal must extend the recorded approvals; replay is refused")
    return raw, target.isoformat()


def _binding(approval, document):
    return {"source_id": approval.source_id, "url": approval.url,
            "paragraph_ids": [p.id for p in document.source.paragraphs],
            "paragraph_sha256": list(approval.paragraph_sha256),
            "text_sha256": approval.text_sha256, "raw_sha256": approval.raw_sha256,
            "robots_sha256": approval.robots_sha256}


def prepare_review(authorization, approvals, selection, catalog, *, now=None):
    """Produce unchecked human review forms, never a decision or activation."""
    now = _now(now)
    _, originals, _, approved, documents = _state(approvals, selection, catalog)
    owner_raw, target = _authorization(authorization, approved, now)
    return {"record_type": "source_renewal_review", "record_version": 1,
            "authorization_sha256": digest(owner_raw),
            "input_sha256": {k: digest(v) for k, v in originals.items()},
            "target_expiry": target,
            "identity_assurance": "Local human attestations; not independent authentication.",
            "sources": [{**_binding(a, documents[s]), "decision": "pending",
                         "reviewed_at": None, "reviewer": None, "reviewer_role": None,
                         "checks": {key: False for key in CHECKS},
                         "provenance_file": None, "provenance_sha256": None,
                         "provenance_template": {
                             **_binding(a, documents[s]),
                             "record_type": "source_renewal_provenance", "record_version": 1,
                             "observed_at": None,
                             "input_boundary": "authorized_non_personal_material",
                             "checks": {key: False for key in PROVENANCE_CHECKS}}}
                        for s, a in approved.items()]}


def complete_technical_review(authorization, reviews, approvals, selection, catalog,
                              output_dir, *, now=None):
    """Fill locally verifiable metadata, never human attestations or freshness.

    Preserve the input draft before updating it. Evidence drafts stay explicitly
    unchecked; a real file digest is not proof of human provenance review.
    """
    now = _now(now)
    review_path = _path(reviews)
    directory = _path(output_dir)
    if directory.exists() or directory == review_path.parent or not directory.is_relative_to(review_path.parent):
        raise RenewalError("Use a new technical-evidence directory beneath the review directory")
    lock = review_path.with_name(review_path.name + ".technical.lock")
    _exclusive(lock, b"technical-review\n")
    try:
        original = _read(review_path, 512 * 1024)
        review = _decode(original)
        fresh = prepare_review(authorization, approvals, selection, catalog, now=now)
        for key in ("record_type", "record_version", "authorization_sha256", "input_sha256", "target_expiry"):
            if review.get(key) != fresh[key]:
                raise RenewalError("Technical completion refuses stale authorization, inputs or expiry")
        paths, originals, _, approved, documents = _state(approvals, selection, catalog)
        rows = review.get("sources")
        if (not isinstance(rows, list) or len(rows) != len(approved)
                or {row["source_id"] for row in rows} != set(approved)):
            raise RenewalError("Technical completion requires one review per authorized source")
        for row in rows:
            binding = _binding(approved[row["source_id"]], documents[row["source_id"]])
            if any(row.get(key) != value for key, value in binding.items()):
                raise RenewalError("Technical completion refuses changed source identity or hashes")
        directory.mkdir()
        _exclusive(directory / "review.before.json", original)
        worksheet = []
        for row in rows:
            source_id = row["source_id"]
            binding = _binding(approved[source_id], documents[source_id])
            filename = row.get("provenance_file")
            if filename is None:
                if row.get("provenance_sha256") is not None:
                    raise RenewalError("A provenance hash without a file cannot be repaired automatically")
                evidence = {**binding, "record_type": "source_renewal_provenance", "record_version": 1,
                            "observed_at": None, "input_boundary": "authorized_non_personal_material",
                            "checks": {key: False for key in PROVENANCE_CHECKS}}
                evidence_path = directory / (source_id + ".provenance.json")
                evidence_raw = _encoded(evidence)
                _exclusive(evidence_path, evidence_raw)
                row["provenance_file"] = evidence_path.relative_to(review_path.parent).as_posix()
            else:
                if (not isinstance(filename, str) or "\\" in filename or ":" in filename
                        or Path(filename).is_absolute() or ".." in Path(filename).parts
                        or Path(filename).suffix != ".json"):
                    raise RenewalError("Relative sanitized provenance JSON file required")
                evidence_path = _path(review_path.parent / filename)
                if not evidence_path.is_relative_to(review_path.parent):
                    raise RenewalError("Provenance file is outside review directory")
                evidence_raw = _read(evidence_path)
                evidence = _decode(evidence_raw)
                if any(evidence.get(k) != v for k, v in binding.items()):
                    raise RenewalError("Technical completion refuses mismatched provenance bindings")
                if row.get("provenance_sha256") not in (None, digest(evidence_raw)):
                    raise RenewalError("Provenance file changed; do not silently rebind a reviewed file")
            row["provenance_sha256"] = digest(evidence_raw)
            row["technical_verification"] = {
                "verified_at_utc": now.isoformat(), "performed_by": "source-renewal-tool",
                "method": "Existing local records only; no municipal retrieval or human review.",
                "checks": {key: True for key in (
                    "approval_schema_and_official_https_url_valid", "source_identity_matches",
                    "selection_scope_matches", "paragraph_identity_and_hashes_match",
                    "combined_text_hash_matches", "recorded_provenance_matches_catalog",
                    "recorded_expiry_matches_catalog", "limited_privacy_pattern_screen_no_flags")},
                "provenance_file_hash_verified": True,
                "human_review_performed": False, "source_freshness_established": False,
                "privacy_clearance_established": False}
            worksheet.append({"source_id": source_id, "url": row["url"],
                              "paragraphs": [{"id": p.id, "text": p.text}
                                             for p in documents[source_id].source.paragraphs],
                              "owner_must_assess": list(CHECKS),
                              "provenance_attestations_required": list(PROVENANCE_CHECKS),
                              "decision": row.get("decision"), "technical_verification": row["technical_verification"]})
        _exclusive(directory / "owner-review-items.json", _encoded({
            "record_type": "local_owner_review_worksheet", "recorded_at_utc": now.isoformat(),
            "target_expiry": fresh["target_expiry"], "human_review_performed": False,
            "sources": worksheet}))
        if _read(review_path, 512 * 1024) != original or any(
                _read(paths[k], 16 * 1024 * 1024) != originals[k] for k in LABELS):
            raise RenewalError("Inputs changed during technical completion; draft not overwritten")
        _replace(review_path, _encoded(review))
        return {"activation": "not_attempted", "technical_sources_verified": len(rows),
                "paragraphs_verified": sum(len(d.source.paragraphs) for d in documents.values()),
                "human_reviews_created": 0, "review_file_sha256": digest(_encoded(review)),
                "source_expiries_changed": False}
    finally:
        lock.unlink()


def _review(row, binding, review_path, now):
    for key, value in binding.items():
        if row.get(key) != value:
            raise RenewalError("Review source identity or hashes are stale/invalid")
    if row.get("decision") != "approve":
        raise RenewalError("Documented source/privacy approval is missing or rejected")
    if (row.get("reviewer_role") not in {"project-owner", "source-and-privacy-reviewer"}
            or not isinstance(row.get("reviewer"), str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", row["reviewer"])):
        raise RenewalError("Reviewer project identifier and combined review role required")
    reviewed = _timestamp(row.get("reviewed_at"))
    if reviewed.date() != now.date() or reviewed > now:
        raise RenewalError("Review must be current (same UTC day), never future-dated")
    checks = row.get("checks", {})
    missing = [key for key in CHECKS if checks.get(key) is not True]
    if missing:
        raise RenewalError("Missing review checks: " + ", ".join(missing))
    filename = row.get("provenance_file")
    if (not isinstance(filename, str) or not filename or "\\" in filename
            or Path(filename).is_absolute() or ":" in filename
            or ".." in Path(filename).parts or Path(filename).suffix != ".json"):
        raise RenewalError("Relative sanitized provenance JSON file required")
    evidence_path = _path(review_path.parent / filename)
    if not evidence_path.is_relative_to(review_path.parent):
        raise RenewalError("Provenance evidence must be inside the review directory")
    raw = _read(evidence_path)
    if digest(raw) != row.get("provenance_sha256"):
        raise RenewalError("Provenance evidence hash does not match review")
    evidence = _decode(raw)
    expected = {"record_type", "record_version", "observed_at", "input_boundary", "checks", *binding}
    if (set(evidence) != expected or evidence.get("record_type") != "source_renewal_provenance"
            or evidence.get("record_version") != 1
            or evidence.get("input_boundary") != "authorized_non_personal_material"
            or any(evidence.get(k) != v for k, v in binding.items())
            or any(evidence.get("checks", {}).get(k) is not True for k in PROVENANCE_CHECKS)):
        raise RenewalError("Current non-personal source/robots provenance is invalid or incomplete")
    observed = _timestamp(evidence["observed_at"])
    if observed.date() != now.date() or observed > reviewed:
        raise RenewalError("Provenance observation must precede review on the same UTC day")
    return {"source_id": binding["source_id"], "reviewer": row["reviewer"],
            "reviewer_role": row["reviewer_role"], "reviewed_at": row["reviewed_at"],
            "review_checks": {k: True for k in CHECKS},
            "provenance_file": filename, "provenance_sha256": digest(raw)}


def check_renewal(authorization, reviews, approvals, selection, catalog, *, now=None):
    """Read-only validation with a separate refusal for every incomplete source."""
    now = _now(now)
    paths, originals, values, approved, documents = _state(approvals, selection, catalog)
    owner_raw, target = _authorization(authorization, approved, now)
    review_path = _path(reviews)
    raw = _read(review_path, 512 * 1024)
    review = _decode(raw)
    if (review.get("record_type") != "source_renewal_review" or review.get("record_version") != 1
            or review.get("authorization_sha256") != digest(owner_raw)
            or review.get("input_sha256") != {k: digest(v) for k, v in originals.items()}
            or review.get("target_expiry") != target):
        raise RenewalError("Review must bind the exact authorization, inputs and target expiry")
    rows = review["sources"]
    if not isinstance(rows, list) or len({r["source_id"] for r in rows}) != len(rows):
        raise RenewalError("Duplicate or malformed source reviews")
    by_id = {r["source_id"]: r for r in rows}
    if set(by_id) - set(approved):
        raise RenewalError("Review contains unauthorized sources")
    errors, decisions = [], []
    for source_id, approval in approved.items():
        try:
            if source_id not in by_id:
                raise RenewalError("Source review is missing")
            decisions.append(_review(by_id[source_id], _binding(approval, documents[source_id]), review_path, now))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            # Do not echo filesystem paths, untrusted source text or exception bodies.
            reason = str(exc) if isinstance(exc, RenewalError) else "Review/evidence file is missing or malformed"
            row = by_id.get(source_id, {})
            checks = row.get("checks", {}) if isinstance(row, dict) else {}
            errors.append({"source_id": source_id, "reason": reason,
                           "missing_review_checks": [k for k in CHECKS if not isinstance(checks, dict) or checks.get(k) is not True],
                           "missing_review_fields": [k for k in ("reviewed_at", "reviewer", "reviewer_role", "provenance_file", "provenance_sha256") if not row.get(k)]})
    report = {"record_type": "source_renewal_activation", "record_version": 1,
              "recorded_at_utc": now.isoformat(), "target_expiry": target,
              "activation": "blocked" if errors else "eligible_not_activated",
              "errors": errors, "source_ids": list(approved), "reviews": decisions,
              "authorization_sha256": digest(owner_raw), "review_file_sha256": digest(raw),
              "input_sha256": {k: digest(v) for k, v in originals.items()},
              "identity_assurance": "Owner-controlled local attestations, not municipal/instructor approval."}
    return report, paths, originals, values


def activate_renewal(authorization, reviews, approvals, selection, catalog, transaction_dir,
                    *, confirm, application_stopped=False, now=None):
    """All-or-nothing on handled failures; preserve a durable recovery journal.

    Multi-file replacement is NOT crash-atomic. Stop application processes first.
    An interrupted PREPARED transaction must be recovered before restarting.
    """
    paths = dict(zip(LABELS, map(_path, (approvals, selection, catalog))))
    if not application_stopped:
        raise RenewalError("Stop application processes and confirm application-stopped")
    transaction = _path(transaction_dir)
    if transaction.exists() or any(transaction.is_relative_to(p) or p.is_relative_to(transaction)
                                   for p in (*paths.values(), _path(authorization), _path(reviews))):
        raise RenewalError("A new, separate transaction directory is required")
    lock_path = paths["approvals"].with_name(paths["approvals"].name + ".renewal.lock")
    lock_created = False
    keep_lock = False
    try:
        _exclusive(lock_path, _encoded({"transaction": str(transaction)}))
        lock_created = True
        report, paths, originals, values = check_renewal(
            authorization, reviews, approvals, selection, catalog, now=now)
        if report["errors"]:
            return report
        if confirm != "renew " + report["target_expiry"]:
            raise RenewalError("Explicit 'renew TARGET-DATE' confirmation required")
        target = report["target_expiry"]
        for row in values["approvals"]:
            row["expires_on"] = target
        for row in values["selection"]:
            row["expires_on"] = target
        for row in values["catalog"]["documents"]:
            row["approval_expires"] = target
        renewed = {key: _encoded(values[key]) for key in LABELS}
        if len(renewed["approvals"]) > 65536 or len(renewed["selection"]) > 65536 or len(renewed["catalog"]) > 16 * 1024 * 1024:
            raise RenewalError("Renewed input exceeds runtime size limits")
        transaction.mkdir()  # No reuse or overwrite of previous transaction/audits.
        for key in LABELS:
            _exclusive(transaction / (key + ".before.json"), originals[key])
            _exclusive(transaction / (key + ".after.json"), renewed[key])
        # Validate staged data with the same schema/provenance rules before writes.
        _state(*(transaction / (key + ".after.json") for key in LABELS))
        owner_raw = _read(authorization)
        review_raw = _read(reviews, 512 * 1024)
        if digest(owner_raw) != report["authorization_sha256"] or digest(review_raw) != report["review_file_sha256"]:
            raise RenewalError("Owner authorization or review changed during renewal")
        _exclusive(transaction / "authorization.json", owner_raw)
        _exclusive(transaction / "reviews.json", review_raw)
        for decision in report["reviews"]:
            evidence = _read(_path(reviews).parent / decision["provenance_file"])
            if digest(evidence) != decision["provenance_sha256"]:
                raise RenewalError("Provenance evidence changed during renewal")
            _exclusive(transaction / (decision["source_id"] + ".provenance.json"), evidence)
        report["output_sha256"] = {key: digest(value) for key, value in renewed.items()}
        report["destination_path_sha256"] = {key: digest(str(path).encode("utf-8")) for key, path in paths.items()}
        report["application_stopped_confirmed"] = True
        report["activation"] = "prepared"
        _exclusive(transaction / "PREPARED.json", _encoded(report))
        expected = dict(originals)
        attempted = []
        try:
            # Catalog first, approvals last: intermediate startup fails closed.
            for key in ("catalog", "selection", "approvals"):
                if any(_read(paths[k], 16 * 1024 * 1024) != expected[k] for k in LABELS):
                    raise RenewalError("Inputs changed during renewal; refusing overwrite")
                attempted.append(key)
                _replace(paths[key], renewed[key])
                expected[key] = renewed[key]
            if any(_read(paths[k], 16 * 1024 * 1024) != renewed[k] for k in LABELS):
                raise RenewalError("Post-write verification failed")
            report["activation"] = "activated"
            _exclusive(transaction / "COMMITTED.json", _encoded(report))
            return report
        except BaseException:
            restored = True
            for key in reversed(attempted):
                try:
                    current = _read(paths[key], 16 * 1024 * 1024)
                    if current not in (originals[key], renewed[key]):
                        raise RenewalError("Concurrent change requires manual recovery")
                    if current != originals[key]:
                        _replace(paths[key], originals[key])
                except BaseException:
                    restored = False
            try:
                restored = restored and all(_read(paths[k], 16 * 1024 * 1024) == originals[k] for k in LABELS)
            except OSError:
                restored = False
            keep_lock = not restored
            marker = "ROLLED_BACK.json" if restored else "RECOVERY_REQUIRED.json"
            try:
                _exclusive(transaction / marker, _encoded({"activation": "rolled_back" if restored else "recovery_required"}))
            except OSError:
                keep_lock = True
            raise
    finally:
        if lock_created and not keep_lock:
            lock_path.unlink()


def recover_renewal(transaction_dir, approvals, selection, catalog, *, application_stopped=False):
    """Restore an interrupted transaction using verified original bytes only."""
    if not application_stopped:
        raise RenewalError("Stop application processes before recovery")
    transaction = _path(transaction_dir)
    if (transaction / "COMMITTED.json").exists() or (transaction / "RECOVERED.json").exists():
        raise RenewalError("Committed or recovered transactions cannot be rolled back here")
    prepared = _decode(_read(transaction / "PREPARED.json", 512 * 1024))
    paths = dict(zip(LABELS, map(_path, (approvals, selection, catalog))))
    if prepared.get("destination_path_sha256") != {key: digest(str(path).encode("utf-8")) for key, path in paths.items()}:
        raise RenewalError("Recovery destinations do not match the transaction")
    lock = paths["approvals"].with_name(paths["approvals"].name + ".renewal.lock")
    if _decode(_read(lock)).get("transaction") != str(transaction):
        raise RenewalError("Recovery lock does not match transaction")
    originals = {}
    for key in LABELS:
        originals[key] = _read(transaction / (key + ".before.json"), 16 * 1024 * 1024)
        current = _read(paths[key], 16 * 1024 * 1024)
        if digest(originals[key]) != prepared["input_sha256"][key] or digest(current) not in (
                prepared["input_sha256"][key], prepared["output_sha256"][key]):
            raise RenewalError("Recovery hashes do not match; refusing overwrite")
    for key in LABELS:
        _replace(paths[key], originals[key])
    if any(_read(paths[k], 16 * 1024 * 1024) != originals[k] for k in LABELS):
        raise RenewalError("Recovery verification failed; keep application stopped")
    result = {"activation": "recovered_originals", "recorded_at_utc": _now().isoformat()}
    _exclusive(transaction / "RECOVERED.json", _encoded(result))
    lock.unlink()
    return result
