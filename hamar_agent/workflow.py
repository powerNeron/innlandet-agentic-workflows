"""Offline orchestration; summarization and verification belong to providers."""
from collections.abc import Callable
from dataclasses import dataclass, field

from .schemas import Claim, Result, Source
from .sources import load_source
from .summarize import Summarizer
from .verify import VerificationFinding, VerificationReport, verify_claims
from .revision import OneRevisionGate, RevisionRequest


# Orchestration-owned seam, not an assumed method on JeppeGs's future adapter.
CorrectionCallback = Callable[[Source, RevisionRequest], tuple[Claim, ...]]


@dataclass(frozen=True)
class CorrectionOutcome:
    status: str = "not_needed"
    attempts: int = 0
    initial_claims: tuple[Claim, ...] = ()
    initial_findings: tuple[VerificationFinding, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowResult(Result):
    """Additive workflow report; the shared Result schema remains unchanged."""
    workflow_version: str = "1.0"
    verification: VerificationReport = field(default_factory=lambda: VerificationReport((), ()))
    correction: CorrectionOutcome = field(default_factory=CorrectionOutcome)


def _check_claims(claims: tuple[Claim, ...]) -> None:
    # Keep Result's nonempty/unique-record contract, before invoking the verifier.
    if not isinstance(claims, tuple) or not claims or not all(isinstance(c, Claim) for c in claims):
        raise ValueError("summarizer must return a non-empty tuple of Claim records")
    if len({c.id for c in claims}) != len(claims):
        raise ValueError("summarizer returned duplicate claim IDs")


def run_workflow(
    source_id: str,
    summarizer: Summarizer,
    *,
    provider: str,
    loader: Callable[[str], Source] = load_source,
    corrector: CorrectionCallback | None = None,
    allow_non_synthetic: bool = False,
) -> WorkflowResult:
    """Use a trusted approval-enforcing loader; propagate initial failures.

    Injection is a programmatic test/integration seam, not a CLI approval bypass.
    The existing verifier owns evidence classification, never semantic truth.
    Correction failures retain the initial report for review; never retry again.
    """
    source = loader(source_id)
    if not isinstance(source, Source) or source.id != source_id:
        raise ValueError("loader returned an unexpected source")
    if not source.synthetic and not allow_non_synthetic:
        raise ValueError("offline workflow accepts synthetic sources only")
    claims = summarizer.summarize(source)
    _check_claims(claims)
    report = verify_claims(source, claims)
    correction = CorrectionOutcome()
    if report.has_findings:
        correction = CorrectionOutcome("not_configured", initial_claims=report.claims, initial_findings=report.findings)
        if corrector is not None:
            request = OneRevisionGate().request(source, report.claims, report.findings)
            try:
                revised = corrector(source, request)
                _check_claims(revised)
                final_report = verify_claims(source, revised)
            except (OSError, ValueError, TypeError, RuntimeError):
                correction = CorrectionOutcome("failed", 1, report.claims, report.findings,
                                               ("Correction failed; original findings retained for review.",))
            else:
                correction = CorrectionOutcome("completed", 1, report.claims, report.findings)
                report = final_report
    warnings = ["Evidence matching is not semantic fact-checking or a guarantee of truth."]
    if source.synthetic:
        warnings.insert(0, "Synthetic demonstration; not municipal information.")
    if report.has_findings:
        warnings.append("Review required: verification findings remain unresolved.")
    warnings.extend(correction.warnings)
    return WorkflowResult(source=source, claims=report.claims, provider=provider,
                          warnings=tuple(warnings), verification=report, correction=correction)
