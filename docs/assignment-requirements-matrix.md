# Compulsory 2 requirements and current readiness

Authority: [the official assignment supplied by the students](official-assignment-user-supplied.md), Abstract and Sections 1-2. This matrix was corrected on 2026-10-26 using the latest read-only offline audit. It distinguishes current software verification from historical measurements and from the students' separately maintained report. Neither this matrix nor a test pass awards a course grade.

- **PASS**: the stated technical requirement or documented fact was verified within the audit scope.
- **PARTIAL**: supporting material exists, but content, scope or student review remains incomplete or unverified. A separate report is not a failure merely because it is absent from GitHub.
- **PENDING**: publication or external confirmation awaits explicit authorization or a later check.

## Documentation split for the current submission branch

The ten-Markdown `main` retains application inputs, context instructions, code, tests, approved-source data and non-Markdown evidence unchanged. Historical result analysis, meeting/decision records, prompt summaries and the two performance Markdown tables are in the complete `archive/exam-documentation-2026` worktree. Historical PASS statements below describe the dated audits, not a successful full-package verification on the reduced main. The unchanged `comp2/verify_package.py --evidence-only` reports missing historical Markdown on main (exit 1); run it in the archive worktree for the original manifest/table checks. This expected failure is not suppressed or counted as PASS. The current application is validated independently by the complete offline suite, synthetic CLI/web demonstration and held-out synthetic case, as documented in README.

The official report requirements are unchanged: a separate English report in the supplied NeurIPS 2025 preprint template, 3-4 main-text pages, the required problem/success/architecture/schedule/risk/repository content, representative coding-agent excerpts of at most two pages, and genuine meeting reports. Archiving repository Markdown neither supplies nor removes these separate submission obligations. The report/PDF has not been verified here.

## Mandatory Compulsory 2 requirements: software and context

| Requirement and authority | Status | Current evidence and exact next action |
| --- | --- | --- |
| Recurring information-work need in Innlandet, Section 1 | PASS | README.md and SPEC.md describe Hamar municipal-service search for residents and others, producing official links and reviewed excerpts. Keep the separate report aligned with this scope. |
| Work as a pair, Abstract | PASS | Existing contribution history and component ownership document powerNeron and JeppeGs. Preserve actual contributions and coding-agent involvement; do not infer equal hours from component counts. |
| No collecting, storing or processing identifying personal information, Section 1 | PARTIAL | Synthetic execution and fail-closed HTML entrypoints are verified. Historical transient HTML processing and the full ignored catalog have not been certified as compliant by this audit. Retain that limitation and seek course clarification if needed. |
| Respect sources and avoid prohibited scraping or unnecessary republication, Section 1 | PASS | Verified current offline runs make no municipal requests. Relevant live HTML retrieval/import paths reject acquisition, and snapshot import rejects before opening the supplied HTML. Existing URL/paragraph approvals limit catalog use; this does not certify historical privacy compliance or authorize new fetching. |
| Fit local language, institutions and context, Section 1 | PASS | Norwegian Hamar service topics, official source references and the independent student-project scope are documented and tested with synthetic cases. This is not a human usability or complete municipal-coverage assessment. |
| One runnable end-to-end walking-skeleton path, Section 2 | PASS | The current synthetic CLI consumes an explicitly labeled fixture and returns two supported claims, citations and no findings. Synthetic inputs are allowed by Section 1; no new real-model run is claimed. |
| Reproduction README, Section 2 | PASS | Root README commands cover Python 3.12, synthetic CLI, mock website, offline tests and evidence verification without private machine paths. All 45 local README link targets resolved in the audit. |
| Context files used by the harness, Section 2 | PASS | SPEC.md, AGENTS.md, synthetic fixtures and source/selection manifests are retained. The real catalog is ignored local data, not supplied by a clone and not currently recreatable through HTML import. |
| Technical minimum 1: input and checkable output | PASS | Fresh synthetic CLI output has source/paragraph IDs, matching claim/evidence text and verification results. Evidence matching is not semantic fact-checking or factual truth. |
| Technical minimum 2: multiple stages | PASS | Loading/eligibility, retrieval where applicable, provider selection, verification, optional bounded correction/re-verification and JSON output are separate stages. Multiple subagents are not mandatory. |
| Technical minimum 3: tools | PASS | Local JSON fixtures, file handling, search index, CLI and local HTTP interfaces provide tool use. New external retrieval is not necessary for the verified synthetic path. |
| Technical minimum 4: an automatic stage | PASS | A single CLI invocation runs the multistage workflow without manual intervention between stages. Human source admission remains outside runtime automation. |
| Reproducible offline evaluation, supporting the Abstract | PASS | The pre-refactor audit passed 282 offline tests. After verifier maintenance, all 318 offline tests passed: the original 282 plus 36 verifier regressions, zero failures/errors, with real sockets and DNS blocked. A separate reserved synthetic search/citation evaluation passed in the pre-refactor audit. These are not factual-accuracy estimates. |
| Systematic testing, stress testing and validation before demonstration, Abstract | PARTIAL | Fresh offline checks and historical stress/failure/browser/model records exist. Preserve their original dates and denominators. Confirm the demonstration plan; fresh real-model inference, visual browser validation and the actual student demonstration were not performed in this audit. |

