"""Provider boundary for a later, separately approved OpenAI adapter."""
from typing import Protocol
from .schemas import Claim, Source


class Summarizer(Protocol):
    def summarize(self, source: Source) -> tuple[Claim, ...]:
        """Return claims with references; do not imply verification."""
        ...


class MockSummarizer:
    """Deterministic extractive stand-in, not an LLM or live integration."""

    def summarize(self, source: Source) -> tuple[Claim, ...]:
        if not source.synthetic:
            raise ValueError("mock demonstration accepts synthetic sources only")
        return tuple(
            Claim(f"c{index}", p.text, p.id, p.text)
            for index, p in enumerate(source.paragraphs, start=1)
        )
