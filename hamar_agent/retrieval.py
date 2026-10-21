"""Isolated, approval-only HTTP transport. Production approvals are empty."""
from dataclasses import dataclass
from datetime import date
import hashlib
from http.client import HTTPException
import re
import ssl
from types import MappingProxyType
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener,
)

TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 512 * 1024


class RetrievalError(ValueError):
    """Sanitized transport/approval error; never includes response body text."""


def _validate_url(url: str) -> None:
    if not isinstance(url, str) or not url.isascii():
        raise ValueError("approval URL must be ASCII HTTPS")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("approval URL contains whitespace or controls")
    if any(c in url for c in ("\\", "?", "#")):
        raise ValueError("approval URL must not contain backslashes, queries or fragments")
    parts = urlsplit(url)
    if parts.scheme != "https" or not url.startswith("https://"):
        raise ValueError("approval URL must use HTTPS")
    # Deliberately narrow DNS syntax; no credentials, ports or IP literals.
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+", parts.netloc):
        raise ValueError("approval URL requires a lowercase DNS hostname without credentials or ports")
    if all(label.isdigit() for label in parts.netloc.split(".")):
        raise ValueError("IP literals are not accepted")
    if not parts.path.startswith("/"):
        raise ValueError("approval URL must specify an explicit path")
    if any(segment in (".", "..") for segment in parts.path.split("/")):
        raise ValueError("approval URL must not contain relative path segments")


@dataclass(frozen=True)
class HttpApproval:
    source_id: str
    url: str
    rationale: str
    reviewed_on: date
    expires_on: date
    sha256: str | None = None

    def __post_init__(self) -> None:
        for value in (self.source_id, self.rationale):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("approval ID and rationale must be non-empty text")
        _validate_url(self.url)
        if type(self.reviewed_on) is not date or type(self.expires_on) is not date:
            raise ValueError("approval dates must be dates")
        if self.expires_on < self.reviewed_on:
            raise ValueError("approval expiry precedes review")
        if self.sha256 is not None and (
            not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)
        ):
            raise ValueError("SHA-256 must be 64 lowercase hex characters")


# No real municipal source is approved. No CLI or workflow calls this module.
HTTP_APPROVALS: Mapping[str, HttpApproval] = MappingProxyType({})


@dataclass(frozen=True)
class RetrievedDocument:
    source_id: str
    url: str
    text: str
    sha256: str


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def fetch_document(
    source_id: str, *, registry: Mapping[str, HttpApproval] = HTTP_APPROVALS,
    today: date | None = None,
) -> RetrievedDocument:
    """Fetch only a trusted registry entry; injected registries are for offline tests.

    Socket timeout is not an overall deadline. A digest checks integrity only;
    reading and rejecting a body cannot guarantee no personal data was received.
    """
    approval = registry.get(source_id)
    if not isinstance(approval, HttpApproval) or approval.source_id != source_id:
        raise RetrievalError("source is not approved")
    current = today if today is not None else date.today()
    if not approval.reviewed_on <= current <= approval.expires_on:
        raise RetrievalError("source approval is not current")
    _validate_url(approval.url)
    # Explicit opener: no environment proxies, cookies, auth handlers or retries.
    opener = build_opener(
        ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _RejectRedirects(),
    )
    request = Request(approval.url, headers={
        "Accept": "text/plain", "Accept-Encoding": "identity",
        "User-Agent": "HamarKommuneAgent-course-prototype/0.1",
    }, method="GET")
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != approval.url:
                raise RetrievalError("unexpected HTTP status or response URL")
            headers = response.headers
            types = headers.get_all("Content-Type", [])
            if len(types) != 1 or headers.get_content_type() != "text/plain":
                raise RetrievalError("expected text/plain content type")
            params = headers.get_params() or []
            if sum(key.lower() == "charset" for key, _ in params) != 1 or headers.get_content_charset() != "utf-8":
                raise RetrievalError("expected explicit UTF-8 charset")
            encodings = headers.get_all("Content-Encoding", [])
            if encodings and (len(encodings) != 1 or encodings[0].strip().lower() != "identity"):
                raise RetrievalError("compressed responses are not accepted")
            lengths = headers.get_all("Content-Length", [])
            expected_length = None
            if lengths:
                if len(lengths) != 1 or len(lengths[0]) > 20 or not re.fullmatch(r"[0-9]+", lengths[0]):
                    raise RetrievalError("invalid content length")
                expected_length = int(lengths[0])
                if expected_length > MAX_RESPONSE_BYTES:
                    raise RetrievalError("response exceeds size limit")
            chunks = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, MAX_RESPONSE_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise RetrievalError("response exceeds size limit")
                chunks.append(chunk)
            if expected_length is not None and total != expected_length:
                raise RetrievalError("response length does not match header")
            raw = b"".join(chunks)
            digest = hashlib.sha256(raw).hexdigest()
            if approval.sha256 is not None and digest != approval.sha256:
                raise RetrievalError("response integrity check failed")
            text = raw.decode("utf-8", errors="strict")
            return RetrievedDocument(source_id, approval.url, text, digest)
    except HTTPError as exc:
        exc.close()
        raise RetrievalError("HTTP request rejected") from None
    except (URLError, OSError, UnicodeError, HTTPException):
        raise RetrievalError("network, TLS or UTF-8 decoding failure") from None
