"""Deterministic evidence checks; matches do not establish truth."""
from dataclasses import dataclass, replace
from enum import StrEnum
import re

from .schemas import Claim, EvidenceStatus, Source
from .summarize import SummaryResponseError, parse_claim_response


class FindingCode(StrEnum):
    MALFORMED_OUTPUT = "malformed_output"
    MALFORMED_CLAIM = "malformed_claim"
    MISSING_CITATION = "missing_citation"
    INVALID_PARAGRAPH_ID = "invalid_paragraph_id"
    FABRICATED_EVIDENCE = "fabricated_evidence"
    UNSUPPORTED_NUMBER = "unsupported_number"
    POTENTIALLY_UNSUPPORTED = "potentially_unsupported"
    UNCERTAIN_CLAIM = "uncertain_claim"
    DUPLICATE_CLAIM_ID = "duplicate_claim_id"
    CONFLICTING_CLAIMS = "conflicting_claims"


@dataclass(frozen=True)
class VerificationFinding:
    code: FindingCode
    message: str
    claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationReport:
    """Traceability statuses plus explicit findings for human review."""

    claims: tuple[Claim, ...]
    findings: tuple[VerificationFinding, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")
_WORD = re.compile(r"[a-zæøå0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset({
    "alle", "and", "at", "av", "bare", "ble", "den", "denne", "der", "det", "du",
    "en", "er", "et", "for", "fra", "hadde", "har", "i", "ikke", "ingen", "kan",
    "med", "men", "mot", "noe", "og", "om", "opp", "på", "så", "til", "under", "var",
    "vi", "vil", "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on",
})


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(match.group().replace(",", ".") for match in _NUMBER.finditer(text))


def _claim_signature(text: str) -> tuple[str, tuple[str, ...]]:
    numbers = _numbers(text)
    stem = _NUMBER.sub("<number>", text.casefold())
    stem = " ".join(re.findall(r"[\w<>]+", stem))
    return stem, numbers


def _content_terms(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _WORD.findall(text)
        if token.casefold() not in _STOPWORDS and not token.isdecimal()
    }


def verify_response(source: Source, payload: object) -> VerificationReport:
    """Parse and check an untrusted structured response against a source."""
    try:
        claims = parse_claim_response(payload)
    except SummaryResponseError as exc:
        code = {
            "missing_citation": FindingCode.MISSING_CITATION,
            "duplicate_claim_id": FindingCode.DUPLICATE_CLAIM_ID,
            "malformed_claim": FindingCode.MALFORMED_CLAIM,
        }.get(exc.code, FindingCode.MALFORMED_OUTPUT)
        return VerificationReport((), (VerificationFinding(code, str(exc)),))
    return verify_claims(source, claims)


def verify_claims(source: Source, claims: tuple[Claim, ...]) -> VerificationReport:
    """Check references, excerpts, numeric assertions, and claim conflicts.

    A valid excerpt receives EXACT_MATCH even when its claim is unsupported;
    findings separately flag detectable problems. General semantic entailment
    and factual truth are outside this deterministic check.
    """
    if not isinstance(source, Source):
        raise TypeError("source must be a Source record")
    if not isinstance(claims, tuple):
        raise TypeError("claims must be a tuple of Claim records")
    if not claims:
        return VerificationReport((), (
            VerificationFinding(FindingCode.MALFORMED_OUTPUT, "response must contain at least one claim"),
        ))

    findings: list[VerificationFinding] = []
    prepared: list[Claim] = []
    paragraph_text = {paragraph.id: paragraph.text for paragraph in source.paragraphs}
    seen_ids: set[str] = set()

    for claim in claims:
        if not isinstance(claim, Claim):
            findings.append(VerificationFinding(FindingCode.MALFORMED_CLAIM, "response contains a non-Claim value"))
            continue
        if claim.id in seen_ids:
            findings.append(VerificationFinding(
                FindingCode.DUPLICATE_CLAIM_ID,
                f"claim ID {claim.id!r} is repeated",
                (claim.id,),
            ))
        seen_ids.add(claim.id)

        cited_text = paragraph_text.get(claim.paragraph_id)
        status = EvidenceStatus.MISSING
        if not claim.paragraph_id or not claim.evidence_quote:
            findings.append(VerificationFinding(
                FindingCode.MISSING_CITATION,
                "claim is missing a paragraph ID or quoted excerpt",
                (claim.id,),
            ))
        elif cited_text is None:
            findings.append(VerificationFinding(
                FindingCode.INVALID_PARAGRAPH_ID,
                f"paragraph ID {claim.paragraph_id!r} is not in the prepared source",
                (claim.id,),
            ))
        elif claim.evidence_quote not in cited_text:
            findings.append(VerificationFinding(
                FindingCode.FABRICATED_EVIDENCE,
                "quoted excerpt does not occur in the referenced paragraph",
                (claim.id,),
            ))
        else:
            status = EvidenceStatus.EXACT_MATCH
            evidence_numbers = _numbers(claim.evidence_quote)
            unsupported_numbers = tuple(number for number in _numbers(claim.text) if number not in evidence_numbers)
            if unsupported_numbers:
                findings.append(VerificationFinding(
                    FindingCode.UNSUPPORTED_NUMBER,
                    f"claim contains numeric value(s) absent from its evidence: {', '.join(unsupported_numbers)}",
                    (claim.id,),
                ))
            unsupported_terms = _content_terms(claim.text) - _content_terms(claim.evidence_quote)
            if unsupported_terms:
                findings.append(VerificationFinding(
                    FindingCode.POTENTIALLY_UNSUPPORTED,
                    "claim contains content terms absent from its quote; semantic review is required",
                    (claim.id,),
                ))
        if claim.text.casefold().startswith(("usikkert:", "uavklart:", "muligens:")):
            findings.append(VerificationFinding(
                FindingCode.UNCERTAIN_CLAIM,
                "claim is explicitly marked uncertain and requires human review",
                (claim.id,),
            ))
        prepared.append(replace(claim, evidence_status=status))

    signatures: dict[str, dict[tuple[str, ...], list[str]]] = {}
    for claim in prepared:
        stem, numbers = _claim_signature(claim.text)
        if numbers:
            signatures.setdefault(stem, {}).setdefault(numbers, []).append(claim.id)
    for stem, variants in signatures.items():
        if len(variants) > 1:
            claim_ids = tuple(claim_id for ids in variants.values() for claim_id in ids)
            findings.append(VerificationFinding(
                FindingCode.CONFLICTING_CLAIMS,
                f"claims with the same wording contain conflicting numeric values: {stem}",
                claim_ids,
            ))

    return VerificationReport(tuple(prepared), tuple(findings))
