"""Bounded in-memory inverted full-text index over reviewed documents."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import math
import re
import unicodedata

from .categories import CATEGORY_IDS
from .schemas import Source
from .historical_sources import retained_document, HISTORICAL_WARNING

STOPWORDS = frozenset({"og", "i", "er", "en", "et", "det", "den", "for", "til", "av", "om", "hva", "hvordan", "hvor", "kan", "jeg", "med",
             "soker", "soke", "gjelder", "koster", "trenger", "finn", "finne", "finner", "informasjon",
             "hvem", "far", "fa", "tid", "de", "yngste", "elevene", "tilbud",
             "fungerer", "elever", "hamar", "uten", "soknad", "soknader", "a", "å", "ma", "pa", "som"})
STOPWORDS = STOPWORDS | frozenset({"kommer", "fra"})
QUERY_ALIASES = {
    "garasje": "bygge", "garasjen": "bygge", "garasjer": "bygge",
    "parkere": "parkering", "parkerer": "parkering", "parkeringen": "parkering",
    "parkeringsplass": "parkering", "parkeringsplasser": "parkering",
    "drikkevannet": "drikkevann", "vannforsyning": "vann", "vannforsyningen": "vann",
    "biblioteket": "bibliotek", "bibliotekets": "bibliotek", "lane": "bibliotek",
    "kommuneplanen": "kommuneplan", "kommuneplanens": "kommuneplan",
    "byggesak": "bygge", "byggetillatelse": "bygge", "byggetillatelsen": "bygge",
    "byggesøknad": "bygge", "byggesoknad": "bygge",
}
FOLLOWUP_MODIFIERS = frozenset({"pris", "priser", "prisen", "vilkar", "frister", "krav", "mer", "videre", "ogsa"})
# Live search accepts only broad, reviewed service topics. Personal data is
# detected separately; an unrecognized safe topic never reaches the model.
REAL_SERVICE_QUERY_TERMS = frozenset({
    "barnehage", "bibliotek", "bolig", "byggesak", "bygge", "drikkevann", "familie",
    "folkehelse", "gratis", "helse", "kommuneplan", "kultur", "luftkvalitet",
    "miljo", "miljø", "oppvekst", "parkering", "plan", "planer", "politikk",
    "service", "skole", "skolefritidsordning", "sfo", "sosial", "teknisk", "trinn", "vann",
    "vanntrykk", "water", "veg", "vei", "avlop", "avløp",
})


class QueryPrivacyError(ValueError):
    """Input matched a prohibited personal/contact-data pattern."""


class InvalidQueryError(ValueError):
    """Input is malformed or exceeds the documented query limit."""


class UnsupportedTopicError(ValueError):
    """Safe query terms do not map to an approved municipal topic."""


_PERSONAL_ADDRESS = re.compile(
    r"\b(?:(?:[\w.'-]*?(?:gata|vei|veien))|(?:[\w.'-]+\s+(?:gate|street|road))|(?:gate|gata|vei|veien|street|road))\s+\d{1,4}[a-z]?\b",
    re.I,
)
_PERSONAL_DETAILS = re.compile(
    r"\b(?:jeg\s+heter|navnet\s+mitt\s+er|mitt\s+navn\s+er|fødselsnummer|personnummer|"
    r"telefonnummer|e-?postadresse|min\s+adresse|jeg\s+bor\s+i)\b",
    re.I,
)


def validate_query_privacy(query: str) -> None:
    """Reject recognizable personal/contact information before topic checks."""
    if not isinstance(query, str):
        raise InvalidQueryError("Query must be text")
    if len(query) > 160 or any(ord(c) < 32 for c in query):
        raise InvalidQueryError("Query is malformed or too long")
    if (re.search(r"@|https?://|\d[\d ()+-]{5,}\d", query, re.I)
            or _PERSONAL_ADDRESS.search(query) or _PERSONAL_DETAILS.search(query)):
        raise QueryPrivacyError("Personal or contact information is not accepted")


def tokens(text: str) -> list[str]:
    # Match common Norwegian spellings even when users omit diacritics.
    folded = unicodedata.normalize("NFC", text).casefold().translate(str.maketrans({"æ": "ae", "ø": "o", "å": "a"}))
    words = re.findall(r"[^\W_]+", folded)
    # Normalize frequent inflections/compounds present in reviewed plans and
    # public-health excerpts so base-form queries match their paragraphs.
    return ["folkehelse" if word.startswith("folkehelsearbeid") else QUERY_ALIASES.get(word, word)
            for word in words]


def validate_query(query: str, *, real_sources: bool = False, allow_followup: bool = False) -> list[str]:
    validate_query_privacy(query)
    terms = list(dict.fromkeys(t for t in tokens(query) if t not in STOPWORDS))[:16]
    if allow_followup:
        terms = [term for term in terms if term not in FOLLOWUP_MODIFIERS]
    if real_sources and any(term not in REAL_SERVICE_QUERY_TERMS for term in terms):
        raise UnsupportedTopicError("No approved municipal topic was identified")
    return terms


@dataclass(frozen=True)
class IndexedDocument:
    source: Source
    category: str
    retrieved_at: str | None
    indexed_at: str
    text_sha256: str
    approval_expires: str | None = None
    raw_sha256: str | None = None

    def __post_init__(self):
        if self.category not in CATEGORY_IDS:
            raise ValueError("Unknown service category")
        text = "\n\n".join(p.text for p in self.source.paragraphs)
        if self.text_sha256 != hashlib.sha256(text.encode("utf-8")).hexdigest():
            raise ValueError("Indexed text integrity mismatch")
        if not self.source.synthetic:
            from .portal_sources import validate_page_url
            validate_page_url(self.source.url)
            if not self.retrieved_at or not self.approval_expires:
                raise ValueError("Live documents require provenance and expiring approval")
            retrieved = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
            if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc):
                raise ValueError("Retrieval timestamp must be timezone-aware and not in the future")
            date.fromisoformat(self.approval_expires)

    def provenance(self) -> dict:
        expired = not self.source.synthetic and date.fromisoformat(self.approval_expires) < date.today()
        return {"source_id": self.source.id, "title": self.source.title, "url": self.source.url,
                "approval_status": "historical_expired" if expired else ("synthetic" if self.source.synthetic else "within_recorded_period"),
                "historical_warning": HISTORICAL_WARNING if expired else None,
                "retrieved_at": self.retrieved_at, "indexed_at": self.indexed_at,
                "text_sha256": self.text_sha256, "synthetic": self.source.synthetic,
                "category": self.category, "approval_expires": self.approval_expires, "raw_sha256": self.raw_sha256}


def index_document(source: Source, category: str, *, retrieved_at=None, approval_expires=None, raw_sha256=None) -> IndexedDocument:
    text = "\n\n".join(p.text for p in source.paragraphs)
    return IndexedDocument(source, category, retrieved_at, datetime.now(timezone.utc).isoformat(),
                           hashlib.sha256(text.encode("utf-8")).hexdigest(), approval_expires, raw_sha256)


@dataclass(frozen=True)
class SearchHit:
    document: IndexedDocument
    score: float
    excerpt: str
    paragraph_ids: tuple[str, ...]

    def to_dict(self):
        return {**self.document.provenance(), "score": round(self.score, 5),
                "excerpt": self.excerpt, "paragraph_ids": self.paragraph_ids}


class SearchIndex:
    """Immutable corpus per instance; queries never fetch or discover URLs."""

    def __init__(self, documents=()):
        documents = tuple(documents)
        if len(documents) > 200:
            raise ValueError("Index limit is 200 individually reviewed documents")
        self.documents = {d.source.id: d for d in documents}
        self.real_sources = any(not d.source.synthetic for d in documents)
        if len(self.documents) != len(documents):
            raise ValueError("Duplicate indexed source IDs")
        self.postings = defaultdict(dict)
        self.lengths = {}
        for doc in documents:
            body = " ".join(p.text for p in doc.source.paragraphs)
            words = tokens(body)
            if len(body.encode("utf-8")) > 512 * 1024:
                raise ValueError("Indexed document is too large")
            counts = Counter(words)
            # Title matches are weighted while body contains the full reviewed text.
            counts.update({word: count * 3 for word, count in Counter(tokens(doc.source.title)).items()})
            self.lengths[doc.source.id] = max(1, len(words))
            for word, count in counts.items():
                self.postings[word][doc.source.id] = count
        self.average_length = sum(self.lengths.values()) / max(1, len(self.lengths))

    def eligible(self, doc):
        return (doc.source.synthetic or date.fromisoformat(doc.approval_expires) >= date.today()
                or retained_document(doc))

    def search(self, query: str, *, category: str | None = None, limit: int = 10) -> tuple[SearchHit, ...]:
        terms = validate_query(query, real_sources=self.real_sources)
        if category is not None and category not in CATEGORY_IDS:
            raise ValueError("Ukjent tjenestekategori.")
        if not 1 <= limit <= 20:
            raise ValueError("Invalid result limit")
        if not terms:
            # Empty query is category browsing, not evidence for an AI answer.
            docs = [d for d in self.documents.values() if self.eligible(d) and (category is None or d.category == category)]
            return tuple(SearchHit(d, 0.0, d.source.paragraphs[0].text[:280], (d.source.paragraphs[0].id,))
                         for d in sorted(docs, key=lambda d: d.source.id)[:limit])
        candidates = set(self.postings.get(terms[0], {}))
        for term in terms[1:]:
            candidates.intersection_update(self.postings.get(term, {}))
        ranked = []
        n = len(self.documents)
        for doc_id in candidates:
            doc = self.documents[doc_id]
            if not self.eligible(doc) or category is not None and doc.category != category:
                continue
            score = 0.0
            for term in terms:
                tf = self.postings[term][doc_id]
                idf = math.log(1 + (n - len(self.postings[term]) + .5) / (len(self.postings[term]) + .5))
                score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * self.lengths[doc_id] / self.average_length))
            paragraphs = sorted(doc.source.paragraphs, key=lambda p: (-len(set(tokens(p.text)) & set(terms)), p.id))
            # Return real paragraph text; no HTML/highlight markup in the data.
            ranked.append(SearchHit(doc, score, paragraphs[0].text[:280], tuple(p.id for p in paragraphs[:2])))
        return tuple(sorted(ranked, key=lambda hit: (-hit.score, hit.document.source.id))[:limit])
