"""Offline orchestration; summarization and verification belong to providers."""
from collections.abc import Callable

from .schemas import Result, Source
from .sources import load_source
from .summarize import Summarizer


def run_workflow(
    source_id: str,
    summarizer: Summarizer,
    *,
    provider: str,
    loader: Callable[[str], Source] = load_source,
) -> Result:
    """Use a trusted approval-enforcing loader; propagate failures to the caller.

    Injection is a programmatic test/integration seam, not a CLI approval bypass.
    No evidence classification or status promotion is performed here.
    """
    source = loader(source_id)
    if not isinstance(source, Source) or source.id != source_id:
        raise ValueError("loader returned an unexpected source")
    if not source.synthetic:
        raise ValueError("offline workflow accepts synthetic sources only")
    return Result(source, summarizer.summarize(source), provider=provider)
