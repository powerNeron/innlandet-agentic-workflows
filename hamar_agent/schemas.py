"""Immutable shared records. Evidence status never means factual truth."""
from dataclasses import asdict, dataclass
from enum import StrEnum
import json


def require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")


class EvidenceStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    EXACT_MATCH = "exact_match"
    MISSING = "missing"


@dataclass(frozen=True)
class Paragraph:
    id: str
    text: str

    def __post_init__(self) -> None:
        require_text(self.id, "paragraph id")
        require_text(self.text, "paragraph text")


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    paragraphs: tuple[Paragraph, ...]
    synthetic: bool
    url: str | None = None

    def __post_init__(self) -> None:
        require_text(self.id, "source id")
        require_text(self.title, "source title")
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic must be a boolean")
        if not isinstance(self.paragraphs, tuple) or not self.paragraphs:
            raise ValueError("paragraphs must be a non-empty tuple")
        if not all(isinstance(p, Paragraph) for p in self.paragraphs):
            raise ValueError("paragraphs must contain Paragraph records")
        if len({p.id for p in self.paragraphs}) != len(self.paragraphs):
            raise ValueError("paragraph IDs must be unique")
        if self.url is not None:
            require_text(self.url, "source URL")


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    paragraph_id: str
    evidence_quote: str
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_CHECKED

    def __post_init__(self) -> None:
        for field in ("id", "text", "paragraph_id", "evidence_quote"):
            require_text(getattr(self, field), field)
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise ValueError("evidence_status must be an EvidenceStatus")


@dataclass(frozen=True)
class Result:
    source: Source
    claims: tuple[Claim, ...]
    provider: str = "mock"
    schema_version: str = "1.0"
    warnings: tuple[str, ...] = (
        "Synthetic demonstration; not municipal information.",
        "Evidence matching is not semantic fact-checking or a guarantee of truth.",
    )

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise ValueError("source must be a Source record")
        if not isinstance(self.claims, tuple) or not self.claims:
            raise ValueError("claims must be a non-empty tuple")
        if not all(isinstance(c, Claim) for c in self.claims):
            raise ValueError("claims must contain Claim records")
        if len({c.id for c in self.claims}) != len(self.claims):
            raise ValueError("claim IDs must be unique")
        require_text(self.provider, "provider")
        if self.schema_version != "1.0":
            raise ValueError("unsupported schema version")
        if not isinstance(self.warnings, tuple):
            raise ValueError("warnings must be a tuple")
        for warning in self.warnings:
            require_text(warning, "warning")

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"
