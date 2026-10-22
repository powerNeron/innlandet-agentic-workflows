"""Reviewed local snapshot/catalog imports; live HTML retrieval is disabled."""
import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket  # Compatibility namespace; no retrieval path calls it.
from types import MappingProxyType
from urllib.parse import urlsplit
from .robots_policy import robots_interval

from .categories import CATEGORY_IDS
from .html_extract import extract_html, extract_service_excerpts
from .retrieval import _validate_url
from .schemas import Paragraph, Source

HOST = "www.hamar.kommune.no"
AGENT = "HamarKommuneAgent/0.2"
MAX_BYTES = 512 * 1024


def validate_page_url(url):
    _validate_url(url)
    parts = urlsplit(url)
    if parts.hostname != HOST or "%" in parts.path or parts.path.startswith("//"):
        raise ValueError("Only exact reviewed canonical Hamar HTTPS page URLs are allowed")
    return parts


@dataclass(frozen=True)
class PageApproval:
    source_id: str
    url: str
    title: str
    category: str
    reviewed_on: str
    expires_on: str
    raw_sha256: str
    text_sha256: str
    robots_sha256: str
    rationale: str
    no_personal_data: bool
    content_type: str = "text/html"
    content_tag: str = "main"
    review_scope: str = "full_document"
    paragraph_sha256: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("source_id", "url", "title", "category", "reviewed_on", "expires_on", "raw_sha256", "text_sha256", "robots_sha256", "rationale", "content_type", "content_tag"):
            if not isinstance(getattr(self, name), str):
                raise ValueError("Approval text fields must be strings")
        if self.review_scope not in ("full_document", "service_excerpts"):
            raise ValueError("Invalid review scope")
        if self.review_scope == "service_excerpts":
            if self.content_type != "text/html" or not isinstance(self.paragraph_sha256, (list, tuple)) or not 1 <= len(self.paragraph_sha256) <= 80 or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in self.paragraph_sha256) or len(set(self.paragraph_sha256)) != len(self.paragraph_sha256):
                raise ValueError("Reviewed service paragraph hashes required")
            object.__setattr__(self, "paragraph_sha256", tuple(self.paragraph_sha256))
        validate_page_url(self.url)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", self.source_id):
            raise ValueError("Invalid source ID")
        if not self.title.strip() or not self.rationale.strip() or self.no_personal_data is not True:
            raise ValueError("Explicit non-personal review within the declared scope and rationale required")
        if self.category not in CATEGORY_IDS or self.content_type not in ("text/html", "text/plain") or self.content_tag not in ("main", "article"):
            raise ValueError("Unreviewed extraction policy")
        if date.fromisoformat(self.reviewed_on) > date.fromisoformat(self.expires_on):
            raise ValueError("Invalid approval dates")
        for digest in (self.raw_sha256, self.text_sha256, self.robots_sha256):
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Reviewed body, extracted text and robots SHA-256 required")

    def current(self):
        return date.fromisoformat(self.reviewed_on) <= date.today() <= date.fromisoformat(self.expires_on)


APPROVED_PAGES = MappingProxyType({})


def load_approvals(path: Path):
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("Approval manifest too large")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list) or len(data) > 200:
        raise ValueError("Expected a reviewed page list")
    result = {}
    for entry in data:
        approval = PageApproval(**entry)
        if not approval.current():
            raise ValueError("Manifest contains an expired or future approval")
        if approval.source_id in result or any(a.url == approval.url for a in result.values()):
            raise ValueError("Duplicate approval")
        result[approval.source_id] = approval
    return MappingProxyType(result)


def validate_robots(approval: PageApproval, raw: bytes):
    if len(raw) > 64 * 1024 or hashlib.sha256(raw).hexdigest() != approval.robots_sha256:
        raise ValueError("Robots policy changed; review required")
    return robots_interval(raw, approval.url, AGENT)


def import_reviewed_bytes(approval: PageApproval, raw: bytes, *, retrieved_at: str, robots: bytes):
    from .search import index_document
    validate_robots(approval, robots)
    if not approval.current() or len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != approval.raw_sha256:
        raise ValueError("Expired approval, oversized body or changed content; review required")
    text = raw.decode("utf-8", errors="strict")
    if approval.review_scope == "service_excerpts":
        paragraphs = extract_service_excerpts(text, approval.paragraph_sha256, content_tag=approval.content_tag)
    elif approval.content_type == "text/html":
        paragraphs = extract_html(text, content_tag=approval.content_tag)
    else:
        # Use the same conservative contact-pattern check as the HTML adapter.
        import html
        paragraphs = extract_html("<main>" + html.escape(text).replace("\n", "</p><p>") + "</main>")
    digest = hashlib.sha256("\n\n".join(paragraphs).encode("utf-8")).hexdigest()
    if digest != approval.text_sha256:
        raise ValueError("Extracted text differs from the reviewed content")
    source = Source(approval.source_id, approval.title, tuple(Paragraph(f"p{i}", p) for i,p in enumerate(paragraphs,1)), False, approval.url)
    return index_document(source, approval.category, retrieved_at=retrieved_at, approval_expires=approval.expires_on,
                          raw_sha256=approval.raw_sha256)


