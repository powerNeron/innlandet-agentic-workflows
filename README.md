# Aisha Agent - Innlandet Agentic Workflows

Aisha Agent (also named Hamar KommuneAgent in earlier records) is a two-student software project for KIUA-2003 at the University of Inland Norway. It helps residents and others seeking general, non-personal municipal service information for Hamar through independent service-search and AI question-answering forms.

The real-source workflow retrieves reviewed local excerpts, asks a local model to select one complete paragraph, verifies its source and exact wording, and returns an official citation or a refusal. It permits at most one correction followed by mandatory re-verification. This is an extractive prototype: evidence matching establishes traceability, not factual truth, complete municipal coverage or semantic verification of paraphrases.

**Development status:** the walking skeleton, tests and historical evaluation evidence are retained for Compulsory 2 and continued development toward the final exam. This repository is not a completed or approved academic submission.

## Requirements and setup

- Python 3.12. Historical evaluation records identify Python 3.12.10.
- No third-party Python packages or credentials are needed for synthetic operation or the standard-library Ollama application.
- Real local inference additionally requires a running Ollama server, an installed server-allowlisted model, and an eligible approved local municipal catalog.

Open the repository in a terminal or IDE and use its root as the working directory. Check the interpreter:

```powershell
python --version
```

An isolated environment is optional. If desired, create one and use its interpreter for the commands below:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
```

No package installation is required for the default local paths. OpenAI is an optional external provider, disabled by default. Install its separate [requirements](requirements-openai.txt) only after external processing has been explicitly authorized; follow the [provider configuration guide](docs/provider-configuration.md). No provider automatically falls back to a paid service.

The application reads process environment variables. [.env.example](.env.example) is a reference; the application does not load `.env` files. Keep credentials in ignored local configuration and never commit them.

## Run the synthetic walking skeleton

From the repository root:

```powershell
python -B -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
```

Expected output is JSON on standard output with the explicitly synthetic source, two supported claims, evidence references and no verification findings. This path uses the mock provider, needs no catalog or model, and makes no municipal retrieval request. It checks orchestration and evidence matching, not real-model quality.

The historical result is preserved in [walking-skeleton-synthetic.json](comp2/evidence/walking-skeleton-synthetic.json), with command metadata in [new-command-register.json](comp2/evidence/new-command-register.json). Running the CLI command above does not overwrite either file.

For the offline demonstration website:

```powershell
python -B -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
```

Open <http://127.0.0.1:8000>. Run only one server on the chosen port; reuse an existing appropriate server rather than starting a duplicate. In PyCharm, select Python 3.12 and run the module with the repository root as the working directory; do not execute `hamar_agent/__main__.py` as a standalone script. See the [Python setup notes](docs/python-scaffold.md).

## Run with approved local municipal sources

Real mode requires all of the following:

1. An existing, lawfully obtained and individually approved local catalog at `output/municipal-catalog.json`.
2. Exact URL- and paragraph-specific approval and provenance matching the reviewed manifests, with valid review and expiry dates.
3. Ollama already running locally, with the chosen model installed and allowed by server configuration. The documented model is `llama3.2:3b`; the application never installs or downloads models.

The catalog is ignored local data and is not supplied by a Git clone. The recorded source approvals expire on **2026-10-28**. Missing, expired or ineligible sources must cause real mode to refuse operation; do not extend dates simply to reproduce a result. Reproduction on a new machine requires separately authorized access to eligible excerpts.

**Raw municipal HTML acquisition and import are disabled, including offline snapshot parsing.** Historical acquisition instructions and observations do not authorize new retrieval. Do not recreate or renew a catalog from HTML until an approved input process establishes that personal information is never received or processed.

After satisfying the local requirements, inspect installed models and start real mode:

```powershell
ollama list
python -B -X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Open <http://127.0.0.1:8000> and, for example, ask `Hva kan jeg bygge uten å søke?`. Check the displayed excerpt, verification status and official source link. The website lists only model tags both installed locally and allowed by the server. Default web startup uses real-source mode; synthetic mode requires the explicit demo flags.

A source-based CLI run is also available:

```powershell
python -B -X utf8 -m hamar_agent --real-sources --source hamar-byggesak --model llama3.2:3b --ollama-timeout 90
python -B -X utf8 -m hamar_agent --real-sources --source hamar-drikkevann --model llama3.2:3b --ollama-timeout 90 --output output/NEW-result.json
```

