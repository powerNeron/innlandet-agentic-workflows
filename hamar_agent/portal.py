"""Search-to-workflow integration; never fetches documents on a query."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import time

from .application import WorkflowService
from .categories import CATEGORIES, MENU_REFERENCE, OFFICIAL_HOME
from .schemas import Paragraph, Source
from .search import (FOLLOWUP_MODIFIERS, QUERY_ALIASES, REAL_SERVICE_QUERY_TERMS, STOPWORDS,
                     InvalidQueryError, QueryPrivacyError, SearchIndex, UnsupportedTopicError,
                     index_document, tokens, validate_query)
from .workflow import run_workflow

DEMO_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portal-synthetic.json"
DEMO_SHA256 = "aece5c40409ebd712abc67705d1d26f77a98cf81d78a1018d1f764094bf968bf"

_PRICE_REQUEST_TERMS = frozenset({"koster", "pris", "priser", "prisen", "avgift", "gebyr", "gebyrer"})
_PRICE_AMOUNT = re.compile(r"(?:\b\d[\d., ]*\s*(?:kr(?:oner)?|,-)(?!\w)|\b(?:kr|kroner)\s*\d)", re.I)
_APPLICATION_STEPS = re.compile(
    r"\b(?:s[oø]k(?:nad)?\s+(?:via|p[åa]|gjennom)|s[oø]knad(?:en)?\s+(?:sendes|leveres)|"
    r"send\s+(?:inn\s+)?s[oø]knad|s[oø]knadsskjema)\b", re.I
)


def _asks_how_to_apply(query: str) -> bool:
    words = set(tokens(query))
    # "Hva kan jeg bygge uten å søke?" asks what is exempt, not how to submit an application.
    return "uten" not in words and "hvordan" in words and bool(words & {"soker", "soke", "soknad", "soknader"})


def _asks_for_price(query: str) -> bool:
    return bool(set(tokens(query)) & _PRICE_REQUEST_TERMS)


def _asks_library_loans(query: str) -> bool:
    folded = query.casefold().replace("å", "a")
    return bool(re.search(r"\b(?:lane|laner|lant|utlan)\b", folded))


def _citation_records(hits):
    return [{"paragraph_id": hit.document.source.id + ":" + paragraph.id,
             **hit.document.provenance()}
            for hit in hits for paragraph in hit.document.source.paragraphs
            if paragraph.id in hit.paragraph_ids]


def demo_index() -> SearchIndex:
    raw = DEMO_FIXTURE.read_bytes()
    if len(raw) > 64 * 1024 or hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != DEMO_SHA256:
        raise ValueError("Synthetic portal fixture needs renewed review")
    data = json.loads(raw.decode("utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("Expected the explicitly synthetic portal fixture")
    docs = []
    for page in data["pages"]:
        source = Source(page["id"], page["title"], tuple(Paragraph(f"p{i}", text) for i, text in enumerate(page["paragraphs"], 1)), True)
        docs.append(index_document(source, page["category"]))
    return SearchIndex(docs)


class PortalService:
    def __init__(self, workflow_service: WorkflowService | None = None, *, index: SearchIndex | None = None):
        self.workflow = workflow_service if workflow_service is not None else WorkflowService()
        self.index = index if index is not None else (self.workflow.index if getattr(self.workflow, "real_sources", False) else demo_index())

    def overview(self):
        return {
            "categories": [{**asdict(c), "count": sum(d.category == c.id and self.index.eligible(d) for d in self.index.documents.values())} for c in CATEGORIES],
            "official_home": OFFICIAL_HOME,
            "category_reference": MENU_REFERENCE,
            "query_contract_version": 1,
            "documents": sum(self.index.eligible(d) for d in self.index.documents.values()),
            "synthetic": all(d.source.synthetic for d in self.index.documents.values()),
            "allowed_query_terms": sorted(REAL_SERVICE_QUERY_TERMS),
            "query_stopwords": sorted(STOPWORDS),
            "query_followup_modifiers": sorted(FOLLOWUP_MODIFIERS),
            "query_aliases": QUERY_ALIASES,
            "provider": self.workflow.provider,
            "coverage": "Kun individuelt gjennomgåtte, indekserte kilder. Ikke fullstendig kommunal dekning.",
        }

    def search(self, query: str, *, category: str | None = None):
        try:
            validate_query(query, real_sources=True)
            hits = self.index.search(query, category=category)
        except (QueryPrivacyError, InvalidQueryError):
            return {"query": "", "category": category, "results": [], "query_status": "input_rejected",
                    "message": "Søket ble avvist av hensyn til personvernet.",
                    "coverage": self.overview()["coverage"], "provider": self.workflow.provider}
        except UnsupportedTopicError:
            return {"query": "", "category": category, "results": [], "query_status": "unsupported_topic",
                    "message": "Jeg finner ikke et godkjent kommunalt tema i dette søket.",
                    "official_menu_url": MENU_REFERENCE,
                    "coverage": self.overview()["coverage"], "provider": self.workflow.provider}
        result = {"query": "" if getattr(self.workflow, "real_sources", False) else query,
                  "category": category, "results": [h.to_dict() for h in hits],
                  "coverage": self.overview()["coverage"], "provider": self.workflow.provider}
        if not hits:
            result.update(query_status="no_results", official_menu_url=MENU_REFERENCE)
        return result

    def answer(self, query: str, *, category: str | None = None, workflow_service=None,
               prior_terms=()):
        workflow = workflow_service if workflow_service is not None else self.workflow
        safe_query = "" if getattr(workflow, "real_sources", False) else query
        try:
            allowed_prior = tuple(dict.fromkeys(term for term in prior_terms
                                                if isinstance(term, str) and term in REAL_SERVICE_QUERY_TERMS))
            if len(allowed_prior) > 16:
                raise InvalidQueryError("Invalid conversation context")
            terms = validate_query(query, real_sources=True, allow_followup=bool(allowed_prior))
        except QueryPrivacyError:
            return {"query": "", "answer_status": "input_rejected", "result": None, "citations": [],
                    "message": "Forespørselen ble avvist av hensyn til personvernet. Ikke skriv personopplysninger.",
                    "coverage": self.overview()["coverage"]}
        except InvalidQueryError:
            return {"query": "", "answer_status": "input_rejected", "result": None, "citations": [],
                    "message": "Skriv et kort spørsmål uten kontrolltegn.",
                    "coverage": self.overview()["coverage"]}
        except UnsupportedTopicError:
            return {"query": "", "answer_status": "clarification_required", "result": None, "citations": [],
                    "message": "Jeg er usikker på hvilken kommunal tjeneste du mener. Prøv et tema som skole, byggesak, vann eller bibliotek.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        is_follow_up = not terms and bool(allowed_prior)
        if not terms and not is_follow_up:
            return {"query": safe_query, "answer_status": "clarification_required", "result": None, "citations": [],
                    "message": "Skriv gjerne hvilken kommunal tjeneste spørsmålet gjelder.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        if is_follow_up:
            terms = list(allowed_prior)
            query = " ".join(terms)
        hits = self.index.search(query, category=category, limit=3) if terms else ()
        context_terms = {term for hit in hits for p in hit.document.source.paragraphs
                         if p.id in hit.paragraph_ids for term in tokens(p.text)}
        citations = _citation_records(hits)
        if not hits or not set(terms).issubset(context_terms):
            return {"query": safe_query, "answer_status": "insufficient_evidence", "result": None, "citations": citations,
                    "message": "Vi har ikke tilstrekkelig indeksert kildegrunnlag for dette søket.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        if "bibliotek" in terms and _asks_library_loans(query):
            return {"query": safe_query, "answer_status": "insufficient_evidence", "result": None,
                    "citations": citations,
                    "message": "De gjennomgåtte bibliotekkildene beskriver ikke hvilke materialer du kan låne.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        selected_paragraphs = [paragraph for hit in hits for paragraph in hit.document.source.paragraphs
                               if paragraph.id in hit.paragraph_ids]
        if _asks_how_to_apply(query) and not any(_APPLICATION_STEPS.search(p.text) for p in selected_paragraphs):
            return {"query": safe_query, "answer_status": "insufficient_evidence", "result": None,
                    "citations": citations,
                    "message": "De gjennomgåtte utdragene forklarer ikke hvordan du sender en søknad.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        if _asks_for_price(query) and not any(_PRICE_AMOUNT.search(p.text) for p in selected_paragraphs):
            return {"query": safe_query, "answer_status": "insufficient_evidence", "result": None,
                    "citations": citations,
                    "message": "Det gjennomgåtte kildeutdraget oppgir ikke et konkret beløp. Jeg kan derfor ikke oppgi en pris.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
        paragraphs = []
        for hit in hits:
            for paragraph in hit.document.source.paragraphs:
                if paragraph.id in hit.paragraph_ids:
                    identifier = hit.document.source.id + ":" + paragraph.id
                    paragraphs.append(Paragraph(identifier, paragraph.text))
        source = Source("portal-search-context", "Kildeutdrag for søk: " + query, tuple(paragraphs),
                        all(hit.document.source.synthetic for hit in hits))
        if not source.synthetic and workflow.provider == "mock":
            return {"query": safe_query, "answer_status": "provider_unavailable", "result": None, "citations": citations,
                    "message": "Kildene kan søkes i, men mock-leverandøren er bare for syntetiske data. Koble til en godkjent modelladapter før AI-svar kan lages.",
                    "official_menu_url": MENU_REFERENCE, "coverage": self.overview()["coverage"]}
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
