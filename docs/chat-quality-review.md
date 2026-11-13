# Human review of local AI chat answers

The local model harness records actual answer text, exact prompt fingerprints, provider metadata, latency, token usage when available, and mechanical observations. Keyword matches and HTTP success are not quality scores. Use independent human review for answer correctness, relevance, context use, calibration and clarity.

From the repository root, create a blank scorecard for a completed run (all output paths must be new and stay under `output/`):

```powershell
python -B -m harness.chat_quality_review --run output/ollama-quality-primary-unique --template output/ollama-quality-primary-reviewer-a.json
```

Open the template and fill `reviewer_code`, `reviewed_at`, each integer score from 0 to 2, and optional controlled tags. Use anonymous reviewer codes; do not enter names, personal data, raw answers, or free-text notes. Review the answer in the corresponding run JSON file and score against the fixed case expectation. Do not let keyword observations determine a score.

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Accuracy | Incorrect or materially invented | Partly correct or missing a key condition | Correct for the question and stated scope |
| Relevance | Does not address the question | Partly addresses it | Directly addresses it |
| Context | Ignores explicit conversation context | Uses some context but misses a cue | Correctly uses the relevant context |
| Calibration | Unwarranted certainty or guessed detail | Some uncertainty/clarification, but incomplete | Appropriate confidence; asks when needed |
| Clarity | Misleading or hard to follow | Understandable with notable ambiguity | Clear, concise Norwegian |

Allowed tags are `unsupported_claim`, `wrong_sense`, `context_dropped`, `ambiguity_unresolved`, `uncertainty_missing`, `language_issue`, `overly_verbose`, `safe_referral`, `useful_clarification`, and `provider_error`. The tool rejects missing/duplicate cases, unknown tags, non-integer scores, duplicate reviewer codes, and scorecards bound to a different run digest.

Summarize one or multiple independently completed reviewer files:

```powershell
python -B -m harness.chat_quality_review --run output/ollama-quality-primary-unique --scores output/ollama-quality-reviewers.json --report output/ollama-quality-review-summary.json
```

`--scores` accepts one scorecard object or a JSON list of scorecards. The report keeps reviewer means separate and shows per-case score ranges; it never silently averages away disagreement. A completed review describes only that exact model digest, prompt/case-set digest and run. It does not establish population accuracy, truth, or reliability on unseen inputs. The existing prompt suite remains small and human-reviewed; retain additional/adversarial and high-stakes cases as separate suites rather than tuning against a held-out set.
