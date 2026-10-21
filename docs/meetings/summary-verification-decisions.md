# Summary and evidence verification decisions

## Scope

- Work is isolated on `feat/summary-verification`, based on merged PR #1.
- Keep the shared schema and powerNeron-owned fetching, workflow, CLI, and JSON-output components unchanged.
- Use only Python's standard library and synthetic fixtures; make no model or network calls.

## Decisions

- Retain `Summarizer.summarize(Source) -> tuple[Claim, ...]` as the provider contract.
- Parse model-like responses into the existing immutable `Claim` records and reject malformed structures before verification.
- Keep evidence traceability status separate from verification findings. Exact excerpt matches never mean semantic support or truth.
- Restrict automatic numeric and conflict checks to deterministic heuristics and report findings for human review.
- Flag low lexical support and explicit uncertainty markers as review findings without presenting either as semantic proof.
- Expose a single-use correction gate. Workflow orchestration and model calls remain outside this component.
- Add a loopback-only Ollama adapter and injectable correction provider without changing Source, Claim, Result, workflow, or CLI contracts. The workflow owner controls the revision count.
- Keep real-model evaluation opt-in and restricted to approved synthetic fixtures. Record traceability metrics as heuristics, never semantic truth scores.
