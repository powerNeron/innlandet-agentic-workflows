# Summary and evidence verification design

## Interface and provider boundary

The summarizer accepts a prepared `Source` containing paragraphs and returns immutable `Claim` records. Each claim carries a Norwegian text, one paragraph ID, and a quoted excerpt. The parser rejects malformed provider payloads, missing required citation fields, and duplicate claim IDs before records enter the verification stage. The existing shared schema remains unchanged.

`Summarizer` is the provider protocol. `MockSummarizer` supplies deterministic valid and intentionally invalid response payloads for offline evaluation, which can be passed through the same response verifier as a provider result. This protocol is the future adapter seam for an OpenAI implementation; this change adds no SDK, credentials, network use, or paid calls.

## Evidence checks and limits

The verifier reports missing citations, unknown paragraph IDs, excerpts absent from the cited paragraph, unsupported numeric values, duplicate IDs, malformed output, and conflicting claims with the same normalized wording but different numbers. A result's `exact_match` status means only that the cited excerpt occurs in the referenced paragraph. It does not establish that the claim follows from the excerpt or that either is true.

Numeric checks and conflict detection are deliberately narrow heuristics. General semantic entailment, paraphrase support, dates, units, negation, and factual truth require more capable review and may be missed. Findings should be surfaced for human review. Source paragraphs and model responses remain untrusted data.

The shared `Claim` schema supports one paragraph reference per claim. Multiple evidence spans, confidence scores, and richer uncertainty labels are outside this change so existing serialized output stays compatible.

## Bounded correction interface

`OneRevisionGate` packages the prior claims and verification findings into one `RevisionRequest`. A gate instance issues at most one request and raises `RevisionLimitExceeded` on a second request. It does not call a model or orchestrate workflow steps; the workflow owner decides when to use the request and validates the revised claims again.

## Evaluation

Tests use only the explicitly synthetic fixture `fixtures/verification-synthetic.json`. Scenarios cover valid structured claims, malformed output, absent citation fields, invalid paragraph IDs, fabricated excerpts, changed numbers, conflicting numeric claims, and the one-revision limit. The suite uses Python `unittest`; no network or model provider is used.

Run from the repository root:

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
```

The complete suite passed: 21 tests. No network calls or model providers were used.
