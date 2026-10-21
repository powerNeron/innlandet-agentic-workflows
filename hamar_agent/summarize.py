"""Provider boundary and offline model-response fixtures for summaries."""
from enum import StrEnum
import re
from typing import Protocol

from .schemas import Claim, Source


class Summarizer(Protocol):
    """Interface for a provider that summarizes an already prepared source."""

    def summarize(self, source: Source) -> tuple[Claim, ...]:
        """Return structured claims with paragraph IDs and quoted evidence."""
        ...


class SummaryResponseError(ValueError):
    """Raised when provider output does not match the claim contract."""

    def __init__(self, message: str, code: str = "malformed_output") -> None:
        super().__init__(message)
        self.code = code


_CLAIM_FIELDS = {"id", "text", "paragraph_id", "evidence_quote"}


def parse_claim_response(payload: object) -> tuple[Claim, ...]:
    """Validate a provider's decoded response without trusting its content."""
    if not isinstance(payload, dict) or set(payload) != {"claims"}:
        raise SummaryResponseError("response must be an object containing only 'claims'")
    raw_claims = payload["claims"]
    if not isinstance(raw_claims, list) or not raw_claims:
        raise SummaryResponseError("'claims' must be a non-empty list")

    claims = []
    for index, item in enumerate(raw_claims):
        if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
            raise SummaryResponseError(f"claim {index} must be an object with string keys", "malformed_claim")
        missing = _CLAIM_FIELDS - set(item)
        if missing:
            missing_citation = bool(missing & {"paragraph_id", "evidence_quote"})
            code = "missing_citation" if missing_citation else "malformed_claim"
            raise SummaryResponseError(f"claim {index} is missing fields: {', '.join(sorted(missing))}", code)
        if set(item) != _CLAIM_FIELDS:
            unexpected = ", ".join(sorted(set(item) - _CLAIM_FIELDS))
            raise SummaryResponseError(f"claim {index} contains unexpected fields: {unexpected}")
        try:
            claims.append(Claim(**item))
        except (TypeError, ValueError) as exc:
            text = str(exc)
            code = "missing_citation" if "paragraph_id" in text or "evidence_quote" in text else "malformed_claim"
            raise SummaryResponseError(f"claim {index} is invalid: {exc}", code) from exc

    if len({claim.id for claim in claims}) != len(claims):
        raise SummaryResponseError("claim IDs must be unique", "duplicate_claim_id")
    return tuple(claims)


class MockScenario(StrEnum):
    VALID = "valid"
    MISSING_CITATION = "missing_citation"
    INVALID_PARAGRAPH = "invalid_paragraph"
    FABRICATED_QUOTE = "fabricated_quote"
    CHANGED_NUMBER = "changed_number"
    UNSUPPORTED_STATEMENT = "unsupported_statement"
    UNCERTAIN_CLAIM = "uncertain_claim"
    CONFLICTING_CLAIMS = "conflicting_claims"
    MALFORMED_OUTPUT = "malformed_output"


class MockSummarizer:
    """Deterministic model-like responses; no LLM, network, or credentials."""

    def __init__(self, scenario: MockScenario = MockScenario.VALID) -> None:
        self.scenario = MockScenario(scenario)

    def summarize(self, source: Source) -> tuple[Claim, ...]:
        return parse_claim_response(self.response_payload(source))

    def response_payload(self, source: Source) -> object:
        """Return a deterministic decoded model-like payload for evaluation."""
        if not isinstance(source, Source):
            raise TypeError("source must be a Source record")
        if not source.synthetic:
            raise ValueError("mock demonstration accepts synthetic sources only")

        paragraphs = source.paragraphs
        if self.scenario is MockScenario.VALID:
            payload = {
                "claims": [
                    {
                        "id": f"c{index}",
                        "text": paragraph.text,
                        "paragraph_id": paragraph.id,
                        "evidence_quote": paragraph.text,
                    }
                    for index, paragraph in enumerate(paragraphs, start=1)
                ]
            }
        elif self.scenario is MockScenario.MISSING_CITATION:
            payload = {"claims": [{"id": "c1", "text": "En påstand", "evidence_quote": paragraphs[0].text}]}
        elif self.scenario is MockScenario.INVALID_PARAGRAPH:
            payload = {"claims": [self._claim("c1", "En syntetisk påstand", "p999", "Ukjent sitat")]}
        elif self.scenario is MockScenario.FABRICATED_QUOTE:
            payload = {"claims": [self._claim("c1", "En syntetisk påstand", paragraphs[0].id, "Oppdiktet sitat")]}
        elif self.scenario is MockScenario.CHANGED_NUMBER:
            payload = {
                "claims": [
                    self._claim("c1", "Den syntetiske målingen er 999.", paragraphs[0].id, paragraphs[0].text)
                ]
            }
        elif self.scenario is MockScenario.UNSUPPORTED_STATEMENT:
            payload = {
                "claims": [
                    self._claim("c1", "Kommunen stenger skolen i morgen.", paragraphs[0].id, paragraphs[0].text)
                ]
            }
        elif self.scenario is MockScenario.UNCERTAIN_CLAIM:
            payload = {
                "claims": [
                    self._claim("c1", f"Usikkert: {paragraphs[0].text}", paragraphs[0].id, paragraphs[0].text)
                ]
            }
        elif self.scenario is MockScenario.CONFLICTING_CLAIMS:
            first = paragraphs[0]
            second = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
            numbers = [re.findall(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", p.text) for p in (first, second)]
            first_number = numbers[0][0] if numbers[0] else "3"
            second_number = numbers[1][0] if numbers[1] and numbers[1][0] != first_number else "4"
            payload = {
                "claims": [
                    self._claim("c1", f"Målingen er {first_number}.", first.id, first.text),
                    self._claim("c2", f"Målingen er {second_number}.", second.id, second.text),
                ]
            }
        else:
            payload = {"claims": "dette er ikke en liste"}
        return payload

    @staticmethod
    def _claim(claim_id: str, text: str, paragraph_id: str, quote: str) -> dict[str, str]:
        return {
            "id": claim_id,
            "text": text,
            "paragraph_id": paragraph_id,
            "evidence_quote": quote,
        }
