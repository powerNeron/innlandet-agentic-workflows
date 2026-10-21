"""Reviewed HTML/text ingestion. Empty defaults; no discovery, login or crawling."""
import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from threading import Lock
import time
from types import MappingProxyType
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .categories import CATEGORY_IDS
from .html_extract import extract_html
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

    def __post_init__(self):
        for name in ("source_id", "url", "title", "category", "reviewed_on", "expires_on", "raw_sha256", "text_sha256", "robots_sha256", "rationale", "content_type", "content_tag"):
            if not isinstance(getattr(self, name), str):
                raise ValueError("Approval text fields must be strings")
        validate_page_url(self.url)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", self.source_id):
            raise ValueError("Invalid source ID")
        if not self.title.strip() or not self.rationale.strip() or self.no_personal_data is not True:
            raise ValueError("Explicit non-personal full-document review and rationale required")
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
    policy = RobotFileParser()
    policy.parse(raw.decode("utf-8", errors="strict").splitlines())
    if not policy.can_fetch(AGENT, approval.url):
        raise ValueError("robots.txt disallows this source")
    interval = max(2, policy.crawl_delay(AGENT) or 0)
    rate = policy.request_rate(AGENT)
    if rate:
        if rate.requests <= 0:
            raise ValueError("Invalid robots rate policy")
        interval = max(interval, rate.seconds / rate.requests)
    if interval > 60:
        raise ValueError("Robots rate policy requires a separate scheduling decision")
    return interval


def import_reviewed_bytes(approval: PageApproval, raw: bytes, *, retrieved_at: str, robots: bytes):
    from .search import index_document
    validate_robots(approval, robots)
    if not approval.current() or len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != approval.raw_sha256:
        raise ValueError("Expired approval, oversized body or changed content; review required")
    text = raw.decode("utf-8", errors="strict")
    if approval.content_type == "text/html":
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


class RateGate:
    def __init__(self, *, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self.last = None
        self.lock = Lock()

    def wait(self, interval):
        with self.lock:
            if self.last is not None:
                self.sleep(max(0, self.last + interval - self.clock()))
            self.last = self.clock()


_RATE = RateGate()


def public_addresses(host):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("DNS returned a private/reserved address; request refused")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=10, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Pin the already validated address while validating the original hostname.
        sock = socket.create_connection((self.address, 443), timeout=10)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class ReviewedFetcher:
    def __init__(self, *, enabled=False, approvals=APPROVED_PAGES, resolver=public_addresses,
                 connection_factory=PinnedHTTPSConnection, rate_gate=_RATE):
        self.enabled, self.approvals = enabled, approvals
        self.resolver, self.connection_factory, self.rate_gate = resolver, connection_factory, rate_gate

    def _get(self, url, content_type, max_bytes, interval):
        parts = validate_page_url(url)
        addresses = self.resolver(parts.hostname)
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("Non-public address refused")
        self.rate_gate.wait(interval)
        connection = self.connection_factory(parts.hostname, addresses[0])
        try:
            connection.request("GET", parts.path, headers={"User-Agent": AGENT, "Accept": content_type, "Accept-Encoding": "identity"})
            response = connection.getresponse()
            try:
                if response.status != 200:
                    raise ValueError("Expected public HTTP 200; redirects/authentication/errors refused")
                if len(response.headers.get_all("Content-Type", [])) != 1 or response.headers.get_content_type() != content_type:
                    raise ValueError("Unexpected content type")
                if response.headers.get_content_charset() not in (None, "utf-8") or sum(key.lower() == "charset" for key,_ in response.headers.get_params()) > 1:
                    raise ValueError("Only unambiguous UTF-8 documents are allowed")
                if parts.path != "/robots.txt" and re.search(r"noindex|none", ",".join(response.headers.get_all("X-Robots-Tag", [])), re.I):
                    raise ValueError("Source requests exclusion from indexing")
                encodings = response.headers.get_all("Content-Encoding", [])
                if len(encodings) > 1 or encodings and encodings[0].strip().lower() != "identity":
                    raise ValueError("Compressed/ambiguous encoding refused")
                if response.headers.get("Transfer-Encoding") and response.headers.get("Content-Length"):
                    raise ValueError("Ambiguous response framing")
                lengths = response.headers.get_all("Content-Length", [])
                if len(lengths) > 1 or lengths and (not re.fullmatch(r"[0-9]{1,12}", lengths[0]) or int(lengths[0]) > max_bytes):
                    raise ValueError("Invalid/oversized content length")
                chunks, total = [], 0
                while True:
                    chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Response size limit exceeded")
                    chunks.append(chunk)
                if lengths and total != int(lengths[0]):
                    raise ValueError("Truncated/inconsistent response")
                return b"".join(chunks)
            finally:
                response.close()
        finally:
            connection.close()

    def fetch(self, source_id):
        if not self.enabled or source_id not in self.approvals:
            raise ValueError("Live retrieval is disabled or source is unapproved")
        approval = self.approvals[source_id]
        if approval.source_id != source_id or not approval.current():
            raise ValueError("Source approval is not current")
        try:
            robots = self._get("https://" + HOST + "/robots.txt", "text/plain", 64 * 1024, 2)
            interval = validate_robots(approval, robots)
            raw = self._get(approval.url, approval.content_type, MAX_BYTES, interval)
            return import_reviewed_bytes(approval, raw, retrieved_at=datetime.now(timezone.utc).isoformat(), robots=robots)
        except (OSError, http.client.HTTPException, UnicodeError) as exc:
            raise ValueError("Approved retrieval failed; no document indexed") from None


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
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--robots-snapshot", type=Path, help="Reviewed robots.txt used for the original acquisition")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--retrieved-at", help="Original snapshot retrieval time, ISO-8601 with timezone")
    parser.add_argument("--enable-live", action="store_true")
    args = parser.parse_args(argv)
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