## Mandatory Compulsory 2 requirements: separate report and appendices

Students write and maintain the report separately. None of the following PARTIAL statuses asserts that the separate report is missing or incorrect; its final content and PDF were not inspected. Repository readiness and report readiness must be assessed separately.

| Requirement from Section 2 | Status | Exact student action |
| --- | --- | --- |
| Submission includes report and walking skeleton | PARTIAL | Deliver the separate report and the reproducible repository through the required submission channel. The skeleton is verified; confirm the final report independently. |
| Problem, recurring need, target users and output | PARTIAL | Verify that all are explicit in the report and agree with README.md and SPEC.md. |
| Definition of success and checkable correctness | PARTIAL | Describe source/excerpt support and refusals; do not equate passing tests or exact text matches with universal factual accuracy. |
| Architecture: context, stages or subagents, automatic parts | PARTIAL | Match the actual implemented workflow and human source-review boundary. Independent subagents are optional, not a minimum requirement. |
| Milestones from submission to demonstration, planned backwards from demonstration | PARTIAL | Confirm the actual submission/demonstration dates and include a dated backward plan. The retained relative D-21 to D template is not a confirmed calendar. |
| Risk assessment and mitigations | PARTIAL | Cover source availability/expiry, local model availability, limited coverage, verification limits and privacy. Distinguish implemented controls from proposed repairs. |
| Repository link | PARTIAL | Include https://github.com/powerNeron/innlandet-agentic-workflows and confirm examiner access to the intended revision. Local origin matched that address; remote access was not checked. |
| Supplied LaTeX template, NeurIPS preprint option, no NeurIPS checklist | PARTIAL | Use the actually supplied NeurIPS 2025 template, include `\usepackage[preprint]{neurips_2025}`, remove the NeurIPS checklist and inspect the compiled PDF. |
| English report; 3-4 main-text pages | PARTIAL | Verify language and compiled main-page count. References and appendices are excluded from this limit. |
| Required appendix | PARTIAL | Include representative coding-agent excerpts and genuine meeting documentation. The appendix as a whole has no stated page limit. |
| Representative coding-agent excerpts, maximum two pages | PARTIAL | Four authentic evaluation instructions are preserved in resultat/english/17_prompt_excerpts.md. Select representative genuine development/correction excerpts as available and verify the PDF limit. docs/prompt-log.md contains summaries, not verbatim dialogue. |
| Meeting reports showing iterative reasoning, decisions and revisions | PARTIAL | Use authentic evidence and student confirmation where available. The meeting register supplies dates for October 19-26 and limited October 19 content; October 27 is planned, not completed as of October 26. Dates alone do not establish the required substantive evidence. |
| References and consistency with repository evidence | PARTIAL | Check source references, dates, denominators and limitations. Section 2 gives no separate reference-count or bibliography-style requirement. Do not pool the 23-case model suite, 17 earlier saved positive outputs and 14/20 completed performance calls. |

