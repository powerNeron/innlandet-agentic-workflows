"""Shared application service for CLI and local web routes."""
from collections.abc import Callable, Mapping

from .schemas import Paragraph, Source
from .sources import APPROVED_SOURCES, load_source
from .retrieval import HTTP_APPROVALS, HttpApproval, fetch_document
from .summarize import MockSummarizer, Summarizer
from .workflow import CorrectionCallback, WorkflowResult, run_workflow


class WorkflowService:
    """Trusted startup configuration, never supplied by web request bodies."""

    def __init__(self, *, summarizer: Summarizer | None = None, provider: str = "mock",
                 corrector: CorrectionCallback | None = None, enable_http: bool = False,
                 http_registry: Mapping[str, HttpApproval] = HTTP_APPROVALS,
                 fixture_loader: Callable[[str], Source] = load_source) -> None:
        self.summarizer = summarizer if summarizer is not None else MockSummarizer()
        self.provider = provider
        self.corrector = corrector
        self.enable_http = enable_http
        self.http_registry = http_registry
        self.fixture_loader = fixture_loader

    def sources(self) -> list[dict[str, str]]:
        entries = [{"id": key, "label": key, "kind": "synthetic fixture"} for key in APPROVED_SOURCES]
        if self.enable_http:
            entries.extend({"id": key, "label": key, "kind": "approved HTTP document"}
                           for key in self.http_registry if key not in APPROVED_SOURCES)
        return entries

    def load(self, source_id: str) -> Source:
        if source_id in APPROVED_SOURCES:
            return self.fixture_loader(source_id)
        if not self.enable_http:
            raise ValueError("source is not approved; external retrieval is disabled")
        # Transport still checks explicit URL, approval dates, TLS, redirects and limits.
        document = fetch_document(source_id, registry=self.http_registry)
        paragraphs = tuple(Paragraph(f"p{i}", part.strip()) for i, part in
                           enumerate(document.text.split("\n\n"), 1) if part.strip())
        return Source(document.source_id, document.source_id, paragraphs, False, document.url)

    def run(self, source_id: str) -> WorkflowResult:
        return run_workflow(source_id, self.summarizer, provider=self.provider,
                            loader=self.load, corrector=self.corrector,
                            allow_non_synthetic=self.enable_http)

    def run_prepared(self, source: Source) -> WorkflowResult:
        # CLI path input has already passed the guarded fixture loader.
        return run_workflow(source.id, self.summarizer, provider=self.provider,
                            loader=lambda _: source, corrector=self.corrector)
