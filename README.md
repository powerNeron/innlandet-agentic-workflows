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

Open <http://127.0.0.1:8000>. Run only one server on the chosen port; reuse an existing appropriate server rather than starting a duplicate. In PyCharm, select Python 3.12 and run the module with the repository root as the working directory; do not execute `hamar_agent/__main__.py` as a standalone script.

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

Real mode never silently substitutes synthetic data when its catalog, model or verification fails. See the [real-source workflow and historical test evidence](docs/real-source-workflow.md), [source review process](docs/source-review-process.md) and [provider configuration](docs/provider-configuration.md).

### Portal search and catalog loading

Ordinary municipal search uses `/api/search` over the reviewed local paragraph index and never invokes a model. The independent AI form uses `/api/answer`, performs its own retrieval and sufficiency check, and does not require a preceding ordinary search or reuse its category selection. A new or edited question clears the previous answer/download state. The index uses word-based retrieval and ranking, not semantic/vector search or whole-site crawling. Missing indexed evidence does not mean that a municipal service does not exist.

Follow-ups retain only bounded, volatile topic context and repeat retrieval; previous model answers are never evidence. Reset/model changes clear context. Do not enter personal information. POST bodies and privacy-pattern screening do not guarantee that arbitrary user input contains no personal data. Real-mode refusal must not trigger a synthetic or paid-provider fallback.

For an existing eligible catalog at a non-default path, use the current real-source loading options:

```powershell
python -B -X utf8 -m hamar_agent.web --real-sources --catalog LOCAL_CATALOG.json --approvals docs/approved-service-pages.json --model llama3.2:3b --port 8000
```

Repeat `--catalog` only for individually reviewed eligible catalogs matching the supplied approval manifest. Loading rechecks identity, URL, paragraph hashes, provenance and expiry; it does not acquire HTML or renew approvals. Do not combine real catalogs with `--empty-index` or treat old snapshot-import commands as supported ingestion. No web endpoint can approve sources, upload pages or enable fetching.

### JSON output and file saving

Use `--output` with an unused filename in an existing parent directory, preferably ignored `output/`. Successful CLI saving writes UTF-8 JSON and prints the same result to stdout. Exclusive creation prevents overwriting existing files; handled saving/serialization failures report an error on stderr and exit `2` without success JSON. No parent directories, filenames, retries or backups are created automatically.

Exclusive creation is not atomic completion or crash durability: interruption/write failure can leave a partial new file, and a stdout failure after saving can leave a valid file. Export does not add privacy detection or establish semantic correctness. Review new outputs before sharing; never regenerate historical evidence in place.

## Architecture and boundaries

The application uses Python's standard library, a local search index, local HTTP interfaces and versioned JSON results. Ordinary service search does not invoke the model. The AI form performs its own retrieval and sufficiency checks before invoking the provider.

The runtime stages are:

1. Apply privacy/topic constraints and check source eligibility and validity.
2. Retrieve approved local paragraphs and determine whether evidence is sufficient.
3. Ask the configured provider to select a whole reviewed paragraph.
4. Check paragraph identity, verbatim claim/evidence support and provenance through the existing verifier and strict adapter.
5. Permit at most one correction, re-verify, and return a cited result or safe refusal.

Human source admission precedes runtime. There is no autonomous crawling, source approval or unrestricted shell execution by the model. See the [workflow contract](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/full-system-contract.md), [integration guide](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/full-system-web.md), [summary and verification design](docs/summary-verification.md) and [workflow figure](comp2/figures/aisha-workflow.pdf). JSON export constraints are documented above.

### Privacy and security

