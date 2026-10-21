# Summary and evidence verification design

## Interface and provider boundary

The summarizer accepts a prepared `Source` containing paragraphs and returns immutable `Claim` records. Each claim carries a Norwegian text, one paragraph ID, and a quoted excerpt. The parser rejects malformed provider payloads, missing required citation fields, and duplicate claim IDs before records enter the verification stage. The existing shared schema remains unchanged.

`Summarizer` is the provider protocol. `MockSummarizer` supplies deterministic valid and intentionally invalid response payloads for offline evaluation. `OllamaSummarizer` implements this same protocol through a standard-library HTTP client. It accepts only loopback HTTP endpoints, uses JSON mode, temperature 0, a fixed seed, bounded prompt/output sizes, and a configurable timeout. `HAMAR_OLLAMA_MODEL` selects the model (default `llama3.2:3b`). It needs no external dependencies or API credentials.

## Evidence checks and limits

The verifier reports missing citations, unknown paragraph IDs, excerpts absent from the cited paragraph, unsupported numeric values, potentially unsupported content terms, explicit uncertainty markers, duplicate IDs, malformed output, and conflicting claims with the same normalized wording but different numbers. A result's `exact_match` status means only that the cited excerpt occurs in the referenced paragraph. It does not establish that the claim follows from the excerpt or that either is true.

Numeric checks, content-term overlap and conflict detection are deliberately narrow heuristics. Paraphrases may be flagged for review, while semantically unsupported wording may still pass the overlap heuristic. General semantic entailment, dates, units, negation, and factual truth require human review and may be missed. Findings should be surfaced for human review. Source paragraphs and model responses remain untrusted data.

The shared `Claim` schema supports one paragraph reference per claim. Multiple evidence spans, confidence scores, and richer uncertainty labels are outside this change so existing serialized output stays compatible.

## Bounded correction interface

`CorrectionProvider.revise(source, claims, findings) -> CorrectionResult` is the injectable correction contract. `OllamaCorrectionProvider` includes only the supplied source paragraphs, claims, and verifier feedback in its prompt, then verifies returned claims again. The workflow owner decides when to call it and enforces the revision limit. `CorrectionResult` carries immutable `claims`, `findings`, and `provider` fields; no shared schema changed. The existing `OneRevisionGate` remains available for the original scaffold contract.

## Evaluation

Offline tests use synthetic fixtures and fake transport responses. They cover malformed outputs, absent citations, invalid paragraph IDs, fabricated excerpts, changed numbers, conflicts, transport errors, prompt bounds, loopback enforcement, and correction re-verification. No network or real model is used by the default test command.

Run from the repository root:

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
```

The current offline suite passed: 86 tests. Fake transport is used for provider tests; this does not establish semantic correctness of generated claims.

Run the deterministic synthetic verifier scorecard with `python eval/evaluate_verification.py`. On 2026-10-21 it detected all 8 of 8 injected known issue types (1.0 expected-issue detection rate): missing citation, invalid paragraph ID, fabricated quote, changed number, unsupported statement, explicit uncertainty, conflicting claims, and malformed output. This is a small fixture-based self-check; it is not a model-quality or truth metric.

## Opt-in local model evaluation

Only sources in `hamar_agent.sources.APPROVED_SOURCES` are accepted by the smoke script; these fixtures are synthetic and contain no municipal facts or personal data. To run a local inference from PowerShell:

```powershell
ollama pull llama3.2:3b
# Start the local service if it is not already running:
ollama serve
# In a second terminal, from the repository root:
$env:HAMAR_OLLAMA_MODEL = "llama3.2:3b"
python eval/ollama_smoke.py --source-id synthetic-verification-demo
```

The endpoint is fixed to loopback (`127.0.0.1:11434`). Timeout defaults to 45 seconds, request size to 24,000 characters, response size to 128,000 bytes, and generation to at most 700 tokens. The smoke report includes citation, valid paragraph, exact quote, and verifier finding counts. These are traceability and heuristic metrics only, not semantic entailment or truth metrics.

For example, the fixture paragraph `I denne oppdiktede målingen er hardheten 3 °dH.` supports a traceable excerpt when the model returns that paragraph ID and quote. If it changes `3` to `30`, the unsupported-number finding should catch the difference. A matching quote alone still does not establish that the claim is factually true.

On 2026-10-21, `ollama list` showed `llama3.2:3b` installed. The smoke invocation reached Ollama but failed with HTTP 500; a minimal `ollama run llama3.2:3b` check reported that `llama-server` terminated (`0xc0000409`) with `CUDA error: device kernel image is invalid`. No model claims or quality metrics were produced. This points to a local GPU/runtime compatibility problem, not a missing model. Resolve the local Ollama/CUDA runtime and rerun the command above to obtain actual metrics.

## Integration contract for workflow owner

- Summarization: instantiate `OllamaSummarizer()` and pass it to existing `run_workflow(source_id, summarizer, provider="ollama", ...)`. Its `summarize(Source)` method returns `tuple[Claim, ...]`.
- Findings: use `summarize_with_report(Source)` when the caller needs claims and `VerificationReport.findings` together, or call `verify_claims(source, claims)` after summarization.
- Correction: instantiate `OllamaCorrectionProvider()` and call `revise(source, claims, findings)`. It returns `CorrectionResult`; workflow enforces the one-revision policy.
- Mock: `MockSummarizer` keeps its public interface and remains usable offline.
- Do not send personal data or unapproved retrieved content to a model. Smoke source loading is restricted to approved synthetic fixtures.
