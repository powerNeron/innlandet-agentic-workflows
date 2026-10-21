"""Small, orchestration-neutral interface for one bounded correction."""
from dataclasses import dataclass

from .schemas import Claim, Source
from .verify import VerificationFinding


class RevisionLimitExceeded(RuntimeError):
    """Raised when a workflow requests more than one model revision."""


@dataclass(frozen=True)
class RevisionRequest:
    source_id: str
    prior_claims: tuple[Claim, ...]
    findings: tuple[VerificationFinding, ...]
    attempt: int = 1


class OneRevisionGate:
    """Issue at most one correction request; the caller runs the workflow."""

    def __init__(self) -> None:
        self._issued = False

    def request(
        self,
        source: Source,
        prior_claims: tuple[Claim, ...],
        findings: tuple[VerificationFinding, ...],
    ) -> RevisionRequest:
        if self._issued:
            raise RevisionLimitExceeded("at most one revision request is allowed")
        if not isinstance(source, Source):
            raise TypeError("source must be a Source record")
        if not prior_claims or not all(isinstance(claim, Claim) for claim in prior_claims):
            raise ValueError("prior_claims must contain Claim records")
        if not findings or not all(isinstance(finding, VerificationFinding) for finding in findings):
            raise ValueError("findings must contain verification findings")

        self._issued = True
        return RevisionRequest(source.id, prior_claims, findings)