Use a new output filename: JSON export is exclusive and does not overwrite existing results. The CLI source run and the browser's question-based retrieval are distinct checks. An opt-in local-model synthetic example is documented separately:

```powershell
python -B -X utf8 -m hamar_agent --source synthetic-verification-demo --provider ollama --model llama3.2:3b --ollama-timeout 90
```

Real mode never silently substitutes synthetic data when its catalog, model or verification fails. See the [real-source workflow and historical test evidence](docs/real-source-workflow.md), [source review process](docs/source-review-process.md), [portal guide](docs/search-portal.md) and [provider configuration](docs/provider-configuration.md).

## Architecture and boundaries

The application uses Python's standard library, a local search index, local HTTP interfaces and versioned JSON results. Ordinary service search does not invoke the model. The AI form performs its own retrieval and sufficiency checks before invoking the provider.

The runtime stages are:

1. Apply privacy/topic constraints and check source eligibility and validity.
2. Retrieve approved local paragraphs and determine whether evidence is sufficient.
3. Ask the configured provider to select a whole reviewed paragraph.
4. Check paragraph identity, verbatim claim/evidence support and provenance through the existing verifier and strict adapter.
5. Permit at most one correction, re-verify, and return a cited result or safe refusal.

Human source admission precedes runtime. There is no autonomous crawling, source approval or unrestricted shell execution by the model. See the [workflow contract](docs/full-system-contract.md), [integration guide](docs/full-system-web.md), [summary and verification design](docs/summary-verification.md), [JSON storage notes](docs/json-result-saving.md) and [workflow figure](comp2/figures/aisha-workflow.pdf).

### Privacy and security

