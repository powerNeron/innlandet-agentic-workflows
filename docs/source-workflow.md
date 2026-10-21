# Offline source workflow ? KIUA-2003

## Scope and decisions

This branch implements powerNeron's approval, fixture loading, orchestration and CLI components using Python 3.12 and the standard library. It adds no network client, live source, credential handling, model integration, verification logic or result-file saving.

The trusted APPROVED_SOURCES registry initially contains only synthetic-water-demo. Approval binds its ID to a repository-relative fixture location, a SHA-256 content digest and a review rationale. The loader rejects unknown IDs or paths before opening files. It reads at most 64 KiB plus one byte, checks the digest before decoding JSON, then validates synthetic labeling, source identity and the existing Source schema. Digest calculation normalizes CRLF to LF so Git checkout settings do not invalidate approval. Other content changes require review and a new approved digest; approval is never inferred from the input's synthetic flag.

The content hash prevents changed content reaching parsing or summarization, but checking it necessarily reads bytes from the approved path first. The registry is trusted project configuration, not a sandbox against malicious local file replacement or privileged Python callers. No personal-data detector is claimed. Do not place personal data at an approved path. Live municipal approval remains a separate design task.

load_fixture(path) remains importable from hamar_agent.__main__ for compatibility, now delegating to sources.py. Its security behavior is intentionally narrower: arbitrary local paths, even labeled synthetic, are rejected. Tests can inject a trusted temporary registry to exercise malformed approved input without changing production approvals.

run_workflow(source_id, summarizer, *, provider, loader=load_source) returns the existing Result. The loader must enforce approval; injectable loaders are trusted application/test code, not a user-facing bypass. The workflow checks source identity and synthetic status before calling summarize. It preserves responses and statuses, delegates response shape validation to Result, and propagates errors. Provider labeling is explicit rather than incorrectly describing every injected implementation as mock.

The CLI preserves --fixture and JSON stdout. No partial JSON is printed on known input/provider errors, which exit with code 2. No schemas or summarize(source) interfaces changed. The earlier evidence-reference guard remains in separate local commit e833983 on feat/python-scaffold; it is not included here. Existing schema/evidence limitations therefore remain on this branch; orchestration does not imply verification or semantic fact-checking.

## Independent ownership

- powerNeron: source approval, sources.py, fetching when separately approved, workflow.py, CLI and JSON output; unit tests for these components.
- JeppeGs: summarization, LLM integration, evidence verification and evaluation.
- Shared schemas and interfaces: coordinate changes before editing. Preserve summarize(source) -> tuple[Claim, ...].
- Use separate feature branches from current origin/main and PRs for integration. Cross-review is optional at this stage by the user's updated instruction. Ask before pushing, creating PRs or merging; no force pushes or automatic merges.

No modifications to JeppeGs's summarizer, shared schemas, original fixture or original tests are included.

## Running in PyCharm or PowerShell

Use Python 3.12, repository root as working directory, and no third-party packages:

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
```

In PyCharm select the existing Python 3.12 interpreter, run module hamar_agent, and use --fixture fixtures/water-synthetic.json as parameters. Stdout is the result; no output file is created.

## Validation record

All 25 tests passed on Python 3.12.10: 9 existing scaffold tests and 16 new source/workflow tests. These cover approval before reads, immutable default registry, changed content, line-ending portability, malformed approved JSON, oversize and missing files, ID mismatches, injected responses, invalid result shapes, provider failures, no premature summarizer calls, no partial JSON and offline CLI compatibility. Temporary fixtures are synthetic only. No live retrieval or paid API was used.

The previous evidence follow-up suite belongs to a different local branch and is not counted in these 25 tests. Its six regression cases are preserved in commit e833983.

## Sanitized implementation prompt record

User authorized preserving pending work in a local commit, fetching updates, branching from origin/main and implementing only powerNeron's offline components. Remote writes require another approval. No credentials or personal data were used.