Do not collect or process personal data. Public availability is not permission. Use synthetic fixtures for development and explicitly reviewed non-personal excerpts for real operation. Reject uncertain input and treat external source text as untrusted data rather than executable instructions. Source categories based on [Hamar's official menu](https://www.hamar.kommune.no/meny/) do not authorize ingestion.

The local web service binds to loopback and applies Host/Origin and session-token checks. Query topics, model choices, context lifetime and exported results are bounded. These controls and exact-paragraph verification reduce risk but do not establish universal security or semantic correctness. Keep Ollama local; do not expose it through a public tunnel.

Source-update comparison and local review records are offline and proposal-only. They do not activate excerpts, renew approvals or fetch pages. Follow the [source-update policy](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/source-update-proposals.md) and [source proposal administration guide](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/source-proposal-administration.md). Historical raw-HTML processing remains an unresolved assignment-compliance concern; excerpt filtering alone does not establish that no personal data was received.

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

### Active application checks versus historical archive audits

The offline suite and synthetic CLI/web commands above validate the active application. The ten Markdown files on `main` provide current setup, architecture, source-review, provider, assignment and verification instructions. Historical analysis, meeting/decision records, prompt summaries and performance Markdown are preserved in `archive/exam-documentation-2026`, together with the complete original evidence package. Non-Markdown application inputs, tests, approved-source configuration, figures, CSV/JSON evidence and manifests are retained unchanged on `main`.

`comp2/verify_package.py` is an unchanged historical-package verifier, not an application startup requirement. It reads all original manifest files and both historical performance Markdown tables. **On the reduced `main`, `--evidence-only` must report missing historical Markdown and exit `1`; this is not a successful integrity verification and must not be represented as one.** The manifests and checks have not been changed to accommodate the cleanup. Run the full historical verification in the archive worktree instead:

```powershell
# From main's root, using the existing sibling archive worktree:
python -B -X utf8 ../innlandet-agentic-workflows-exam-documentation-archive/comp2/verify_package.py --evidence-only
```

If no archive worktree exists, first obtain the approved archive branch and create a separate worktree with `git worktree add ../innlandet-agentic-workflows-exam-documentation-archive archive/exam-documentation-2026`; do not merge it into main or overwrite an existing directory. This local branch is not assumed to be published. A main-only clone cannot perform a complete historical audit without the archive.

The selected-copy manifest additionally requires the ignored original `output/aisha-heading-encoding-fixed-browser-20261023/browser-check.txt`. An original-byte copy is preserved in both local worktrees, with SHA-256 `4aafbe6eedc58bbc8a58727b798964e72d67680ee141ab106f752621f6c1ce04`. It is not delivered by a normal clone/push. A separately transferred authentic original is needed for that source/copy check on another machine; the retained tracked copy is `comp2/evidence/aisha-browser.txt`. Do not claim a clean-clone full audit without satisfying this dependency. This limitation does not affect application startup or the synthetic tests.

The verifier retains 15 evidence/security checks covering manifests, hashes, selected copies, bilingual tables, provenance, saved outputs and security patterns. JSON schema `2.0` separates `evidence`, `worktree` and optional `report` results. Git inspection reports modifications, deletions, staging, untracked files and detected renames; ignored files are outside Git inspection. Repeated `--scope-path` options classify repository-relative task paths without approving them. `--strict-worktree` makes staging, conflicts, out-of-scope/unreviewed changes or unavailable Git inspection a separate gate failure.

Exit `0` means evidence passes and no requested gate fails; worktree warnings can remain. Exit `1` means integrity/security or verifier/output failure. Exit `2` means an explicit worktree/report gate fails with intact evidence, or invalid CLI usage. Evidence verification is the default; `--evidence-only` remains compatible. Report checks are `NOT RUN` unless `--check-report` is requested, optionally with `--report-source PATH`; these structural checks do not verify compiled page counts or academic correctness. `submission_ready` and `commit_and_push_permitted` always remain `false`.

The 36 verifier regression tests create their own temporary synthetic packages and remain part of the 318-test active offline suite; they do not require the removed historical Markdown. Run them separately with `python -B -X utf8 -m unittest discover -s eval -p 'test_package_verifier.py' -v`.

The separate `docs/reports/verify_evidence.py --archive-only` audit reads preserved historical non-Markdown artifacts and requires a new exclusive output path. Its recorded counts refer to earlier experiments, not new inference. Do not overwrite the existing untracked audit or historical evidence. Prefer running historical tools in the archive worktree. `comp2/build_package.py` and the results generators are historical generators; do not run them to reconstruct main or overwrite evidence, as they can recreate archived presentation files.

The legacy `resultat/audit_package.py --check` also belongs to the complete archive. Even there it has older fingerprint discrepancies for `harness/browser_smoke.cjs` and `hamar_agent/web_assets/app.js`, `index.html`, and `style.css`, all unchanged from the pre-cleanup HEAD. These unresolved discrepancies must not be reported as a successful full integrity audit. The archive's separate 190-file results manifest and evidence-only verifier are distinct checks.

## Results, provenance and academic evidence

| Location | Contents |
| --- | --- |
| Historical results archive | The complete package, including bilingual Markdown analysis, remains in `archive/exam-documentation-2026:resultat/`. Non-Markdown results, logs, figures and manifests are also retained on main; the local directory is not a complete standalone historical package. |
| [Verified-results report](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/reports/verified-results-2026-10-23.md) | Methods, historical outcomes, limitations and links to supporting evidence. |
| [comp2/evidence/](comp2/evidence/) | Selected original-byte logs, selection manifest, saved synthetic/real skeleton output and historical command/audit records. |
| [comp2/tables/](comp2/tables/) | Preserved English/Norwegian CSV results and the English LaTeX results table. Historical Markdown performance summaries are in the archive. |
| [comp2/figures/](comp2/figures/) | Mermaid/PDF workflow and an existing model response-time figure. |
| [Prompt excerpts](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/resultat/english/17_prompt_excerpts.md) | Authentic sanitized evaluation instructions; not a complete development transcript. |
| [Prompt log](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/prompt-log.md) | Sanitized historical prompt summaries, explicitly distinguished from verbatim excerpts. |
| [Archived decision notes](https://github.com/powerNeron/innlandet-agentic-workflows/tree/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/meetings) | Original implementation decisions, human constraints, corrections and verification history; also present in the local archive worktree. |
| [Meeting register](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/meetings/meeting-register-2026-10.md) | Student-supplied October 2026 dates and October 19 agenda; October 27 is planned, not completed. |
| [Historical meeting evidence status](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/resultat/english/09_agent_changes_meetings.md) | Earlier assessment retained unchanged; date registration does not establish attendance or formal confirmation of minutes. |

The selected 2026-10-23 evidence records 282 offline tests and a 23-case Ollama suite containing expected refusals. The 17 saved positive outputs belong to an earlier archived series, not a rerun of the later suite. These denominators must not be pooled. The retained browser log records desktop, tablet and mobile checks; it does not establish human-rated accessibility. Historical checks are not fresh runs on every later code version.

The recorded performance series completed 14 of 20 planned calls before a thermal stop. See the results package for measured latency, tokens and limits; incomplete samples must not be presented as production capacity. Historical failures and unresolved safety findings remain part of the evidence.

`comp2/run_walking_skeleton.py` is a historical recording script with exclusive output creation; it refuses existing evidence filenames. Use the synthetic CLI above for a check without file writes. `comp2/build_package.py` is a retained one-time generator and may regenerate removed presentation files. Do not run it or the `resultat/` generators over the existing package. Historical audit records describe their original state and are preserved unchanged.

## Known limitations and academic context

Students write their academic reports separately. Main provides the software, reproducibility instructions and retained non-Markdown evidence; the archive preserves historical documentation and the complete evidence package. The [official Compulsory 2 assignment](docs/official-assignment-user-supplied.md), [requirements matrix](docs/assignment-requirements-matrix.md) and [historical final-exam readiness evidence](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/resultat/english/13_final_exam_readiness.md) remain available for assessment.

The [meeting register](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/meetings/meeting-register-2026-10.md) records the students' supplied dates and limited agenda information. It does not certify formal minutes or resolve all meeting-evidence requirements. Report formatting and page limits, submission/demonstration dates, a dated milestone plan, complete final-exam requirements, historical HTML/privacy compliance and lawful source reproduction after approval expiry remain matters for student review. Historical assessments remain unchanged and may describe earlier states.

Current limitations include a small reviewed source collection, extractive rather than semantic verification, no completed human usability study, local model availability/cold-start constraints, and no demonstrated global computation kill switch or aggregate token/cost enforcement. Some experimental controls exist only in the evaluation tools. Preserve those distinctions for the final white paper and demonstration.

The repository, code and documentation were assisted by OpenAI Codex under student direction. Students retain responsibility for design, review, interpretation and submitted claims. Do not fabricate prompt history, meetings, survey responses, dates or verification outcomes. Cleaning documentation does not resolve academic requirements or grant permission to publish or merge.

## Repository organization and collaboration

| Path | Purpose |
| --- | --- |
| [SPEC.md](SPEC.md), [AGENTS.md](AGENTS.md) | Scope, acceptance criteria and coding-agent boundaries. |
| [hamar_agent/](hamar_agent/) | Application, source/provider adapters, verification integration, CLI and website assets. |
| [fixtures/](fixtures/) | Explicitly synthetic non-personal examples. |
| [eval/](eval/), [harness/](harness/) | Test cases and execution/evaluation tools. |
| [docs/](docs/) | Current technical, source-review, provider and assignment guides; historical decisions/prompts are in the archive. |
| [comp2/](comp2/) | Functional skeleton scripts, selected evidence, tables and figures. |
| [resultat/](resultat/) | Retained non-Markdown historical evidence; the complete historical package is in the archive. |
| [tasks/](tasks/) | Planned work. |

Use separate feature branches and pull requests for shared integration. Cross-review is currently optional under the independent-component agreement. [powerNeron](https://github.com/powerNeron) owns source approval, fetching, orchestration, CLI and JSON output; [JeppeGs](https://github.com/JeppeGs) owns summarization, LLM integration, evidence verification and evaluation. Coordinate shared interfaces and preserve both students' contribution history. Read `AGENTS.md` before coding; record new task goals under `tasks/` and retain authentic sanitized prompt/decision evidence in the separately maintained submission appendices or approved archive workflow. The historical prompt and meeting records are archived unchanged.

Earlier implementation and ownership context remains in the [offline workflow](docs/source-workflow.md), [full-system decisions](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/meetings/full-system-web-decisions.md), [Ollama integration record](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/meetings/ollama-integration.md) and [historical integration gate](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/final-integration-gate.md). Remote writes and merging require explicit authorization under the project workflow.

### Historical documentation archive

The local branch `archive/exam-documentation-2026` preserves the pre-cleanup documentation at commit `dad5024fda555113ab65233b1d2abdd9c34f09cf`. It is not assumed to be published. For example, inspect an archived document without switching branches with `git show archive/exam-documentation-2026:docs/search-portal.md`. Historical documents describe earlier implementations and test runs; use this README and the current source-review requirements for operation. The two explicitly withdrawn verification-note/final-verification files are deleted in both working trees; earlier Git history is not rewritten.

The manifest-covered `resultat/` Markdown, nine meeting/decision documents, authentic prompt records and retired technical guides remain in the archive. Main retains the ten current Markdown guides and the unchanged non-Markdown application/evidence files. Documentation cleanup does not imply final-exam readiness. GitHub visibility applies to the entire repository, including every pushed branch: an archive branch in a public repository is not private. Verify access and obtain explicit approval before synchronizing either branch; use an approved private remote or private offline transfer if confidentiality is required.

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

