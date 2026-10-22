"""Search-to-workflow integration; never fetches documents on a query."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from .application import WorkflowService
from .categories import CATEGORIES, MENU_REFERENCE, OFFICIAL_HOME
from .schemas import Paragraph, Source
from .search import REAL_SERVICE_QUERY_TERMS, SearchIndex, index_document, tokens, validate_query
from .workflow import run_workflow

DEMO_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portal-synthetic.json"
DEMO_SHA256 = "aece5c40409ebd712abc67705d1d26f77a98cf81d78a1018d1f764094bf968bf"


def demo_index() -> SearchIndex:
    raw = DEMO_FIXTURE.read_bytes()
    if len(raw) > 64 * 1024 or hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != DEMO_SHA256:
        raise ValueError("Synthetic portal fixture needs renewed review")
    data = json.loads(raw.decode("utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("Expected the explicitly synthetic portal fixture")
    docs = []
    for page in data["pages"]:
        source = Source(page["id"], page["title"], tuple(Paragraph(f"p{i}", text) for i,text in enumerate(page["paragraphs"],1)), True)
        docs.append(index_document(source, page["category"]))
    return SearchIndex(docs)


class PortalService:
    def __init__(self, workflow_service: WorkflowService | None = None, *, index: SearchIndex | None = None):
        self.workflow = workflow_service if workflow_service is not None else WorkflowService()
        self.index = index if index is not None else (self.workflow.index if getattr(self.workflow, "real_sources", False) else demo_index())

    def overview(self):
        return {"categories": [{**asdict(c), "count": sum(d.category == c.id and self.index.eligible(d) for d in self.index.documents.values())} for c in CATEGORIES],
                "official_home": OFFICIAL_HOME, "category_reference": MENU_REFERENCE,
                "documents": sum(self.index.eligible(d) for d in self.index.documents.values()),
                "synthetic": all(d.source.synthetic for d in self.index.documents.values()),
                "allowed_query_terms": sorted(REAL_SERVICE_QUERY_TERMS),
                "provider": self.workflow.provider, "coverage": "Kun individuelt gjennomgåtte, indekserte kilder. Ikke fullstendig kommunal dekning."}

    def search(self, query: str, *, category: str | None = None):
        try:
            validate_query(query, real_sources=True)
            hits = self.index.search(query, category=category)
        except ValueError:
            # Never echo or persist rejected free-form portal queries.
            return {"query": "", "category": category, "results": [],
                    "coverage": self.overview()["coverage"], "provider": self.workflow.provider}
        return {"query": "" if getattr(self.workflow, "real_sources", False) else query, "category": category, "results": [h.to_dict() for h in hits],
                "coverage": self.overview()["coverage"], "provider": self.workflow.provider}

    def answer(self, query: str, *, category: str | None = None, workflow_service=None,
               prior_terms=()):
        workflow = workflow_service if workflow_service is not None else self.workflow
        safe_query = "" if getattr(workflow, "real_sources", False) else query
        try:
            allowed_prior = tuple(dict.fromkeys(term for term in prior_terms
                                                if isinstance(term, str) and term in REAL_SERVICE_QUERY_TERMS))
            if len(allowed_prior) > 16:
                raise ValueError("Invalid conversation context")
            terms = validate_query(query, real_sources=True, allow_followup=bool(allowed_prior))
        except ValueError:
            return {"query": "", "answer_status": "input_rejected", "result": None, "citations": [],
                    "message": "Bruk bare generelle temaer om kommunale tjenester. Ikke skriv personopplysninger.",
                    "coverage": self.overview()["coverage"]}
        is_follow_up = not terms and bool(allowed_prior)
        if is_follow_up:
            terms = list(allowed_prior)
            query = " ".join(terms)
        hits = self.index.search(query, category=category, limit=3) if terms else ()
        context_terms = {term for hit in hits for p in hit.document.source.paragraphs if p.id in hit.paragraph_ids for term in tokens(p.text)}
        if not hits or not set(terms).issubset(context_terms):
            return {"query": safe_query, "answer_status": "insufficient_evidence", "result": None, "citations": [],
                    "message": "Vi har ikke tilstrekkelig indeksert kildegrunnlag for dette søket. Prøv et annet søkeord eller kommunens offisielle nettsted.",
                    "coverage": self.overview()["coverage"]}
        paragraphs, citations = [], []
        for hit in hits:
            for paragraph in hit.document.source.paragraphs:
                if paragraph.id in hit.paragraph_ids:
                    id = hit.document.source.id + ":" + paragraph.id
                    paragraphs.append(Paragraph(id, paragraph.text))
                    citations.append({"paragraph_id": id, **hit.document.provenance()})
        source = Source("portal-search-context", "Kildeutdrag for søk: " + query, tuple(paragraphs),
                        all(h.document.source.synthetic for h in hits))
        if not source.synthetic and workflow.provider == "mock":
            return {"query": safe_query, "answer_status": "provider_unavailable", "result": None, "citations": citations,
                    "message": "Kildene kan s\u00f8kes i, men den n\u00e5v\u00e6rende mock-leverand\u00f8ren er bare for syntetiske data. En godkjent modelladapter m\u00e5 kobles til f\u00f8r AI-svar kan lages.",
                    "coverage": self.overview()["coverage"]}
        provider_started = time.perf_counter()
        if not source.synthetic and getattr(workflow, "real_sources", False):
            result = workflow.run_context(source)
        elif source.synthetic:
            result = workflow.run_prepared(source)
        else:
            result = run_workflow(source.id, workflow.summarizer, provider=workflow.provider,
                                  loader=lambda _: source, corrector=workflow.corrector,
                                  allow_non_synthetic=True)
        # The verifier is authoritative for excerpts/findings, never truth.
        data = json.loads(result.to_json())
        status = "review_required" if result.verification.has_findings else ("demo" if result.provider.startswith("mock") else "evidence_checked")
        return {"query": safe_query, "answer_status": status, "result": data, "citations": citations,
                "is_follow_up": is_follow_up,
                "provider_latency_ms": getattr(result, "provider_latency_ms", None) or round((time.perf_counter() - provider_started) * 1000),
                "message": "Kildebasert utdrag med mock, ikke et ekte AI-svar." if result.provider.startswith("mock") else "Kildebasert svar; vurder funn og kildene før bruk.",
                "coverage": self.overview()["coverage"]}