class ReviewedFetcher:
    def __init__(self, *, enabled=False, approvals=APPROVED_PAGES, resolver=None,
                 connection_factory=None, rate_gate=None):
        self.enabled, self.approvals = enabled, approvals
        # Accept legacy injection keywords for caller compatibility, but do
        # not retain or invoke any network-capable transport.

    def _get(self, url, content_type, max_bytes, interval):
        # Retain this private method as a compatibility seam, but do not allow
        # direct callers to bypass the disabled public fetch method.
        raise ValueError("Live HTML retrieval disabled: no network access was attempted")

    def fetch(self, source_id):
        # Filtering HTML after download is too late to guarantee that personal
        # information was never acquired or processed. Keep reviewed local
        # catalogs available, but fail closed before DNS or any network call.
        raise ValueError("Live HTML retrieval disabled: use the existing reviewed local catalog")


def save_catalog(documents, path):
    payload = json.dumps({"catalog_version": 1, "documents": [asdict(d) for d in documents]}, ensure_ascii=False, indent=2)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload + "\n")


def load_catalog(path, approvals=APPROVED_PAGES):
    from .search import IndexedDocument, SearchIndex
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Catalog too large")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("catalog_version") != 1 or not isinstance(payload.get("documents"), list):
        raise ValueError("Unsupported catalog")
    docs = []
    for data in payload["documents"]:
        data = dict(data)
        source_data = dict(data.pop("source"))
        approval = approvals.get(source_data.get("id"))
        if not approval or not approval.current():
            raise ValueError("Unapproved/expired indexed document")
        if source_data.get("url") != approval.url or source_data.get("title") != approval.title or source_data.get("synthetic") is not False:
            raise ValueError("Catalog source identity mismatch")
        if data.get("text_sha256") != approval.text_sha256 or data.get("raw_sha256") != approval.raw_sha256 or data.get("category") != approval.category or data.get("approval_expires") != approval.expires_on:
            raise ValueError("Catalog does not match reviewed extraction")
        source_data["paragraphs"] = tuple(Paragraph(**p) for p in source_data["paragraphs"])
        docs.append(IndexedDocument(source=Source(**source_data), **data))
    return SearchIndex(docs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "validate", "import-snapshot", "fetch-reviewed"))
    parser.add_argument("--approvals", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--snapshot", type=Path, help="Legacy option; raw HTML snapshot import is disabled")
    parser.add_argument("--robots-snapshot", type=Path, help="Legacy option; raw HTML snapshot import is disabled")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--retrieved-at", help="Original snapshot retrieval time, ISO-8601 with timezone")
    parser.add_argument("--enable-live", action="store_true", help="Legacy flag; live HTML retrieval remains disabled")
    args = parser.parse_args(argv)
    if args.command == "import-snapshot":
        # A local HTML file can contain personal information too. Parsing it
        # before excerpt filtering would still process that information.
        parser.exit(2, "Raw HTML snapshot import disabled; use the existing reviewed catalog or synthetic fixtures.\n")
    try:
        approvals = load_approvals(args.approvals) if args.approvals else APPROVED_PAGES
        if args.command in ("list", "validate"):
            print(json.dumps({"approved_sources": list(approvals), "live_enabled": False}))
            return 0
        if not args.source_id or args.source_id not in approvals or args.output is None:
            raise ValueError("Explicit approved source ID and new output path required")
        if args.command == "fetch-reviewed":
            doc = ReviewedFetcher(enabled=args.enable_live, approvals=approvals).fetch(args.source_id)
        else:
            if args.snapshot is None:
                raise ValueError("A reviewed snapshot is required")
            with args.snapshot.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if args.retrieved_at is None or args.robots_snapshot is None:
                raise ValueError("Original retrieval timestamp and reviewed robots snapshot are required")
            with args.robots_snapshot.open("rb") as stream:
                robots = stream.read(64 * 1024 + 1)
            doc = import_reviewed_bytes(approvals[args.source_id], raw, retrieved_at=args.retrieved_at, robots=robots)
        save_catalog([doc], args.output)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(2, "Source management failed; verify approval, content and destination.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
