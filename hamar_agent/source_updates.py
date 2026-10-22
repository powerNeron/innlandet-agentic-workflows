"""Privacy-bounded, proposal-only checks for manually reviewed text changes.

Raw municipal HTML acquisition is intentionally unavailable under the current
source policy. This module compares reviewer-prepared plain-text excerpts to the
approved local catalog and writes a separate, non-authoritative proposal report.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from types import SimpleNamespace

from .html_extract import privacy_check
from .portal_sources import PageApproval

MAX_CANDIDATE_BYTES = 64 * 1024
MAX_PARAGRAPHS = 80


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def validate_candidate(data: dict) -> dict:
    if not isinstance(data, dict) or set(data) != {"source_id", "url", "observed_at", "paragraphs"}:
        raise ValueError("Candidate must contain only source_id, url, observed_at and paragraphs")
    if not isinstance(data["source_id"], str) or not isinstance(data["url"], str):
        raise ValueError("Invalid source identity")
    observed = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
    if observed.tzinfo is None or observed > datetime.now(timezone.utc):
        raise ValueError("Candidate timestamp must be timezone-aware and not in the future")
    paragraphs = data["paragraphs"]
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= MAX_PARAGRAPHS:
        raise ValueError("Candidate needs 1 to 80 plain-text paragraphs")
    total = 0
    for text in paragraphs:
        if not isinstance(text, str) or not text.strip() or re.search(r"<[^>]*>", text):
            raise ValueError("Candidate must contain plain text excerpts, not HTML")
        total += len(text.encode("utf-8"))
        if total > MAX_CANDIDATE_BYTES:
            raise ValueError("Candidate text exceeds the size limit")
        privacy_check(text)
    return {**data, "observed_at": observed.astimezone(timezone.utc).isoformat()}


def load_candidate(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(MAX_CANDIDATE_BYTES + 1)
    if len(raw) > MAX_CANDIDATE_BYTES:
        raise ValueError("Candidate exceeds the size limit")
    return validate_candidate(json.loads(raw.decode("utf-8")))


def compare_candidate(candidate: dict, approvals: dict, catalog, *, today: date | None = None) -> dict:
    """Return a review proposal; never changes approvals or the active catalog."""
    candidate = validate_candidate(candidate)
    today = today or date.today()
    approval = approvals.get(candidate.get("source_id"))
    if approval is None or candidate.get("url") != approval.url:
        raise ValueError("Candidate does not match an exact approved source URL")
    document = catalog.documents.get(approval.source_id)
    if document is None or document.source.url != approval.url:
        raise ValueError("Approved source is missing from the current local catalog")
    old = [paragraph.text for paragraph in document.source.paragraphs]
    new = [normalize_text(value) for value in candidate["paragraphs"]]
    old_normalized = [normalize_text(value) for value in old]
    unchanged = old_normalized == new
    expired = date.fromisoformat(approval.expires_on) < today
    status = "approval_expired_human_review_required" if expired else ("unchanged" if unchanged else "changed_human_review_required")
    return {
        "report_version": 1,
        "source_id": approval.source_id,
        "url": approval.url,
        "checked_at": candidate["observed_at"],
        "previous_reviewed_on": approval.reviewed_on,
        "previous_approval_expires": approval.expires_on,
        "previous_text_sha256": approval.text_sha256,
        "previous_normalized_text_sha256": hashlib.sha256("\n\n".join(old_normalized).encode("utf-8")).hexdigest(),
        "candidate_normalized_text_sha256": hashlib.sha256("\n\n".join(new).encode("utf-8")).hexdigest(),
        "status": status,
        "human_approval_required": True,
        "old_excerpts": old,
        "proposed_excerpts": new,
        "approval_changed": False,
        "catalog_changed": False,
    }


def save_proposal(report: dict, path: Path) -> None:
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)


def load_update_inputs(approvals_path: Path, catalog_path: Path):
    """Validate approval/catalog identity for review, allowing expired records.

    This read-only path is intentionally separate from retrieval loaders, which
    continue to reject expired approvals before any model context is built.
    """
    with approvals_path.open("rb") as stream:
        approval_bytes = stream.read(64 * 1024 + 1)
    if len(approval_bytes) > 64 * 1024:
        raise ValueError("Approval manifest too large")
    records = json.loads(approval_bytes.decode("utf-8"))
    if not isinstance(records, list) or len(records) > 200:
        raise ValueError("Expected a reviewed page list")
    approvals = {}
    for record in records:
        approval = PageApproval(**record)
        if approval.source_id in approvals or any(item.url == approval.url for item in approvals.values()):
            raise ValueError("Duplicate approval")
        approvals[approval.source_id] = approval
    with catalog_path.open("rb") as stream:
        catalog_bytes = stream.read(16 * 1024 * 1024 + 1)
    if len(catalog_bytes) > 16 * 1024 * 1024:
        raise ValueError("Catalog too large")
    payload = json.loads(catalog_bytes.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("catalog_version") != 1 or not isinstance(payload.get("documents"), list):
        raise ValueError("Unsupported catalog")
    documents = {}
    for entry in payload["documents"]:
        source = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict):
            raise ValueError("Malformed catalog source")
        source_id = source.get("id")
        approval = approvals.get(source_id)
        if (approval is None or source.get("url") != approval.url or source.get("title") != approval.title
                or source.get("synthetic") is not False or entry.get("text_sha256") != approval.text_sha256
                or entry.get("raw_sha256") != approval.raw_sha256 or entry.get("approval_expires") != approval.expires_on
                or entry.get("category") != approval.category):
            raise ValueError("Catalog identity or reviewed hashes do not match approval")
        paragraphs = source.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs or any(not isinstance(p, dict) or not isinstance(p.get("id"), str) or not isinstance(p.get("text"), str) for p in paragraphs):
            raise ValueError("Malformed catalog paragraphs")
        text = "\n\n".join(p["text"] for p in paragraphs)
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != approval.text_sha256:
            raise ValueError("Catalog text integrity mismatch")
        if source_id in documents:
            raise ValueError("Duplicate catalog source")
        documents[source_id] = SimpleNamespace(source=SimpleNamespace(id=source_id, url=approval.url,
                                                                          paragraphs=tuple(SimpleNamespace(text=p["text"]) for p in paragraphs)))
    return approvals, SimpleNamespace(documents=documents)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("compare",))
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True, help="Human-prepared sanitized plain-text excerpts; raw HTML is refused")
    parser.add_argument("--output", type=Path, required=True, help="New proposal JSON path; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        approvals, catalog = load_update_inputs(args.approvals, args.catalog)
        candidate = load_candidate(args.candidate)
        report = compare_candidate(candidate, approvals, catalog)
        save_proposal(report, args.output)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(2, "Source update proposal failed safely; verify current approvals, sanitized excerpts and a new output path. No network was used.\n")
    print(json.dumps({"source_id": report["source_id"], "status": report["status"],
                      "output": str(args.output), "network_used": False,
                      "catalog_changed": False, "approval_changed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
