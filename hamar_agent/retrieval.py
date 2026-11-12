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


class PreparedPublicTransport:
    """Dormant exact-URL transport; no application factory enables it.

    Only an explicitly reviewed full-response plain-text boundary is supported.
    Existing excerpt-only HTML approvals cannot authorize this transport. An
    approval is an administrative decision, never a proof that a changing remote
    response cannot contain personal data. Resolve that policy before activation.
    DNS waits/blocked sockets may outlive callers; use bounded_tool_call outside.
    """
    def __init__(self, approvals, *, authorized=lambda: False, input_authorized=lambda: False,
                 resolver=None, connection_factory=None, clock=None, sleep=None):
        import time
        from threading import Lock
        self.approvals = MappingProxyType(dict(approvals))
        self.authorized, self.input_authorized = authorized, input_authorized
        self.resolver, self.connection_factory = resolver, connection_factory
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.lock, self.next_start = Lock(), 0.

    def _admit(self, approval, owner):
        from .run_control import current_run
        if (not self.authorized() or not self.input_authorized() or current_run() is not owner
                or owner is None or not approval.current()
                or self.approvals.get(approval.source_id) != approval):
            raise RetrievalError('Source access not authorized')
        # Refuse the existing partial-HTML privacy boundary before DNS.
        if approval.content_type != 'text/plain' or approval.review_scope != 'full_document':
            raise RetrievalError('A reviewed full non-personal plain-text response is required')
        _validate_url(approval.url)
        host = urlsplit(approval.url).hostname
        if host.endswith(('.local', '.internal', '.localhost', '.lan', '.home', '.home.arpa')):
            raise RetrievalError('Non-public source host')
        owner.admit_tool('research_transport_admission')

    def _get(self, approval, url, limit, deadline, owner, interval):
        import ipaddress
        import socket
        self._admit(approval, owner)
        if url not in (approval.url,'https://'+urlsplit(approval.url).netloc+'/robots.txt'):
            raise RetrievalError('URL outside exact approval')
        with self.lock:
            wait = max(0., self.next_start-self.clock())
            if wait >= deadline-self.clock():
                raise RetrievalError('Source rate interval exceeds deadline')
            self.next_start = max(self.next_start, self.clock())+interval
        if wait:
            self.sleep(wait)
        self._admit(approval, owner)
        host = urlsplit(url).hostname
        resolver = self.resolver or socket.getaddrinfo
        addresses = resolver(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        if not isinstance(addresses, (list, tuple)) or not 1 <= len(addresses) <= 8:
            raise RetrievalError('Invalid DNS answer')
        # Reject mixed public/private responses rather than choosing one safe IP.
        for family, kind, proto, canonical, address in addresses:
            value = ipaddress.ip_address(address[0])
            if (family not in (socket.AF_INET, socket.AF_INET6) or not value.is_global
                    or value.is_private or value.is_reserved or value.is_loopback or value.is_link_local
                    or value.is_multicast or value.is_unspecified or getattr(value,'is_site_local',False)
                    or getattr(value, 'ipv4_mapped', None) is not None
                    or getattr(value, 'sixtofour', None) is not None or getattr(value, 'teredo', None) is not None
                    or value.version==6 and value in ipaddress.ip_network('64:ff9b::/96')
                    or (family==socket.AF_INET)!=(value.version==4)
                    or address[1] != 443 or kind != socket.SOCK_STREAM):
                raise RetrievalError('Non-public DNS answer')
        timeout = min(10., deadline-self.clock(), owner.remaining())
        if timeout <= 0:
            raise RetrievalError('Source deadline exceeded')
        self._admit(approval, owner)  # DNS/rate waiting may have crossed revocation.
        factory = self.connection_factory or _pinned_public_connection
        connection = factory(host, addresses[0][4][0], timeout)
        try:
            self._admit(approval, owner)
            connection.request('GET', urlsplit(url).path, headers={
                'Accept': 'text/plain', 'Accept-Encoding': 'identity',
                'User-Agent': 'HamarKommuneAgent/0.2', 'Connection': 'close'})
            response = connection.getresponse()
            headers = response.headers
            if (response.status != 200 or headers.get_content_type() != 'text/plain'
                    or len(headers.get_all('Content-Type',[]))!=1
                    or len(headers.get_params())>2
                    or headers.get_content_charset('utf-8').lower() != 'utf-8'
                    or headers.get('Content-Encoding', 'identity').lower() != 'identity'
                    or headers.get('Location') or headers.get('WWW-Authenticate')
                    or re.search(r'\b(?:noindex|none)\b', headers.get('X-Robots-Tag',''), re.I)
                    or sum(len(k)+len(v) for k,v in headers.items()) > 8192):
                raise RetrievalError('Invalid source response')
            lengths = headers.get_all('Content-Length', [])
            transfer=headers.get_all('Transfer-Encoding',[])
            if (len(lengths)>1 or lengths and (not lengths[0].isdigit() or int(lengths[0])>limit)
                    or transfer and (transfer!=['chunked'] or lengths)):
                raise RetrievalError('Invalid source length')
            chunks=[];total=0
            while True:
                self._admit(approval, owner)
                if self.clock()>=deadline:
                    raise RetrievalError('Source deadline exceeded')
                chunk=response.read(min(4096, limit+1-total))
                if not chunk:break
                total+=len(chunk)
                if total>limit:raise RetrievalError('Source body limit exceeded')
                chunks.append(chunk)
            if lengths and total!=int(lengths[0]):
                raise RetrievalError('Source length mismatch')
            return b''.join(chunks), headers.get('Last-Modified')
        finally:
            connection.close()

    def __call__(self, source_id, *, request_id, timeout_seconds, max_bytes):
        from datetime import datetime, timezone
        from .run_control import current_run
        approval=self.approvals.get(source_id);owner=current_run()
        if approval is None or not isinstance(request_id,str) or not re.fullmatch('[0-9a-f]{32}',request_id):
            raise RetrievalError('Invalid source identity')
        self._admit(approval,owner)
        if type(timeout_seconds) not in (int,float) or not 0<timeout_seconds<=10 or type(max_bytes) is not int or not 1<=max_bytes<=MAX_RESPONSE_BYTES:
            raise RetrievalError('Invalid source limits')
        deadline=self.clock()+min(timeout_seconds,owner.remaining())
        try:
            robots_url='https://'+urlsplit(approval.url).netloc+'/robots.txt'
            robots,_=self._get(approval,robots_url,65536,deadline,owner,5.)
            from .robots_policy import robots_interval
            if hashlib.sha256(robots).hexdigest()!=approval.robots_sha256:
                raise RetrievalError('Robots policy changed')
            interval=max(5.,robots_interval(robots,approval.url,'HamarKommuneAgent/0.2'))
            # Reserve the more restrictive policy before the page request.
            with self.lock:
                self.next_start=max(self.next_start,self.clock()+interval)
            body,modified=self._get(approval,approval.url,max_bytes,deadline,owner,interval)
            self._admit(approval,owner)
            return dict(source_id=source_id,url=approval.url,request_id=request_id,body=body,robots=robots,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),status=200,
                        content_type='text/plain',last_modified=modified)
        except RetrievalError:
            raise
        except (OSError,ValueError,HTTPException,UnicodeError):
            raise RetrievalError('Source unavailable or invalid') from None

    def municipal_observer(self, source_id, **limits):
        """Compatible future injection; never selected by a production factory."""
        from .source_updates import PageObservation
        data=self(source_id,**limits);data.pop('retrieved_at')
        return PageObservation(**data)


def _pinned_public_connection(host, address, timeout):
    """Connect to the validated numeric address; TLS verifies the original host."""
    import ipaddress
    import socket
    from http.client import HTTPSConnection
    class Pinned(HTTPSConnection):
        def connect(self):
            if self._tunnel_host:
                raise RetrievalError('Tunnelling is not permitted')
            family=socket.AF_INET6 if ipaddress.ip_address(address).version==6 else socket.AF_INET
            raw=socket.socket(family,socket.SOCK_STREAM)
            try:
                raw.settimeout(self.timeout)
                raw.connect((address,443))
                self.sock=self._context.wrap_socket(raw,server_hostname=host)
            except BaseException:
                raw.close();raise
    return Pinned(host,port=443,timeout=timeout,context=ssl.create_default_context())
