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