Weekly team meetings are strongly encouraged by Section 2; it specifies no minimum count, signatures or attendance format. Technical decision notes must not automatically be relabeled as formally confirmed team-meeting minutes.

## Repository publication

| Item | Status | Exact next action |
| --- | --- | --- |
| Publish the reviewed submission revision to GitHub | PENDING | The latest cleanup and meeting register are local changes. Obtain explicit approval before staging/committing/pushing or other remote writes; then verify the published revision and examiner access. No publication or merge is authorized by this matrix. |
| External GitHub access and CI outcome | PENDING | Confirm remotely only with approval. Local configuration and offline checks do not verify GitHub contents, access permissions or a successful hosted CI run. |

## Reproduce the current verified paths

Run from the repository root with Python 3.12; no packages, credentials, Ollama or municipal requests are needed:

```powershell
python -B -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
python -B -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
python -B -X utf8 -m harness.offline_tests
python -B -X utf8 -m harness.heldout_search_eval
python -B -X utf8 comp2/verify_package.py --evidence-only
```

Run the website separately, reuse an appropriate existing server rather than duplicating its port, and open http://127.0.0.1:8000. The latest audit started the actual synthetic web CLI on a temporary free loopback port with outgoing connections forbidden: the page, portal API, JavaScript and CSS returned HTTP 200. This was a local startup check, not a new visual browser or real-provider evaluation.

The pre-refactor evidence-only audit passed 17 checks and verified 190 original result files; four report checks were explicitly `NOT RUN`. Those 17 included two Git checks. The maintained verifier preserves all 15 evidence/security checks and reports Git inspection separately. Its current evidence-only run passed all 15 checks and verified the same 190 result files; historical results and manifests remain unchanged. Its fixed `submission_ready: false` is not an assessment of a separately maintained report.

Evidence verification is now the default, with `--evidence-only` retained for compatibility. JSON schema `2.0` separates `evidence`, `worktree` and optional `report` results. Documentation updates cannot themselves invalidate intact evidence; manifest/hash or security failures still fail integrity verification. Every Git change, including staging, untracked files and detected renames, is reported. No hard-coded path allowlist remains. Repeat `--scope-path` with repository-relative task files/directories to classify scope, without implying approval. Both paths of a rename/copy are checked. Without scope, changes are unreviewed. Staging remains a reported check; `--strict-worktree` makes staging, conflicts, unreviewed/out-of-scope changes or unavailable Git inspection a separate gate failure. Do not alter evidence or manifests to suppress warnings.

Exit `0` means evidence passes and no requested gate fails, but visible worktree warnings may remain; exit `1` means integrity/security or verifier/output failure; exit `2` means an explicit worktree/report gate failed with intact evidence, or CLI usage is invalid. Git inspection failure is visible as `ERROR`, not clean status; it fails the strict gate but not evidence integrity. Report checks remain `NOT RUN` unless `--check-report` is explicitly requested, optionally with `--report-source PATH`. Separate report absence is not a default verifier failure, and no exit code grants academic or publication approval. See the root README for the full command contract.

Real-source operation additionally needs an existing lawfully obtained eligible local catalog, valid exact URL/paragraph approvals and an installed allowlisted local model. Follow the [root README](../README.md) and [real-source workflow](real-source-workflow.md). The catalog was present but not read in the latest audit; real-mode reproducibility and privacy were not newly certified. Recorded approvals expire on 2026-10-28. Do not extend dates or run legacy HTML-import commands to bypass expiry.

