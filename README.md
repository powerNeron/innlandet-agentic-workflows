# Innlandet Agentic Workflows

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

No application or dependencies have been installed yet. Runtime versions and dependency choices will be agreed upon before implementation. Copy .env.example to .env only when configuration is needed; never commit credentials.
## Offline implementation and current collaboration agreement

Python 3.12 offline source approval and orchestration are documented in [docs/source-workflow.md](docs/source-workflow.md). Run `python -m unittest discover -s eval -p 'test_*.py' -v` and `python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json` from the repository root. No packages or credentials are required. Only the explicitly approved synthetic fixture is accepted.

The current agreement supersedes the earlier peer-review requirement: cross-review is optional while each student develops independently. powerNeron owns sources/orchestration/CLI/JSON; JeppeGs owns summarization/LLM/verification/evaluation. Coordinate shared interfaces, keep separate branches and use PRs for integration.


## Current full-system branch

The local CLI and web interface now run the existing verifier and preserve findings in workflow JSON. Start `python -X utf8 -m hamar_agent.web --port 8000` and open http://127.0.0.1:8000. The default is synthetic data with a mock provider, not a real LLM. No external source is enabled.

See [full-system run instructions](docs/full-system-web.md), [proposed additive integration contract](docs/full-system-contract.md), and [ownership/decisions](docs/meetings/full-system-web-decisions.md). These supersede earlier setup notes about undecided runtime, fixture-only stdout and unconnected verification. Shared schemas and JeppeGs's modules remain unchanged. Earlier PR-specific reports record their historical state.


## Search portal on feat/full-system-web

The local homepage now includes Norwegian service categories, genuine keyword/full-text search, source provenance and verified answer excerpts. Start `python -X utf8 -m hamar_agent.web --port 8000` and open http://127.0.0.1:8000. Defaults are eight clearly synthetic documents and a mock provider; no municipal URL is approved and no search triggers retrieval. This is an independent student project with limited coverage.

See [portal startup and limitations](docs/search-portal.md) and [individual source review/import process](docs/source-review-process.md). The original fixture CLI and developer workflow remain available. Source categories reference [Hamar's official menu](https://www.hamar.kommune.no/meny/); this reference does not authorize ingestion.


## Integrated local Ollama runtime (2026-10-21)

The default remains honest offline mock mode. Jesper's actual Ollama summarizer and correction adapter are now composed with the same verified workflow used by CLI and portal; no provider files or shared schemas were changed. See [integration evidence and limitations](docs/meetings/ollama-integration.md) and the current section of [the additive contract](docs/full-system-contract.md).

From the repository root:

```powershell
python -X utf8 -m hamar_agent.web --port 8000 --provider mock
python -X utf8 -m hamar_agent.web --port 8000 --provider ollama --model llama3.2:3b --ollama-timeout 90
python -X utf8 -m hamar_agent --source synthetic-verification-demo --provider ollama --model llama3.2:3b --ollama-timeout 90
```

Open http://127.0.0.1:8000. Run one server command at a time. Ollama must already be running with that model installed; these commands install or download nothing. Optional --fallback-to-mock is explicit and labels fallback output. Without it provider errors fail. Model output may retain invalid references or uncertainty after the single correction attempt; read all findings. This is evidence checking, not semantic fact-checking. Real municipal LLM answers are not yet supported by the synthetic-only provider.
