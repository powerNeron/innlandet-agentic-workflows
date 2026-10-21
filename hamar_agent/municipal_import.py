"""Explicit administrative import of individually reviewed service excerpts.

Live HTML import is currently disabled: even transiently fetching and parsing
a page can process personal information before excerpt filtering. Existing
reviewed catalogs remain readable; this importer fails closed until an input
format can guarantee that personal information is never acquired.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re

from .categories import CATEGORY_IDS
from .html_extract import privacy_check
from .portal_sources import validate_page_url


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
    # HTML excerpt filtering happens only after the response body has already
    # been acquired and parsed. That cannot satisfy the course's strict
    # no-processing-of-personal-data requirement, so fail before any request.
    raise ValueError("Live HTML import disabled: use a source format certified to contain no personal information")


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