## Current privacy boundary and historical observations

Current code rejects `import-snapshot` before opening the supplied HTML file. `ReviewedFetcher.fetch`, its `_get` seam, `fetch-reviewed --enable-live` and the municipal import entrypoint reject relevant live HTML acquisition paths. Regression coverage, including eval/test_privacy_ingestion.py, remains part of the original 282 tests, all preserved in the current 318-test suite. The former statement that the current snapshot command can still parse supplied HTML is obsolete.

Portal query restrictions, local Host/Origin checks, session ownership, bounded context/results and source/model allowlists remain documented safety controls. Privacy-pattern screening and exact excerpt hashes are defense in depth, not a proof of absence of personal data. Historical receipt/parsing of complete HTML cannot be made compliant by merely retaining non-personal excerpts afterwards. A future source-delivery process must establish a permitted non-personal boundary before acquisition and parsing. No live source renewal is authorized here.

Earlier audits recorded 226 offline tests, a synthetic 1,000-claim adversarial batch and a failed optional local Ollama smoke with `CUDA error: device kernel image is invalid`. A separate historical observation records 229 tests and an HTTP 500 model failure. These observations remain historical and are not today's test count or a diagnosis of the current model runtime. Later historical evidence includes 282 tests, 23 Ollama cases, browser checks and stress/failure records. The latest offline audit repeats no Ollama tests and makes no external requests. See [verified results](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/reports/verified-results-2026-10-23.md), [real-source history](real-source-workflow.md) and the preserved resultat/ evidence package.

Historical raw logs, manifests, sanitized prompt excerpts and decision records remain unchanged. Superseded analysis previously archived locally is not republished or used as assignment authority. The software and documentation were assisted by OpenAI Codex under student direction; students retain responsibility for decisions, review and submitted claims. No meeting dialogue, human correction, experiment or contribution is invented by this matrix.

## Final exam and additional criteria: separate from Compulsory 2

The available official assignment ends after Section 2. It does not establish a complete final-exam rubric. The Abstract supplies semester-wide testing context; it does not make every later user supplement a Compulsory 2 minimum. [Historical final-exam readiness](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/resultat/english/13_final_exam_readiness.md) and the results package retain the outstanding work.

| Later criterion or recommendation | Status | Scope and next action |
| --- | --- | --- |
| Complete final-exam instructions and W40 material | PARTIAL | Obtain and inspect the authoritative material before certifying final-exam requirements. Do not infer missing dates, formats or criteria. |
| Two of four named fault classes, causal failures/repairs/regressions | PARTIAL | Historical user supplement; the official class list is unavailable. Preserve stress/fault evidence and map it only when the actual rubric is supplied. Not a stated Section 2 minimum. |
| Global computation kill switch; aggregate token/cost budgets | PARTIAL | Historical user supplements and known technical limitations, not stated Section 2 requirements. Preserve the negative/limited evidence; any implementation requires a separately scoped task. |
| Permissions and human approval mechanisms | PARTIAL | Existing controls and limitations are documented. Clarify later rubric expectations; do not equate self-attested roles with authenticated reviewers. |
| At least eight genuine meeting reports | PARTIAL | Historical user supplement, absent from Section 2. Keep authentic records and distinguish student-supplied dates from substantive meeting reports; do not fabricate a count. |
| Representative coding-agent evidence for the final exam | PARTIAL | Preserve genuine excerpts, corrections and summaries with accurate provenance. Confirm the final rubric; the Compulsory 2 prompt limit remains two pages. |
| User study, multiple independent subagents or exam Git tag | PARTIAL | Not established as mandatory Compulsory 2 requirements by the supplied text. Keep relevant existing work; do not invent a study or impose a tag/subagent requirement. |

PASS technical checks do not resolve historical privacy questions, certify the separate report, or authorize publication. Those scopes remain explicitly separate.
