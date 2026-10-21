# Python scaffold: PR 1

This document supplements the original project documents without replacing them.

## Scope and decisions

Python 3.12, standard library only. No package installation, network retrieval, paid APIs or credentials are required. Run from the repository root. The fixture is entirely fictional and is not a statement about Hamar water supply.

The CLI loads a local JSON fixture, requires an explicit synthetic boolean and no live source URL, generates deterministic mock extractive claims, and prints JSON to stdout. It does not save result files. Do not supply real municipal content or personal data as fixtures; the synthetic flag is a contract, not a personal-data detector.

Shared immutable dataclasses describe Source, Paragraph, Claim and Result. Sources have unique paragraph IDs; results have unique claim IDs. EvidenceStatus describes only evidence matching, with not_checked as the default. Even exact_match will mean only a matching excerpt, never semantic support or factual correctness. Referential and semantic checking are deliberately not implemented in this scaffold.

The Summarizer protocol is the future model-provider boundary. A later OpenAI adapter can implement it without changing the result schema. No OpenAI SDK, model selection, credentials or API integration is included now. The mock echoes each source paragraph; it is not an LLM quality demonstration.

No timestamps or random identifiers are included in v1, making fixture runs deterministic. Later workflow metadata can extend a versioned schema. Live-source approval, HTTP fetching, actual evidence matching, bounded revision, hashing and exclusive JSON-file saving belong to subsequent PRs. Approval must occur before any future source retrieval.

## Run in PowerShell or PyCharm

From the repository root with Python 3.12:

```powershell
python --version
python -m unittest discover -s eval -p 'test_*.py' -v
python -m hamar_agent --fixture fixtures/water-synthetic.json
```

An isolated environment is optional because there are no external dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s eval -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m hamar_agent --fixture fixtures/water-synthetic.json
```

No activation is required. In PyCharm open the repository folder, select Python 3.12 (or .venv/Scripts/python.exe), set the working directory to the repository root, and run module hamar_agent with parameters --fixture fixtures/water-synthetic.json. Do not configure a script path to __main__.py because the package uses relative imports.

Output contains schema_version, synthetic source and paragraphs, mock claims with evidence references and not_checked status, provider, and warnings. Inspect output in the console; do not treat it as a verified municipal summary.

## Evaluation approach

Tests cover record validation, duplicate identifiers, explicit synthetic input, real-source rejection by the mock, deterministic Unicode JSON, evidence references, offline CLI execution, malformed fixture handling, and an injected fabricated mock claim retaining not_checked status. The latter documents the boundary: schema validation is not evidence or semantic verification.

Tests use temporary directories for invalid inputs and do not overwrite project files. A socket guard prevents accidental network use in the CLI test. Mock tests do not evaluate real model behavior.
## Windows console encoding

If the console displays Norwegian characters incorrectly, use Python UTF-8 mode: python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json. JSON serialization preserves Unicode; UTF-8 mode also makes redirected stdout reproducible across Windows machines.
