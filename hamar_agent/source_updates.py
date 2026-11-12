"""Human-reviewed proposals and request-private source observation staging.

Raw municipal HTML acquisition is intentionally unavailable under the current
source policy. This module compares reviewer-prepared plain-text excerpts to the
approved local catalog and writes a separate, non-authoritative proposal report.
Request-bound staging accepts injected synthetic observations for offline tests;
the production HTML acquisition path remains disabled. It never renews approval.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from types import SimpleNamespace
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from threading import RLock
from contextlib import contextmanager
import uuid

from .html_extract import privacy_check
from .portal_sources import PageApproval, import_reviewed_bytes, validate_page_url, MAX_BYTES
from .search import SearchIndex, RequestIndexedDocument
from .run_control import current_run, bounded_tool_call, checkpoint

MAX_CANDIDATE_BYTES = 64 * 1024
MAX_PARAGRAPHS = 80


class SourceRefreshError(ValueError):
    """Only controlled codes, never response text or external diagnostics."""
    def __init__(self, code='source_unavailable'):
        self.code = code
        super().__init__('Source observation was not admitted')


@dataclass(frozen=True)
class PageObservation:
    source_id: str
    url: str
    request_id: str
    body: bytes
    robots: bytes
    status: int = 200
    content_type: str = 'text/html'
    published_at: str | None = None
    last_modified: str | None = None


class RequestSearchIndex(SearchIndex):
    """An admitted request corpus cannot use historical eligibility exceptions."""
    binding = None

    def eligible(self, doc):
        return (isinstance(doc, RequestIndexedDocument)
                and date.fromisoformat(doc.approval_expires) >= date.today())

    def search(self, *args, **kwargs):
        if self.binding is None:
            raise SourceRefreshError('source_snapshot_incomplete')
        self.binding.assert_publishable()
        return super().search(*args, **kwargs)


class SourceSnapshot:
    """Capability bound to a live RunState, not a reusable date/freshness flag."""
    def __init__(self, index, owner, source_policy, revision, request_id, started, completed, byte_count, approvals):
        self.index, self.owner, self.source_policy = index, owner, source_policy
        self.revision, self.request_id = revision, request_id
        self.started_at, self.completed_at, self.byte_count = started, completed, byte_count
        self.fingerprint = self._fingerprint()
        self.approval_fingerprints={key:hashlib.sha256(json.dumps(asdict(approvals[key]),sort_keys=True).encode()).hexdigest()
                                   for key in index.documents}

    def _fingerprint(self):
        return hashlib.sha256(json.dumps([asdict(doc) for doc in self.index.documents.values()],
            ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()

    def assert_publishable(self):
        if current_run() is not self.owner or self.owner.finished or self.owner.stopped:
            raise SourceRefreshError('source_request_mismatch')
        self.owner.checkpoint('request_source_binding')
        with self.source_policy.lock:
            if self.source_policy.revoked or self.source_policy.revision != self.revision:
                raise SourceRefreshError('source_approval_required')
            for source_id in self.index.documents:
                approval = self.source_policy.approvals[source_id]
                doc=self.index.documents[source_id]
                fingerprint=hashlib.sha256(json.dumps(asdict(approval),sort_keys=True).encode()).hexdigest()
                if not approval.current() or fingerprint!=self.approval_fingerprints[source_id]:
                    raise SourceRefreshError('source_approval_required')
                if (doc.raw_sha256!=approval.raw_sha256 or doc.text_sha256!=approval.text_sha256
                        or doc.source.url!=approval.url or doc.source.title!=approval.title
                        or doc.category!=approval.category or doc.approval_expires!=approval.expires_on):
                    raise SourceRefreshError('source_approval_required')
        if self._fingerprint() != self.fingerprint:
            raise SourceRefreshError('source_snapshot_modified')

    @contextmanager
    def publication_guard(self):
        # Revocation and publication have a common linearization lock.
        with self.source_policy.lock:
            self.assert_publishable()
            yield

    def receipt(self):
        self.assert_publishable()
        return {'policy': 'request_bound', 'request_id': self.request_id,
                'started_at': self.started_at, 'completed_at': self.completed_at,
                'sources': len(self.index.documents), 'source_attempts': len(self.index.documents),
                'received_bytes': self.byte_count, 'corpus_sha256': self.fingerprint,
                'observation_method': self.source_policy.observation_method}


class BoundPortalResult(dict):
    """JSON-compatible output with a non-serialized publication capability."""
    def __init__(self, value, binding):
        super().__init__(value)
        self.binding = binding

    def assert_publishable(self):
        self.binding.assert_publishable()

    def publication_guard(self):
        return self.binding.publication_guard()


class BoundWorkflowResult:
    def __init__(self, value, binding):
        self.value, self.binding = value, binding

    def __getattr__(self, name):
        return getattr(self.value, name)

    def assert_publishable(self):
        self.binding.assert_publishable()

    def publication_guard(self):
        return self.binding.publication_guard()


class RequestBoundSources:
    """Stage a complete index or fail; never change a shared index/catalog.

    Injected fetcher is a trusted testing seam, not an HTTP/query parameter.
    Actual official HTML fetch stays fail-closed pending separate access/privacy
    approval and an independently verified permitted transport.
    """
    def __init__(self, approvals, *, fetcher=None, max_sources=8, max_total_bytes=4*1024*1024,
                 timeout_seconds=10, observation_method='disabled_production_transport'):
        from types import MappingProxyType
        if type(max_sources) is not int or not 1 <= max_sources <= 8:
            raise ValueError('Invalid source count budget')
        if type(max_total_bytes) is not int or not 1 <= max_total_bytes <= 4*1024*1024:
            raise ValueError('Invalid source byte budget')
        if type(timeout_seconds) not in (int,float) or not 0 < timeout_seconds <= 10:
            raise ValueError('Invalid source timeout')
        self.approvals = MappingProxyType(dict(approvals))
        if any(not isinstance(a,PageApproval) or key != a.source_id for key,a in self.approvals.items()):
            raise ValueError('Exact page approvals required')
        if len({a.url for a in self.approvals.values()}) != len(self.approvals):
            raise ValueError('Duplicate approved URL')
        self.fetcher = fetcher
        self.max_sources, self.max_total_bytes, self.timeout_seconds = max_sources,max_total_bytes,timeout_seconds
        self.observation_method = observation_method
        self.lock = RLock(); self.revision = 0; self.revoked = False

    @classmethod
    def from_manifest(cls, path):
        # Read identities only. Never load the historical catalog or invoke its
        # special eligibility exceptions in production. Expiry is checked BEFORE
        # every observation and again before publication; it is never extended.
        with Path(path).open('rb') as stream:
            raw=stream.read(65537)
        if len(raw)>65536:
            raise ValueError('Approval manifest too large')
        def unique_fields(pairs):
            value={}
            for key,item in pairs:
                if key in value:raise ValueError('Duplicate approval field')
                value[key]=item
            return value
        rows=json.loads(raw,object_pairs_hook=unique_fields)
        if not isinstance(rows,list) or len(rows)>8:
            raise ValueError('Bounded approval list required')
        approvals={}
        for row in rows:
            approval=PageApproval(**row)
            if approval.source_id in approvals:
                raise ValueError('Duplicate approval')
            approvals[approval.source_id]=approval
        return cls(approvals)

    def revoke(self):
        with self.lock:
            self.revoked = True; self.revision += 1

    def retrieve(self, source_ids=None):
        owner = current_run()
        if owner is None or owner.finished or owner.stopped:
            raise SourceRefreshError('source_request_mismatch')
        checkpoint('source_admission')
        ids = tuple(self.approvals) if source_ids is None else tuple(source_ids)
        if not ids:
            raise SourceRefreshError('source_approval_required')
        if len(ids)>self.max_sources or len(set(ids))!=len(ids):
            raise SourceRefreshError('source_budget_exhausted')
        with self.lock:
            if self.revoked:
                raise SourceRefreshError('source_approval_required')
            revision = self.revision
            for source_id in ids:
                approval = self.approvals.get(source_id)
                if approval is None or not approval.current():
                    raise SourceRefreshError('source_approval_required')
                validate_page_url(approval.url)
            batch_approvals={key:self.approvals[key] for key in ids}
        request_id=uuid.uuid4().hex
        started=datetime.now(timezone.utc).isoformat(); staged=[]; total=0
        if self.fetcher is None:
            raise SourceRefreshError('source_access_not_authorized')
        for source_id in ids:
            checkpoint('source_observation')
            approval=batch_approvals[source_id]
            timeout=min(self.timeout_seconds,owner.remaining())
            fetcher=self.fetcher
            def observe(source_id=source_id,approval=approval,fetcher=fetcher,timeout=timeout):
                # Dispatch admission linearizes under policy and run locks.
                # Release both before transport: already-admitted work may be
                # residual, while queued/new work must respect revocation.
                with self.lock:
                    if (self.revoked or self.revision!=revision
                            or self.approvals.get(source_id)!=approval or not approval.current()):
                        raise SourceRefreshError('source_approval_required')
                    if current_run() is not owner:
                        raise SourceRefreshError('source_request_mismatch')
                    owner.admit_tool('source_policy_admitted')
                return fetcher(source_id,request_id=request_id,timeout_seconds=timeout,max_bytes=MAX_BYTES)
            try:
                observation=bounded_tool_call(observe,timeout_seconds=timeout)
            except SourceRefreshError:
                raise
            except (OSError,TimeoutError):
                raise SourceRefreshError('source_unavailable') from None
            except ValueError:
                raise SourceRefreshError('source_access_not_authorized') from None
            if (not isinstance(observation,PageObservation) or observation.source_id!=source_id
                    or observation.request_id!=request_id or observation.url!=approval.url
                    or type(observation.status) is not int or observation.status!=200
                    or observation.content_type!=approval.content_type):
                raise SourceRefreshError('source_response_invalid')
            if not isinstance(observation.body,bytes) or not isinstance(observation.robots,bytes):
                raise SourceRefreshError('source_response_invalid')
            total+=len(observation.body)+len(observation.robots)
            if len(observation.body)>MAX_BYTES or len(observation.robots)>65536 or total>self.max_total_bytes:
                raise SourceRefreshError('source_budget_exhausted')
            retrieved=datetime.now(timezone.utc).isoformat()
            try:
                doc=import_reviewed_bytes(approval,observation.body,retrieved_at=retrieved,robots=observation.robots)
                modified=observation.last_modified
                if modified is not None:
                    value=parsedate_to_datetime(modified)
                    if value.tzinfo is None:
                        raise ValueError('Last-Modified timezone required')
                    modified=value.astimezone(timezone.utc).isoformat()
                fields={k:v for k,v in asdict(doc).items() if k!='source'}
                staged.append(RequestIndexedDocument(source=doc.source,**fields,retrieval_request_id=request_id,
                    published_at=observation.published_at,last_modified=modified))
            except (ValueError,TypeError,AttributeError,OverflowError):
                raise SourceRefreshError('source_changed_review_required') from None
        # Atomic admission: no index is exposed until every observation validates.
        index=RequestSearchIndex(staged)
        binding=SourceSnapshot(index,owner,self,revision,request_id,started,
                               datetime.now(timezone.utc).isoformat(),total,batch_approvals)
        index.binding=binding
        binding.assert_publishable()
        checkpoint('source_snapshot_ready')
        return binding


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