Do not collect or process personal data. Public availability is not permission. Use synthetic fixtures for development and explicitly reviewed non-personal excerpts for real operation. Reject uncertain input and treat external source text as untrusted data rather than executable instructions. Source categories based on [Hamar's official menu](https://www.hamar.kommune.no/meny/) do not authorize ingestion.

The local web service binds to loopback and applies Host/Origin and session-token checks. Query topics, model choices, context lifetime and exported results are bounded. These controls and exact-paragraph verification reduce risk but do not establish universal security or semantic correctness. Keep Ollama local; do not expose it through a public tunnel.

Source-update comparison and local review records are offline and proposal-only. They do not activate excerpts, renew approvals or fetch pages. Follow the [source-update policy](docs/source-update-proposals.md) and [source proposal administration guide](docs/source-proposal-administration.md). Historical raw-HTML processing remains an unresolved assignment-compliance concern; excerpt filtering alone does not establish that no personal data was received.

## Tests and evidence verification

### Offline evaluation harness

Run the full offline suite from the repository root:

```powershell
python -B -X utf8 -m harness.offline_tests
```

The harness blocks real sockets and DNS while discovering `eval/test_*.py`. It needs no model, credentials or municipal network access. To retain a new log, supply an unused path:

```powershell
python -B -X utf8 -m harness.offline_tests --output output/NEW-offline-tests.txt
```

For direct unittest discovery, the established command is `python -B -X utf8 -m unittest discover -s eval -p 'test_*.py' -v`; prefer the harness when whole-suite network blocking is required. Test pass rates are not estimates of factual accuracy or general reliability.

### Verify existing Compulsory 2 evidence

```powershell
python -B -X utf8 comp2/verify_package.py --evidence-only
```

Evidence verification is the default; `--evidence-only` remains a compatible explicit choice. The verifier reads existing evidence without invoking Ollama or fetching sources. All hash, manifest, copy-integrity, bilingual table, source-provenance, saved-output and security-pattern checks are retained. Fifteen evidence/security checks are separate from Git inspection; the former total of 17 also included two Git checks. Missing or malformed evidence is a failure, never a documentation warning. No historical result is rewritten.

JSON schema `2.0` has independent `evidence`, `worktree` and `report` sections. Consumers of the former flat `checks` output must use the new schema. `evidence.status` reports integrity only. The worktree section lists every tracked modification/deletion, staging state, untracked file and detected rename/copy, including its original path. Worktree changes always produce review warnings; unavailable Git inspection is explicitly `ERROR`. Ignored files are not listed by Git, but manifest-covered evidence is checked independently. No file-path allowlist is built into the verifier.

Use repeated `--scope-path` options to classify a task's repository-relative files or directories. A directory includes its children; a missing directory can be specified with a trailing `/`. Paths outside the repository and parent traversal are rejected. Without a scope, changes are `UNREVIEWED`; with a scope, they are `IN_SCOPE` or `OUT_OF_SCOPE`. Both sides of a rename/copy must be in scope. Every entry has `approved: false`: scope classification never grants human approval.

`--strict-worktree` adds a separate gate: staging, conflicts, changes outside the supplied scope, unreviewed changes or unavailable Git inspection make it fail. A clean worktree passes without a declared scope. For example, the following checks a task limited to two files; any other current changes remain visible and cause the strict gate to fail:

```powershell
python -B -X utf8 comp2/verify_package.py --strict-worktree --scope-path README.md --scope-path comp2/verify_package.py
```

| Exit code | Meaning |
| --- | --- |
| `0` | Evidence passes and no requested gate fails. Worktree warnings or an unavailable non-strict Git inspection can still require review. |
| `1` | Evidence/security failure, or a required verifier/output operation could not finish. Integrity failures take priority over gate failures. |
| `2` | Evidence passes but an explicit strict-worktree/report gate fails; also used for invalid CLI arguments. |

The four report checks are `NOT RUN` by default and in evidence-only mode. Optional `--check-report` retains the legacy structural checks; `--report-source PATH` selects a source explicitly and requires `--check-report`. Without a supplied path, that opt-in uses the old `comp2/report/main.tex` location and reports its absence gracefully. Evidence remains independent of separate report files and report generation. These limited checks do not establish compiled page counts or academic correctness. `submission_ready` and `commit_and_push_permitted` always remain `false`.

The verifier's standard-library regressions can be run separately with `python -B -X utf8 -m unittest discover -s eval -p 'test_package_verifier.py' -v`. The latest full offline run passed 318 tests: the original 282 plus 36 verifier regressions. The historical 282-test results below are unchanged.

An additional archived-evidence audit is available with an unused output path:

```powershell
python -B -X utf8 docs/reports/verify_evidence.py --archive-only --output comp2/evidence/ANOTHER-UNIQUE-audit.json
```

This creates a new audit record; it does not repeat model evaluation or authorize new use of expired sources. Do not run generators over historical evidence. New experiments require separate outputs, their own dates and documented conditions.

## Results, provenance and academic evidence

| Location | Contents |
| --- | --- |
| [resultat/](resultat/) | Historical evaluation package, bilingual analysis, raw logs, stress/failure evidence, figures, token measurements and integrity manifests. |
| [Verified-results report](docs/reports/verified-results-2026-10-23.md) | Methods, historical outcomes, limitations and links to supporting evidence. |
| [comp2/evidence/](comp2/evidence/) | Selected original-byte logs, selection manifest, saved synthetic/real skeleton output and historical command/audit records. |
| [comp2/tables/](comp2/tables/) | Preserved English/Norwegian CSV results and performance summaries, plus the English LaTeX results table. |
| [comp2/figures/](comp2/figures/) | Mermaid/PDF workflow and an existing model response-time figure. |
| [Prompt excerpts](resultat/english/17_prompt_excerpts.md) | Authentic sanitized evaluation instructions; not a complete development transcript. |
| [Prompt log](docs/prompt-log.md) | Sanitized historical prompt summaries, explicitly distinguished from verbatim excerpts. |
| [Decision notes](docs/meetings/) | Recorded implementation decisions, human constraints, corrections and verification history. |
| [Meeting register](docs/meetings/meeting-register-2026-10.md) | Student-supplied October 2026 dates and October 19 agenda; October 27 is planned, not completed. |
| [Historical meeting evidence status](resultat/english/09_agent_changes_meetings.md) | Earlier assessment retained unchanged; date registration does not establish attendance or formal confirmation of minutes. |

The selected 2026-10-23 evidence records 282 offline tests and a 23-case Ollama suite containing expected refusals. The 17 saved positive outputs belong to an earlier archived series, not a rerun of the later suite. These denominators must not be pooled. The retained browser log records desktop, tablet and mobile checks; it does not establish human-rated accessibility. Historical checks are not fresh runs on every later code version.

The recorded performance series completed 14 of 20 planned calls before a thermal stop. See the results package for measured latency, tokens and limits; incomplete samples must not be presented as production capacity. Historical failures and unresolved safety findings remain part of the evidence.

`comp2/run_walking_skeleton.py` is a historical recording script with exclusive output creation; it refuses existing evidence filenames. Use the synthetic CLI above for a check without file writes. `comp2/build_package.py` is a retained one-time generator and may regenerate removed presentation files. Do not run it or the `resultat/` generators over the existing package. Historical audit records describe their original state and are preserved unchanged.

## Known limitations and academic context

Students write their academic reports separately. This repository provides the software, reproducibility instructions and supporting evidence. The [official Compulsory 2 assignment](docs/official-assignment-user-supplied.md), [requirements matrix](docs/assignment-requirements-matrix.md) and [historical final-exam readiness evidence](resultat/english/13_final_exam_readiness.md) remain available for assessment.

The [meeting register](docs/meetings/meeting-register-2026-10.md) records the students' supplied dates and limited agenda information. It does not certify formal minutes or resolve all meeting-evidence requirements. Report formatting and page limits, submission/demonstration dates, a dated milestone plan, complete final-exam requirements, historical HTML/privacy compliance and lawful source reproduction after approval expiry remain matters for student review. Historical assessments remain unchanged and may describe earlier states.

Current limitations include a small reviewed source collection, extractive rather than semantic verification, no completed human usability study, local model availability/cold-start constraints, and no demonstrated global computation kill switch or aggregate token/cost enforcement. Some experimental controls exist only in the evaluation tools. Preserve those distinctions for the final white paper and demonstration.

The repository, code and documentation were assisted by OpenAI Codex under student direction. Students retain responsibility for design, review, interpretation and submitted claims. Do not fabricate prompt history, meetings, survey responses, dates or verification outcomes. Cleaning documentation does not resolve academic requirements or grant permission to publish or merge.

## Repository organization and collaboration

| Path | Purpose |
| --- | --- |
| [SPEC.md](SPEC.md), [AGENTS.md](AGENTS.md) | Scope, acceptance criteria and coding-agent boundaries. |
| [hamar_agent/](hamar_agent/) | Application, source/provider adapters, verification integration, CLI and website assets. |
| [fixtures/](fixtures/) | Explicitly synthetic non-personal examples. |
| [eval/](eval/), [harness/](harness/) | Test cases and execution/evaluation tools. |
| [docs/](docs/) | Technical, source-review, provider, decision and academic context. |
| [comp2/](comp2/) | Functional skeleton scripts, selected evidence, tables and figures. |
| [resultat/](resultat/) | Preserved historical evaluation material. |
| [tasks/](tasks/) | Planned work. |

Use separate feature branches and pull requests for shared integration. Cross-review is currently optional under the independent-component agreement. [powerNeron](https://github.com/powerNeron) owns source approval, fetching, orchestration, CLI and JSON output; [JeppeGs](https://github.com/JeppeGs) owns summarization, LLM integration, evidence verification and evaluation. Coordinate shared interfaces and preserve both students' contribution history. Read `AGENTS.md` before coding; record task goals under `tasks/`, sanitized prompts in `docs/prompt-log.md`, and meaningful decisions in `docs/meetings/`.

Earlier implementation and ownership context remains in the [offline workflow](docs/source-workflow.md), [full-system decisions](docs/meetings/full-system-web-decisions.md), [Ollama integration record](docs/meetings/ollama-integration.md) and [historical integration gate](docs/final-integration-gate.md). Remote writes and merging require explicit authorization under the project workflow.

## User Interface Screenshots

The screenshots below show the Aisha Agent application running locally.

### Homepage and Search Interface

![Aisha Agent Homepage](comp2/appendices/UI/UI_.png)

### AI Response with Source Verification

![Aisha Agent Verified Answer](comp2/appendices/UI/UI_2.png)

The second screenshot shows a source-checked response generated
by the local Ollama llama3.2:3b model. The interface displays
the exact source quotation and a link to the official Hamar
municipality website.

Source quotation verification does not guarantee factual accuracy
or that the information is up to date.

