"""Explicit administrative import of individually reviewed service excerpts.

No discovery or recursion. Raw HTML is transient. Existing output is never
replaced. A successful run creates both an expiring approval manifest and a
catalog containing only reviewed paragraphs, not the original response.
"""
import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .categories import CATEGORY_IDS
from .html_extract import extract_service_excerpts, privacy_check
from .portal_sources import ReviewedFetcher, PageApproval, MAX_BYTES, AGENT, validate_page_url, import_reviewed_bytes, save_catalog
from .robots_policy import robots_interval


def load_selection(path):
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Selection too large")
    entries = json.loads(raw)
    if not isinstance(entries, list) or not 1 <= len(entries) <= 20:
        raise ValueError("Explicit bounded reviewed selection required")
    ids, urls = set(), set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"source_id", "url", "title", "category", "paragraph_sha256", "reviewed_on", "expires_on"}:
            raise ValueError("Invalid reviewed selection")
        if not date.fromisoformat(entry["reviewed_on"]) <= date.today() <= date.fromisoformat(entry["expires_on"]):
            raise ValueError("Selection approval is expired or not yet valid")
        validate_page_url(entry["url"])
        if not isinstance(entry["source_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", entry["source_id"]):
            raise ValueError("Invalid source ID")
        if entry["source_id"] in ids or entry["url"] in urls or entry["category"] not in CATEGORY_IDS:
            raise ValueError("Duplicate source or unknown category")
        if not isinstance(entry["title"], str) or not entry["title"].strip():
            raise ValueError("Reviewed source title required")
        privacy_check(entry["title"])
        hashes = entry["paragraph_sha256"]
        if not isinstance(hashes, list) or not 1 <= len(hashes) <= 80 or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes) or len(set(hashes)) != len(hashes):
            raise ValueError("Exact reviewed paragraph hashes required")
        ids.add(entry["source_id"]); urls.add(entry["url"])
    return entries


def import_selection(selection, approvals_path, output, *, enable_live=False, fetcher=None):
    entries = load_selection(selection)  # Reject BEFORE DNS or any acquisition.
    if not enable_live:
        raise ValueError("Explicit --enable-live required")
    if approvals_path.resolve() == output.resolve() or approvals_path.exists() or output.exists():
        raise ValueError("Both destinations must be new and distinct")
    if not approvals_path.parent.is_dir() or not output.parent.is_dir():
        raise ValueError("Destination parent directories must already exist")
    fetcher = fetcher or ReviewedFetcher()
    robots = fetcher._get("https://www.hamar.kommune.no/robots.txt", "text/plain", 65536, 5)
    approvals, documents = [], []
    for entry in entries:
        interval = robots_interval(robots, entry["url"], AGENT)
        raw = fetcher._get(entry["url"], "text/html", MAX_BYTES, interval)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        paragraphs = extract_service_excerpts(raw.decode("utf-8", errors="strict"), entry["paragraph_sha256"])
        approval = PageApproval(source_id=entry["source_id"], url=entry["url"], title=entry["title"], category=entry["category"],
            reviewed_on=entry["reviewed_on"], expires_on=entry["expires_on"],
            raw_sha256=hashlib.sha256(raw).hexdigest(), text_sha256=hashlib.sha256("\n\n".join(paragraphs).encode()).hexdigest(),
            robots_sha256=hashlib.sha256(robots).hexdigest(),
            rationale="Individually reviewed non-personal service paragraphs; transient HTML allowed by explicit user decision. No linked pages approved.",
            no_personal_data=True, review_scope="service_excerpts", paragraph_sha256=tuple(entry["paragraph_sha256"]))
        documents.append(import_reviewed_bytes(approval, raw, retrieved_at=retrieved_at, robots=robots))
        approvals.append(approval)
        del raw  # Never write HTML or unselected text to disk.
    with approvals_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps([asdict(a) for a in approvals], ensure_ascii=False, indent=2)+"\n")
    # If this exclusive write fails, the manifest may remain; nothing is removed.
    save_catalog(documents, output)
    return documents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--approvals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--enable-live", action="store_true")
    args = parser.parse_args(argv)
    try:
        docs = import_selection(args.selection, args.approvals, args.output, enable_live=args.enable_live)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(2, "Reviewed import failed; no unreviewed content was retained. Check selection, policy and destinations.\n")
    print(json.dumps({"sources": len(docs), "paragraphs": sum(len(d.source.paragraphs) for d in docs), "raw_html_saved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
