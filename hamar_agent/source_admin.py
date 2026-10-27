"""Local review controls and separately gated, unchanged-content renewal.

This module never fetches sources. The explicit owner-controlled renewal path
can update expiry metadata only after validating the complete review bundle. A
recorded decision is an auditable local human action, not cryptographic proof
of reviewer identity or permission to activate content.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from .html_extract import privacy_check
from .source_updates import normalize_text
from .source_updates import load_update_inputs

MAX_PROPOSAL_BYTES = 256 * 1024
MAX_AUDIT_BYTES = 32 * 1024
_SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
_ROLES = {"source-reviewer", "privacy-reviewer", "source-and-privacy-reviewer"}
_REQUIRED_PROPOSAL_FIELDS = {
    "report_version", "source_id", "url", "checked_at", "previous_reviewed_on",
    "previous_approval_expires", "previous_text_sha256", "previous_normalized_text_sha256",
    "candidate_normalized_text_sha256", "status", "human_approval_required",
    "old_excerpts", "proposed_excerpts", "approval_changed", "catalog_changed",
}


def _sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def load_proposal(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_PROPOSAL_BYTES:
        raise ValueError("Proposal missing or larger than the review limit")
    proposal = json.loads(raw.decode("utf-8"))
    if not isinstance(proposal, dict) or set(proposal) != _REQUIRED_PROPOSAL_FIELDS:
        raise ValueError("Unexpected proposal schema")
    source_id, url = proposal["source_id"], proposal["url"]
    if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
        raise ValueError("Invalid source identity")
    if not isinstance(url, str) or not url.startswith("https://www.hamar.kommune.no/") or any(x in url for x in ("?", "#", "@")):
        raise ValueError("Proposal URL is outside the exact official HTTPS source scope")
    if proposal["report_version"] != 1 or proposal["human_approval_required"] is not True:
        raise ValueError("Proposal is not eligible for human review")
    if proposal["catalog_changed"] is not False or proposal["approval_changed"] is not False:
        raise ValueError("Proposal claims to have changed active data")
    if proposal["status"] not in {"changed_human_review_required", "approval_expired_human_review_required", "unchanged"}:
        raise ValueError("Unsupported proposal status")
    for key in ("previous_text_sha256", "previous_normalized_text_sha256", "candidate_normalized_text_sha256"):
        if not isinstance(proposal[key], str) or not _sha(proposal[key]):
            raise ValueError("Invalid proposal integrity hash")
    for key in ("old_excerpts", "proposed_excerpts"):
        values = proposal[key]
        if not isinstance(values, list) or not 1 <= len(values) <= 80:
            raise ValueError("Proposal excerpt list is invalid")
        for excerpt in values:
            if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt.encode("utf-8")) > 16 * 1024:
                raise ValueError("Proposal contains an invalid excerpt")
            privacy_check(excerpt)
    for key in ("previous_reviewed_on", "previous_approval_expires"):
        date.fromisoformat(proposal[key])
    checked = datetime.fromisoformat(proposal["checked_at"].replace("Z", "+00:00"))
    if checked.tzinfo is None:
        raise ValueError("Proposal check timestamp must include a timezone")
    old_digest = hashlib.sha256("\n\n".join(normalize_text(x) for x in proposal["old_excerpts"]).encode("utf-8")).hexdigest()
    new_digest = hashlib.sha256("\n\n".join(normalize_text(x) for x in proposal["proposed_excerpts"]).encode("utf-8")).hexdigest()
    if old_digest != proposal["previous_normalized_text_sha256"] or new_digest != proposal["candidate_normalized_text_sha256"]:
        raise ValueError("Excerpt integrity does not match the proposal hashes")
    return proposal, hashlib.sha256(raw).hexdigest()


def validate_current_source(proposal: dict, approvals_path: Path, catalog_path: Path) -> None:
    """Bind a proposal to the currently approved local record without network I/O."""
    approvals, catalog = load_update_inputs(approvals_path, catalog_path)
    approval = approvals.get(proposal["source_id"])
    document = catalog.documents.get(proposal["source_id"])
    if approval is None or document is None or proposal["url"] != approval.url:
        raise ValueError("Proposal does not match the current exact source approval")
    if (proposal["previous_reviewed_on"] != approval.reviewed_on
            or proposal["previous_approval_expires"] != approval.expires_on
            or proposal["previous_text_sha256"] != approval.text_sha256):
        raise ValueError("Proposal approval metadata is stale or tampered")
    current_excerpts = [paragraph.text for paragraph in document.source.paragraphs]
    if proposal["old_excerpts"] != current_excerpts:
        raise ValueError("Proposal old excerpts do not match the active local catalog")
    if proposal["status"] == "unchanged" and proposal["candidate_normalized_text_sha256"] != proposal["previous_normalized_text_sha256"]:
        raise ValueError("Proposal unchanged status does not match its content hashes")
    if proposal["status"] == "changed_human_review_required" and proposal["candidate_normalized_text_sha256"] == proposal["previous_normalized_text_sha256"]:
        raise ValueError("Proposal changed status does not match its content hashes")


def make_decision(proposal: dict, proposal_sha256: str, *, decision: str,
                  reviewer_role: str, privacy_reviewer_role: str,
                  source_checked: bool, privacy_checked: bool,
                  service_facts_checked: bool, decided_at: datetime | None = None) -> dict:
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject")
    if reviewer_role not in _ROLES or privacy_reviewer_role not in _ROLES:
        raise ValueError("Reviewer roles must use the documented role values")
    checks = {"official_url_and_excerpt_reviewed": source_checked,
              "privacy_review_completed": privacy_checked,
              "dates_numbers_fees_and_conditions_reviewed": service_facts_checked}
    if decision == "approve" and not all(checks.values()):
        raise ValueError("Approval requires explicit source, privacy and service-fact review")
    if decision == "approve" and proposal["status"] == "approval_expired_human_review_required":
        raise ValueError("An expired approval cannot be renewed through proposal review")
    if decision == "approve" and reviewer_role == "privacy-reviewer":
        raise ValueError("Source review role is required to approve")
    if decision == "approve" and privacy_reviewer_role == "source-reviewer":
        raise ValueError("Privacy review role is required to approve")
    when = decided_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("Decision timestamp must include a timezone")
    return {
        "record_version": 1,
        "source_id": proposal["source_id"],
        "source_url": proposal["url"],
        "proposal_sha256": proposal_sha256,
        "previous_approval_expires": proposal["previous_approval_expires"],
        "decision": decision,
        "decision_status": "approved_pending_activation_review" if decision == "approve" else "rejected",
        "reviewer_role": reviewer_role,
        "privacy_reviewer_role": privacy_reviewer_role,
        "review_checks": checks,
        "decided_at": when.astimezone(timezone.utc).isoformat(),
        "activation": "not_activated",
        "identity_assurance": "local self-attested role; not independently authenticated",
    }


def save_exclusive(record: dict, path: Path) -> None:
    encoded = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_AUDIT_BYTES:
        raise ValueError("Review record exceeds its size limit")
    with path.open("xb") as stream:
        stream.write(encoded)


def blocked_activation(decision: dict, *, attempted_at: datetime | None = None) -> dict:
    if not isinstance(decision, dict) or decision.get("record_version") != 1:
        raise ValueError("Invalid human decision record")
    if decision.get("decision") != "approve" or decision.get("decision_status") != "approved_pending_activation_review":
        raise ValueError("Only an approved proposal can be considered for activation")
    when = attempted_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("Activation timestamp must include a timezone")
    return {
        "record_version": 1,
        "source_id": decision["source_id"],
        "proposal_sha256": decision["proposal_sha256"],
        "attempted_at": when.astimezone(timezone.utc).isoformat(),
        "activation": "blocked",
        "reason": "Raw HTML and snapshot import are disabled; sanitized proposal lacks the source-byte and robots provenance required by the active manifest.",
        "catalog_changed": False,
        "approval_changed": False,
    }


def _load_small_json(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_AUDIT_BYTES:
        raise ValueError("Decision record missing or too large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Decision record must be an object")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("review", help="Display a validated proposal without changing it")
    review.add_argument("--proposal", type=Path, required=True)
    review.add_argument("--approvals", type=Path, required=True)
    review.add_argument("--catalog", type=Path, required=True)
    decision = commands.add_parser("decide", help="Record a human approve/reject decision without activating it")
    decision.add_argument("--proposal", type=Path, required=True)
    decision.add_argument("--approvals", type=Path, required=True)
    decision.add_argument("--catalog", type=Path, required=True)
    decision.add_argument("--decision", choices=("approve", "reject"), required=True)
    decision.add_argument("--reviewer-role", choices=sorted(_ROLES), required=True)
    decision.add_argument("--privacy-reviewer-role", choices=sorted(_ROLES), required=True)
    decision.add_argument("--confirm", required=True, help="Type exactly '<decision> <source-id>' after reviewing the proposal")
    decision.add_argument("--source-checked", action="store_true")
    decision.add_argument("--privacy-checked", action="store_true")
    decision.add_argument("--service-facts-checked", action="store_true")
    decision.add_argument("--output", type=Path, required=True, help="New local audit JSON path; never overwritten")
    activate = commands.add_parser("activate", help="Owner-controlled expiry renewal, or legacy blocked content activation")
    activation_input = activate.add_mutually_exclusive_group(required=True)
    activation_input.add_argument("--decision-record", type=Path, help="Legacy content decision; remains blocked")
    activation_input.add_argument("--owner-authorization", type=Path, help="Recorded conditional owner authorization")
    activate.add_argument("--output", type=Path, help="Legacy blocked activation audit only")
    activate.add_argument("--reviews", type=Path)
    activate.add_argument("--approvals", type=Path)
    activate.add_argument("--selection", type=Path)
    activate.add_argument("--catalog", type=Path)
    activate.add_argument("--transaction-dir", type=Path, help="New directory for original bytes, staged bytes and audit")
    activate.add_argument("--confirm", help="Type exactly 'renew TARGET-DATE'")
    activate.add_argument("--application-stopped", action="store_true")
    for name in ("prepare-renewal", "check-renewal"):
        renewal = commands.add_parser(name, help="Prepare unchecked review forms" if name == "prepare-renewal" else "Read-only renewal eligibility check")
        renewal.add_argument("--owner-authorization", type=Path, required=True)
        renewal.add_argument("--approvals", type=Path, required=True)
        renewal.add_argument("--selection", type=Path, required=True)
        renewal.add_argument("--catalog", type=Path, required=True)
        if name == "prepare-renewal":
            renewal.add_argument("--output", type=Path, required=True)
        else:
            renewal.add_argument("--reviews", type=Path, required=True)
    recover = commands.add_parser("recover-renewal", help="Restore original bytes after an interrupted renewal")
    recover.add_argument("--transaction-dir", type=Path, required=True)
    recover.add_argument("--approvals", type=Path, required=True)
    recover.add_argument("--selection", type=Path, required=True)
    recover.add_argument("--catalog", type=Path, required=True)
    recover.add_argument("--application-stopped", action="store_true")
    args = parser.parse_args(argv)
    if args.command in {"prepare-renewal", "check-renewal", "recover-renewal"} or (
            args.command == "activate" and args.owner_authorization is not None):
        return _renewal_command(args)
    try:
        if args.command == "review":
            proposal, digest = load_proposal(args.proposal)
            validate_current_source(proposal, args.approvals, args.catalog)
            print(json.dumps({key: proposal[key] for key in ("source_id", "url", "checked_at", "previous_reviewed_on", "previous_approval_expires", "status", "old_excerpts", "proposed_excerpts")}, ensure_ascii=False, indent=2))
            print("PROPOSAL_SHA256=" + digest)
            return 0
        if args.command == "decide":
            proposal, digest = load_proposal(args.proposal)
            validate_current_source(proposal, args.approvals, args.catalog)
            if args.confirm != f"{args.decision} {proposal['source_id']}":
                raise ValueError("Explicit decision confirmation did not match the proposal")
            record = make_decision(proposal, digest, decision=args.decision,
                reviewer_role=args.reviewer_role, privacy_reviewer_role=args.privacy_reviewer_role,
                source_checked=args.source_checked, privacy_checked=args.privacy_checked,
                service_facts_checked=args.service_facts_checked)
            save_exclusive(record, args.output)
            print(json.dumps({"source_id": record["source_id"], "decision_status": record["decision_status"],
                              "activation": record["activation"], "audit_record": str(args.output)}, ensure_ascii=False))
            return 0
        if args.output is None:
            raise ValueError("Legacy activation requires a new --output audit path")
        record = _load_small_json(args.decision_record)
        blocked = blocked_activation(record)
        save_exclusive(blocked, args.output)
        print(json.dumps(blocked, ensure_ascii=False))
        return 3
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("Source administration stopped safely: " + str(exc), file=sys.stderr)
        return 2


def _renewal_command(args):
    from .source_renewal import (prepare_review, check_renewal, activate_renewal,
                                 recover_renewal, RenewalError)
    try:
        if args.command == "recover-renewal":
            result = recover_renewal(args.transaction_dir, args.approvals, args.selection,
                                    args.catalog, application_stopped=args.application_stopped)
        else:
            inputs = (args.owner_authorization, args.approvals, args.selection, args.catalog)
            if args.command == "prepare-renewal":
                result = prepare_review(*inputs)
                save_exclusive(result, args.output)
                print(json.dumps({"review_draft": str(args.output), "activation": "not_attempted",
                                  "all_review_checks": False}))
                return 0
            if args.command == "check-renewal":
                result, _, _, _ = check_renewal(args.owner_authorization, args.reviews,
                                               args.approvals, args.selection, args.catalog)
            else:
                if any(x is None for x in (*inputs, args.reviews, args.transaction_dir, args.confirm)) or args.output is not None:
                    raise RenewalError("Renewal requires owner authorization, reviews, approvals, selection, catalog, a new transaction-dir and confirm; omit legacy output")
                result = activate_renewal(args.owner_authorization, args.reviews,
                                         args.approvals, args.selection, args.catalog,
                                         args.transaction_dir, confirm=args.confirm,
                                         application_stopped=args.application_stopped)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result.get("activation") == "blocked" else 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        reason = str(exc) if isinstance(exc, RenewalError) else "Missing, malformed or unwritable renewal inputs; no successful activation is claimed. Inspect any transaction journal before restarting."
        print("Source renewal stopped safely: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
