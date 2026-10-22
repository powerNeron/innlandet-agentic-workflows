# Innlandet Agentic Workflows

> Real reviewed municipal mode can use the existing reviewed local catalog. **All raw HTML acquisition and import are disabled**, including offline snapshot parsing, because personal information cannot be ruled out before parsing. Do not renew or create a catalog from HTML until the input format guarantees that personal information is never received or processed. See [real-source instructions and actual test evidence](docs/real-source-workflow.md) and [PASS/FAIL/UNKNOWN assignment matrix](docs/assignment-requirements-matrix.md). Current source approvals expire on 2026-10-28.


KIUA-2003 group project at the University of Inland Norway, developed by two students.

## Hamar KommuneAgent

The application will automatically process, summarize and verify public municipal information from Hamar, Norway. Summaries must cite their sources and distinguish supported facts from uncertainty. Verification means checking claims against source material; it does not guarantee correctness.

## Data boundary

Do not collect or process personal data. Public availability is not permission to process personal data. Use only explicitly reviewed, non-personal municipal material. Do not ingest unreviewed webpages, meeting records, attachments or free-text submissions. Stop processing and reject a source if its eligibility is uncertain. Use synthetic, non-personal fixtures for development and evaluation.

## Working together

Use short-lived branches and pull requests into `main`. Review changes with the other student. Read AGENTS.md before using Codex. Record task goals and acceptance criteria under tasks/, prompts in docs/prompt-log.md, and decisions in docs/meetings/.

## Structure

- SPEC.md: scope and acceptance criteria
- AGENTS.md: instructions for coding agents
- tasks/: planned work
- harness/: workflow execution and checks
- eval/: evaluation cases and scoring
- fixtures/: synthetic, non-personal examples
- docs/meetings/: meeting notes and decisions

The original lines above describe the initial scaffold only. The current application uses Python 3.12 and the standard library for local/Ollama operation; OpenAI is an optional dependency listed separately. `.env.example` is a reference only: the application reads process environment variables and does not load `.env` files. Never commit credentials.
## Offline implementation and current collaboration agreement

Python 3.12 offline source approval and orchestration are documented in [docs/source-workflow.md](docs/source-workflow.md). Run `python -m unittest discover -s eval -p 'test_*.py' -v` and `python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json` from the repository root. No packages or credentials are required. Only the explicitly approved synthetic fixture is accepted.

The current agreement supersedes the earlier peer-review requirement: cross-review is optional while each student develops independently. powerNeron owns sources/orchestration/CLI/JSON; JeppeGs owns summarization/LLM/verification/evaluation. Coordinate shared interfaces, keep separate branches and use PRs for integration.


## Historical full-system baseline

This section records an earlier synthetic-only phase. The later local-provider instructions below supersede its default-mode description.

See [full-system run instructions](docs/full-system-web.md), [proposed additive integration contract](docs/full-system-contract.md), and [ownership/decisions](docs/meetings/full-system-web-decisions.md). These supersede earlier setup notes about undecided runtime, fixture-only stdout and unconnected verification. Shared schemas and JeppeGs's modules remain unchanged. Earlier PR-specific reports record their historical state.


## Historical initial search-portal baseline

This section records the initial synthetic portal. Current real-source mode, provider selection, independent search form behavior, and source/privacy limitations are described below and in the linked current documentation.

See [portal startup and limitations](docs/search-portal.md) and [individual source review/import process](docs/source-review-process.md). The original fixture CLI and developer workflow remain available. Source categories reference [Hamar's official menu](https://www.hamar.kommune.no/meny/); this reference does not authorize ingestion.


## Local AI providers and website

The website has independent municipal search and AI question-answering forms. Ollama remains the default real-source provider, and the website model selector offers only server-allowlisted models reported by the local Ollama server. The existing verifier and single bounded correction/re-verification path are shared across providers. Answers currently use complete reviewed paragraphs; this is traceability, not semantic fact-checking or paraphrase verification. See [provider setup and limits](docs/provider-configuration.md), [real-source workflow](docs/real-source-workflow.md), and [integration evidence](docs/meetings/ollama-integration.md).

From the repository root:

```powershell
python -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
python -X utf8 -m hamar_agent.web --port 8000 --provider ollama --model llama3.2:3b --ollama-timeout 90
python -X utf8 -m hamar_agent --source synthetic-verification-demo --provider ollama --model llama3.2:3b --ollama-timeout 90
```

Open http://127.0.0.1:8000. Run one server command at a time. Ollama must already be running with the chosen model installed; these commands install or download nothing. The default web startup is real-source mode and fails closed if the local approved catalog or model is unavailable. `--demo --provider mock` explicitly selects synthetic offline mode. OpenAI is optional and remains disabled unless separately configured and privacy-authorized server-side; see the provider guide for its limitations. No provider silently falls back to a paid provider. The real model currently selects exact reviewed paragraphs rather than composing semantically verified paraphrases.


## Current local development commands

```powershell
python -X utf8 -m harness.offline_tests
python -X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000
python -X utf8 -m hamar_agent --real-sources --source hamar-drikkevann --model llama3.2:3b --ollama-timeout 90 --output output/NEW-result.json
```

Real mode uses the approved local catalog, provider adapter, Jesper's verifier plus strict complete-paragraph matching, at most one correction and mandatory re-verification, provenance and exclusive JSON output. Missing data/model fails closed. Synthetic data is for explicit offline/test/demo use (`--demo --provider mock` for the web). No unreviewed source is fetched on a search. The real model selects exact source excerpts; this is not unrestricted generative summarization or semantic fact-checking. Source-update review remains manual and proposal-only because raw HTML acquisition is blocked by the current privacy boundary. README/code/docs were assisted by OpenAI Codex under student direction and require student review and responsibility before submission.

For offline source-proposal comparison and local review decision records, see [source proposal administration](docs/source-proposal-administration.md). These controls do not activate content or change approval dates.
