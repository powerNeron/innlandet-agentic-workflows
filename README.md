# Aisha Agent - Innlandet Agentic Workflows

Aisha Agent (also named Hamar KommuneAgent in earlier records) is a two-student software project for KIUA-2003 at the University of Inland Norway. It helps residents and others seeking general, non-personal municipal service information for Hamar through independent service-search and AI question-answering forms.

The real-source workflow retrieves reviewed local excerpts, asks a local model to select one complete paragraph, verifies its source and exact wording, and returns an official citation or a refusal. It permits at most one correction followed by mandatory re-verification. This is an extractive prototype: evidence matching establishes traceability, not factual truth, complete municipal coverage or semantic verification of paraphrases.

**Development status:** the walking skeleton, tests and historical evaluation evidence are retained for Compulsory 2 and continued development toward the final exam. This repository is not a completed or approved academic submission.

## Current production policy — request-bound sources (2026-11-12)

Every new source-bearing municipal search/answer/direct run must use a complete,
validated source observation from its own active request. Source admission and
final publication reject a different, completed, aborted or revoked request.
Historical catalogs cannot be production fallback; ordinary chat remains separate.
Invalid/private/unsupported inputs and metadata/control requests do not retrieve
source content or make model calls.

**Real source acquisition is still disabled.** The eight old approvals are not
renewed. Production may start with source identities, but municipal queries fail
closed until concrete network access, a permitted non-personal input format,
current URL/paragraph approval and source rights are resolved. No live observer is
currently configured. No CLI/HTTP flag silently enables it. Synthetic injected
observations prove the control mechanism, not physical official-site freshness.

The immutable request corpus preserves exact approved excerpts and records
`retrieved_at`, optional source `published_at` and HTTP `last_modified` separately.
Unknown dates remain unknown. Public cards hide detailed timestamps and show only
necessary cautions. Source failure publishes no answer and does not claim a new
check. Reset stays outside the lazy answer panel and invalidates conversation
publication; it does not cancel a remote inference or already-admitted operation.

The next section records the **superseded historical policy** and evidence. Its
contents are retained for provenance, not current production instructions.

## Historical runtime policy before 2026-11-12: retained municipal dataset

The owner has explicitly removed expiry as a runtime stop for the **exact eight
existing local source records and 39 retained paragraphs**. This supersedes the
earlier expiry-blocked runtime status described in the historical renewal notes
below. This is **historical access, not renewed approval**: the manifests still
record review on 2026-10-21 and expiry on 2026-10-28, without rewriting history.
After expiry, search results, AI evidence/citations and the existing web UI show
that approval has expired and information is historical, not newly approved or
updated. The source list and JSON provenance also expose that status.

The exception is bound to canonical SHA-256 fingerprints of all eight original
approval records and complete catalog documents. It cannot admit a modified or
unrelated expired dataset. Source identity, content/paragraph/provenance checks,
query privacy checks, exact-quote verification and disabled municipal HTML
acquisition remain in place. No new runtime mode or synthetic fallback was
introduced. `PageApproval.current()` still reports the recorded approval's
actual validity. Historical access has no automatic November 28 shutdown; it
does not change the source approval expiry to November 27.

**Actual validation:** 374 offline tests passed. With scoped application clocks
on **2026-11-20** and **2026-11-27**, the real local catalog loaded all eight
sources/39 paragraphs; every source was searchable and produced an actual
`ollama:llama3.2:3b` answer with zero evidence-verification findings and historical
provenance. There were 16 direct source inferences and two portal AI answers.
The real-source web page returned HTTP 200 on both dates. These are tests run
now with simulated dates, not proof of future machine/model availability or
future factual correctness. See the [sanitized validation record](docs/historical-source-access-validation-20261027.json).

Use the existing web application, with Ollama running and the original ignored
local catalog present:

```powershell
python -B -X utf8 -m hamar_agent.web --real-sources --provider ollama --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Open <http://127.0.0.1:8000>. A Git clone does not include the local catalog.
Historical access is not municipal permission or a legal clearance: the
documented reuse-rights uncertainty remains. The original public-health p1
wording is retained as requested; its adoption wording remains unsupported by
the inspected PDF, and the separately approved correction has not been applied.
Consult the official sources for current facts, particularly dates, fees and
conditions. The PDF correction and a genuine source renewal are separate from
this owner-authorized historical runtime policy.

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

### Source Approval Validity and Extension Request — Instructor Note

The latest owner instruction restores **2026-11-27** as the requested expiry for all eight existing municipal sources. The [original November 27 authorization](docs/source-renewal-owner-authorization-20261027.json) is reused; the [intermediate November 20 decision](docs/source-renewal-owner-authorization-20261027-to-20261120.json) is preserved as historical evidence. Source content and all 39 paragraph hashes are unchanged. Original source review remains **2026-10-21**, and actual active expiry remains **2026-10-28**. The owner authorization is not a substitute for unperformed source/privacy/provenance decisions.

All eight records in [the approval manifest](docs/approved-service-pages.json), and their corresponding entries in [the reviewed selection](docs/reviewed-service-selection.json), carry that original expiry:

| Source ID | Reviewed service | Retained paragraphs | Renewal to 2026-11-27 |
| --- | --- | --- | --- |
| `hamar-sfo` | School-age childcare | 5 | Pending reuse-basis clearance |
| `hamar-byggesak` | Building without an application | 5 | Pending reuse-basis clearance |
| `hamar-folkehelse` | Public-health knowledge base | 4 | Pending reuse-basis clearance |
| `hamar-bibliotek` | Municipal library | 5 | Pending reuse-basis clearance |
| `hamar-kommuneplan` | Municipal community plan | 5 | Pending reuse-basis clearance |
| `hamar-drikkevann` | Drinking water | 5 | Pending reuse-basis clearance |
| `hamar-parkering` | Parking locations and payment | 5 | Pending reuse-basis clearance |
| `hamar-luftkvalitet` | Air quality | 5 | Pending reuse-basis clearance |

**Current renewal outcome: zero renewed, eight pending, zero rejected. powerNeron has confirmed human review and conditional approval; the reuse basis remains unresolved. Controlled activation is implemented but has not been applied to these sources.** Read-only comparison of the existing local catalog against both manifests confirms matching official HTTPS URLs, source identities, paragraph hashes and unique paragraph IDs, combined text hashes, recorded raw hashes and expiry metadata for all eight sources. All 39 retained paragraphs pass the existing limited privacy-pattern screen. Retrieval/index timestamps are recorded from 2026-10-21. These checks establish consistency of the retained material, not current website content, current robots permission or a new privacy clearance. The recorded `no_personal_data` assertion and pattern screen are not a fresh human review; raw-page and robots hashes were not reverified against newly acquired material. No municipal HTML was fetched or imported.

Existing local evidence under `output/final-technical-evidence/` includes a bounded catalog privacy review and `source-renewal-review-20261022.json`. The latter records all eight human renewal approvals as pending, no expiry updates, and an older requested target of 2026-11-30. That historical evidence is unchanged. The new owner authorization is recorded separately; it does not retroactively change the earlier findings or supply a new source/privacy reviewer sign-off.

An extension requires a documented, authorized re-review of each exact source URL and approved excerpt under the [source-review process](docs/source-review-process.md), including privacy, service facts, hashes and provenance. Record the actual review date, responsible reviewer using an appropriate project identifier, affected sources, authorization and resulting expiry only when those steps have really been completed. No qualifying new source/privacy re-review or activation was established in this update. The conditional owner authorization therefore leaves the approval manifests, active catalog and historical evidence unchanged.

The legacy content-change proposal workflow remains non-activating, and expired approvals cannot be renewed through its proposal decisions. A separate owner-controlled unchanged-content renewal path is now implemented in `source_admin.activate`: it validates the recorded owner authorization, exact input bytes, all source reviews and their current sanitized provenance evidence before changing expiry metadata. The owner may personally perform and document the required source/privacy review using the `project-owner` role; no independent municipal or instructor approval is implied. A role declaration without completed checks is insufficient.

To complete renewal, an authorized source reviewer and privacy reviewer must document the exact URLs and paragraph scope, an actual review date, the service-fact checks (including dates, numbers, fees and conditions), privacy eligibility and permitted source/robots provenance. Use project identifiers rather than private personal details, and record an explicit source-specific decision for the requested expiry. Current eligible material must be supplied through an authorized non-personal input boundary; do not fetch raw HTML to fill the gap. Only after those checks may the controlled activation command update approval/selection expiry and active catalog expiry together. It preserves original `reviewed_on` dates, source content, all paragraph/raw/text/robots hashes and retrieval/index timestamps; the actual new review dates and reviewer identifiers belong to the new transaction audit. The existing proposal `decide` command alone cannot renew sources. No production activation or expiry edit has been performed.

Earlier validation on 2026-10-27, before the activation implementation, passed all 318 then-existing offline tests. With the original approvals still current, real-source web startup returned HTTP 200 and loaded eight documents using `ollama:llama3.2:3b`. One bounded real-source CLI call for `hamar-drikkevann` returned one claim with zero verification findings. This exercised the existing 2026-10-28 approvals, not a November renewal, and does not establish factual correctness, fresh source review or all-source model quality. No municipal requests were made, and no historical results were overwritten.

The earlier [implementation validation record](docs/source-renewal-validation-20261027.json) documents the completed 350-test offline run, synthetic workflow, real-source Ollama web startup, municipal search and one evidence-checked AI answer. The actual renewal check still reports eight incomplete human reviews (exit `3`); no production activation was attempted. All eight approval/selection/catalog records agree on **2026-10-28**. These successful software checks do not activate the authorized November target or verify the separate academic report.

The subsequent [technical-completion validation](docs/source-renewal-technical-verification-20261027.json) records 356 passing tests, all technical metadata completed for eight sources/39 paragraphs, and successful real-source startup, search and one Ollama answer. It lists the exact remaining human review fields and source-specific factual assessment items. Provenance file paths and hashes are now populated from real local files, but those files are unchecked review drafts, not approved current-source evidence. Actual expiry remains **2026-10-28** for all eight sources.

### Examiner access on November 20: verified date behavior

The owner supplied October 30, 2026 as the submission date and November 20, 2026 as the required examiner-access date. **The actual project sources are not yet usable on November 20:** all eight still expire on October 28. The [simulated-date validation](docs/source-renewal-date-validation-20261027.json) exercised the actual approval/catalog data and runtime loaders with a test-only scoped clock: on November 20, new loading was refused, already-loaded search returned no results, AI refused for insufficient eligible evidence, and no model generation occurred. November 28 likewise correctly refused expired sources. The system clock and production expiry checks were not changed.

Six new offline regressions separately prove that a genuinely authorized renewal of a synthetic temporary test package loads, searches and answers on November 20, includes November 27 itself, and refuses new startup and already-running search/AI on November 28. Those positive cases are not activation of the eight project sources. The complete suite passes 362 tests. Current-date local Ollama web startup/search/one AI answer also passed under the original October 28 approvals. November examiner access remains blocked until the documented human content/privacy/provenance review is completed and the actual renewal transaction succeeds. No fresh official-page check was performed: the approved workflow still has no authorized non-personal delivery boundary for new raw HTML acquisition.

An intermediate owner target was **November 20 inclusive**; that dated decision and its validation remain historical evidence. The existing workflow accepts that target without code changes. Its check still returns exit `3` for all eight missing human reviews. Actual records were checked with simulated November 20 and November 21: both refuse startup, return no eligible search evidence and refuse AI before model generation because the records still expire October 28. This verifies expiry enforcement, not the requested November 20 availability. Current-date local Ollama source loading, search and one verified AI answer passed. The current owner-decision record lists every missing review/attestation field; the old November 27/28 regression evidence remains unchanged historical evidence.

### Official-source comparison and remaining review decisions

The [actual official-source observations](docs/source-review-official-observations-20261027.json) compare all 39 retained paragraphs: 38 match the official rendered text after whitespace/link normalization. All eight URL views were available, but provider-reported crawl ages range from today to two months, so this is not proof of live page-body identity for every source. No HTML was imported into the knowledge base and no personal contact details were copied into project evidence.

One paragraph remains unresolved: `hamar-folkehelse:p1` says the document was **adopted** on February 21, 2024. That statement was not located in the official page view. The linked official PDF instead says it was **treated by the municipal council on 21.02.2024**. Treatment is not automatically evidence of adoption. Supply the actual adoption/source evidence or make a separately reviewed correction; do not certify this paragraph unchanged merely from the date match. Parking paragraph p4 belongs to **zone 3211**, not every parking location.

A direct HTTPS observation of robots.txt on 2026-10-27 returned HTTP 200 and SHA-256 `52b871e73c993dd13ffb8bb1760cddf1bf5ce5eb4175d31234d6f474b2a0adfc`, different from the historical pinned `b05e0051ef9bb54c62b82ed2dd8880438ff2a3032d0ffb40009eac5e965df6fd`. The observed policy allows all eight paths for the checked project/research agents with a five-second minimum interval. This is a robots-access observation, not a reuse license or privacy guarantee; preserve the historical hash and explicitly review the new observation rather than relabelling it as unchanged.

The local worksheet contains these findings. powerNeron has since supplied a project-owner review declaration and conditional approval, recorded at the actual UTC decision time in ignored local audit records. This does not establish unresolved reuse rights or activate the PDF correction. No November activation or production expiry change has been performed.

### Owner-controlled renewal: review, check, activate

**Latest rights assessment (2026-10-27; 367 offline tests passed):** powerNeron has expressly confirmed
human review and conditionally approved continued use, including the proposed
public-health correction supported by the official PDF. The remaining issue is
the documented reuse basis, not another owner authorization. The
[rights assessment](docs/source-reuse-assessment-20261027.json) distinguishes
public access, copyright, privacy and publication. No applicable municipal
licence or source-specific statutory clearance has been established for all 39
verbatim excerpts. Local inference, short length, attribution and academic use
alone do not establish that clearance. No source permission flag has been
invented; actual expiry remains **2026-10-28**, with **0/8 renewed**. Earlier
statements about pending owner review above describe the earlier review state.
The approved public-health correction is prepared locally but is not active:
its PDF provenance differs from the existing exact HTML-source approval.

For explicit navigation without loading any municipal text, run:

```powershell
python -B -X utf8 -m hamar_agent.exam_links
```

This separate, offline **link-only examination mode** lists eight official
reference URLs with project-authored topic labels. It reads no catalog or
approval files, fetches nothing, does not call Ollama and makes no current
service-fact or source-approval assertion. It is never selected automatically
when real mode fails. Follow the links manually for current municipal guidance.
It is not a successful November real-source AI test. A future fact-answer mode
would require separately reviewed fact-only inputs; this command does not
relabel the existing verbatim catalog as free-to-reuse facts.

This is an offline, all-or-nothing renewal of the entire authorized source set, not content admission. No source is changed if any review is missing or rejected. All required human review and provenance observations must be on the activation's current UTC day, not in the future. A project-owner review is a local attestation; the tool does not authenticate identity or independently establish the truth of the review. Protect the local files and audit directories accordingly.

Prepare an unchecked review draft, using a new output filename in an existing directory:

```powershell
$renewalInputs = @('--owner-authorization', 'docs/source-renewal-owner-authorization-20261027.json', '--approvals', 'docs/approved-service-pages.json', '--selection', 'docs/reviewed-service-selection.json', '--catalog', 'output/municipal-catalog.json')
python -B -X utf8 -m hamar_agent.source_admin prepare-renewal @renewalInputs --output output/source-renewal-review-20261027.json
```

Preparation does not perform a human review: every decision is `pending`, every check is `false`, and review timestamps/identifiers are empty.

Automatically complete the verifiable local metadata before the owner reviews it. Use a new technical-evidence directory:

```powershell
python -B -X utf8 -m hamar_agent.source_admin complete-renewal-technical @renewalInputs --reviews output/source-renewal-review-20261027.json --output-dir output/source-renewal-technical-20261027
```

This verifies all eight source bindings and 39 paragraph hashes, records eight separate technical checks per source, creates actual hash-bound provenance draft files, and fills their relative paths/digests in the review JSON. It preserves the original draft as `review.before.json` and creates a local `owner-review-items.json` containing the exact retained paragraphs and assessment items. These ignored local files are not published. It never sets human decision/check/identity fields, invents source-observation timestamps or silently rebinds a changed reviewed file. The existing local draft has now been technically completed this way; all eight human decisions remain pending. Missing provenance file paths and hashes are therefore no longer the blocker. For **each of the eight source entries**, the owner must:

1. Actually review the exact URL, unchanged retained paragraphs, current service facts, privacy eligibility and permitted source/robots provenance. Use authorized non-personal material; do not acquire/import raw HTML. If hashes, paragraphs or provenance differ, this expiry-only path must refuse the record; a separate content-admission process is needed.
2. Complete `decision` (`approve` or `reject`), `reviewer` (a GitHub-style project identifier), `reviewer_role` (`project-owner` or `source-and-privacy-reviewer`) and the genuine timezone-aware `reviewed_at`. Set the seven named `checks` to `true` only for checks actually completed; leave missing checks false. The same owner may perform the combined review without claiming independent approval.
3. Open the provenance draft file created by technical completion (or copy `provenance_template` into a separate sanitized `.json` file beneath the review file's directory if that step was not used). Preserve the source/URL/paragraph/hash binding. Set its actual `observed_at`, and complete its four `checks` only after verifying current service information, source permission, the non-personal input boundary and original hash provenance. The required `input_boundary` is `authorized_non_personal_material`. No raw document, personal data or credentials belong in that evidence file.
4. Set `provenance_file` to that file's forward-slash relative path and `provenance_sha256` to its SHA-256 after editing. For example, `(Get-FileHash -LiteralPath output/REVIEWED-source-provenance.json -Algorithm SHA256).Hash.ToLowerInvariant()` computes the digest; it does not perform the review. Do not alter the draft's authorization/input hashes, target expiry, source IDs, paragraph IDs or content hashes. Evidence observation must precede the review on the same UTC day.

Inspect eligibility without changing the manifests:

```powershell
python -B -X utf8 -m hamar_agent.source_admin check-renewal @renewalInputs --reviews output/source-renewal-review-20261027.json
```

Exit `0` means eligible, not activated or academically approved; `3` means blocked with per-source missing checks/fields; `2` means invalid inputs or an operational failure. Only after a successful check, stop the application and use a new transaction directory:

```powershell
python -B -X utf8 -m hamar_agent.source_admin activate @renewalInputs --reviews output/source-renewal-review-20261027.json --transaction-dir output/source-renewal-transaction-20261027 --confirm 'renew 2026-11-27' --application-stopped
```

This command acquires an exclusive lock and preserves byte-identical original files, proposed files, owner authorization, reviews and provenance evidence in that transaction directory. It verifies all input bindings, stages schema-valid data, changes only the three expiry fields, verifies the resulting bytes and writes `COMMITTED.json`. Handled partial-write/audit failures restore the original bytes; unsuccessful rollback leaves a lock and recovery journal. A stale review, changed input, reused transaction, unexpected concurrent modification or rejected privacy decision cannot be silently accepted. Keep all transaction directories as evidence; restart the application only after successful commit verification.

Three separate filesystem replacements are **not crash-atomic**. Keep application processes stopped during activation. After a crash/interruption, inspect `PREPARED.json` and the final marker before restarting. For an uncommitted prepared transaction with its matching lock, verified recovery restores originals without changing content or historical audits:

```powershell
python -B -X utf8 -m hamar_agent.source_admin recover-renewal --transaction-dir output/source-renewal-transaction-20261027 --approvals docs/approved-service-pages.json --selection docs/reviewed-service-selection.json --catalog output/municipal-catalog.json --application-stopped
```

Recovery refuses committed transactions, mismatched paths/hashes and unknown concurrent edits. A failure before `PREPARED.json` needs manual inspection of the untouched inputs/staging directory and lock; do not delete locks or edit manifests blindly. The retained original files and existing historical manifests are never rewritten to make an audit pass. Historical copies retain their old expiry intentionally. After a genuine activation, README status must be updated from the committed audit; today all eight remain at 2026-10-28.

Runtime validation accepts a recorded approval only from its review date through its expiry date, inclusive, using the system date. The application must continue refusing expired, missing or ineligible sources; indexed expired documents are excluded from search. The synthetic CLI/web demonstration and offline tests remain available independently of municipal-source approval or Ollama. The project does not automatically fetch or approve municipal website content, renew approvals or download models. Raw HTML acquisition and snapshot import remain disabled.

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

Content-update comparison and its legacy decision records remain offline and proposal-only. They do not activate excerpts, renew approvals or fetch pages. The separately gated owner-controlled expiry renewal below does not enable content imports or network retrieval. Follow the [source-update policy](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/source-update-proposals.md) and [source proposal administration guide](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/source-proposal-administration.md). Historical raw-HTML processing remains an unresolved assignment-compliance concern; excerpt filtering alone does not establish that no personal data was received.

## Tests and evidence verification

### Offline evaluation harness

Run the full offline suite from the repository root:

```powershell
python -B -X utf8 -m harness.offline_tests
```

The full offline suite passes **362 tests**, with zero failures or errors: the existing 318 plus 44 unchanged-content renewal regressions. This includes 36 package-verifier regressions using temporary synthetic packages. These results do not certify live Ollama operation or authorize municipal-source use. The synthetic web demonstration above uses the mock provider and remains runnable without source approvals.

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

The 36 verifier regression tests create their own temporary synthetic packages and remain part of the 362-test active offline suite; they do not require the removed historical Markdown. Run them separately with `python -B -X utf8 -m unittest discover -s eval -p 'test_package_verifier.py' -v`.

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

## Final Exam run controls and synthetic scientific evaluation

The application now reserves a shared **generated/output-token allowance** before
each Ollama/OpenAI call, including the single correction. Defaults per run are
1,400 reserved output tokens, 64,000 UTF-8 prompt bytes and two generation calls.
The prompt bound includes system instructions, source context and correction
feedback. Reservations are not refunded after failed or ambiguous calls. They
are not measured token usage, total input/output tokens or a billed-cost cap.
Actual token usage and monetary cost remain unknown in mocked evaluations.

Trusted process variables `HAMAR_RUN_OUTPUT_TOKENS` (32–8192),
`HAMAR_RUN_INPUT_BYTES` (1024–1000000) and `HAMAR_RUN_SECONDS` (0.01–180; default
90) configure these limits. Invalid values fail closed. HTTP requests cannot
override them. Nested stages share the original allowance; independent requests
receive separate state.

The measurable stop condition is expiry of the run's monotonic deadline, budget
exhaustion or unavailable bounded-worker capacity. Provider waiting returns a
safe error; no further correction or result/context publication is permitted.
The web publication lock checks the same run state after serialization. There
are at most four generation/cleanup workers per process; an abandoned worker
keeps its slot until it actually finishes. Close intent is registered before
cleanup starts, preventing generation on the same closing client. Active-owner
close is deferred to its owning worker; nested SDK close reuses that worker.
Otherwise cleanup waits at most 0.1 seconds and may be skipped when all slots
are occupied. Closed clients require replacement. A blocked dependency is
released only after the caller returns in the synthetic deadline experiment.

This is **caller abandonment, not remote inference cancellation**. Existing
provider output limits/timeouts still matter. Synchronous source loading,
verification and serialization have checkpoints but are not forcibly preempted;
this is not a universal hard runtime bound. The 50 ms deadline and 750 ms ceiling
used in tests are an experimental threshold and scheduling tolerance. Web reset
also does not cancel inference. Host Codex/MXC filesystem isolation remains
unverified; application source admission and absence of model shell/file tools
do not establish an operating-system sandbox.

No new dependency is needed for the normal application or numerical campaign.
From the project root, use **new output paths** for every run:

```powershell
New-Item -ItemType Directory -Path output -Force | Out-Null
python -B -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
python -B -X utf8 -m harness.offline_tests --output output/exam-offline-NEW.log
python -B -X utf8 -m eval.evaluate_verification --final-exam --output output/exam-campaign-NEW --regression-log output/exam-offline-NEW.log
```

The optional `--plots` flag uses an **already installed** Matplotlib with Agg.
Set `MPLCONFIGDIR` to a project-local cache before using it; no package is
installed by the campaign. Its output directory must be new and inside this
project. The original no-argument verifier scorecard remains available.

The fixed campaign runs both existing adapters with scripted responses and
compares a one-call refusal policy with bounded two-call correction. It covers
typical/boundary/rejected queries, full-paragraph/citation checks, output budget
and publication stops. The two selected official stress classes are **input
perturbation** (injection actually present in synthetic source context) and
**dependency failure** (outage, throttling, malformed/silently wrong output and a
blocked call). Raw responses, stage traces, reservations, actual scripted call
counts and fresh recovery requests are retained in `raw.jsonl`.

`metrics.json` defines each formula and denominator. T1–T8 CSV tables distinguish
case checks, task completion, source grounding, query confusion, controls,
stress, recovery and limitations. Undefined rates remain null. P95 uses nearest
rank, `sorted_latency[ceil(0.95*n)-1]`; latencies describe this synthetic harness,
not live model speed. Recovery requests are counted separately from primary
cases. No real-provider comparison, semantic truth, human rating or general
prompt-injection resistance is inferred from scripted outputs. Students must
complete the separate qualitative review sheet themselves.

The chapter-only English plan is in `final_exam/report_outline.csv`; it allocates
7.5 planned main-text pages and lists evidence and missing human contributions.
It is not a white-paper draft. The supplied NeurIPS 2025 preprint template,
genuine corrected/challenged prompt excerpts, a complete raw evaluation run,
eight authentic meeting reports and actual demonstration feedback remain
student-controlled submission requirements. Do not tag, publish or submit
without explicit authorization.

## Final local validation and remaining submission work

Bounded genuine-provider checks and the application capability/publication gates are
documented in [provider configuration](docs/provider-configuration.md#bounded-genuine-provider-validation).
The existing smoke harness now exercises the strict Aisha workflow with genuine
local Ollama inference and explicitly fictional context. It preserves the generic
synthetic CLI and does not read the ignored municipal catalog or fetch a source.
OpenAI has a presence-only preflight and a separately gated single-call procedure;
no live OpenAI request or installation is authorized by the test instructions alone.

Evidence from 2026-11-11 is in
`output/aisha-final-validation-9f90a3bcd57f4388b1a7bc47074c93e5/`:

- `final-offline-suite.log`: 425 offline tests, zero failures/errors; sockets and DNS blocked.
- `campaign-reviewed/`: all 56 scripted scenario checks, 20 fresh recovery requests,
  T1–T8 tables, metric formulas/denominators, raw outputs and SVG/PNG figures.
- `live-ollama-reviewed/`: three successful actual `llama3.2:3b` requests with exact
  fixture citations and three correct no-model negative outcomes. Numeric usage is
  reported by Ollama; this small sample does not measure municipal truth or quality.
- `clean-reproduction-reviewed.json`: normal CLI, original verifier scorecard and final
  campaign all exit 0 in a plain project-local delivery copy containing code and
  synthetic context, without Git metadata, credentials, municipal catalog or prior
  outputs. This is not a fresh Git clone, clean OS install or host-isolation test.
- `loopback-integration-reviewed.json`: nine actual HTTP integration checks against
  an ephemeral loopback server, using the existing synthetic mock workflow. UI assets,
  owner export, refusal of another token and reset behavior pass; the server stops.
- `review-counterexamples.json`: two independently identified smoke-harness defects
  reproduced against the exact pre-fix hash, then covered by passing regressions.

The evidence is local/ignored and has not been published. Preserve it explicitly
with the selected submission evidence; a repository URL alone will not deliver
ignored logs. Re-run the commands above to produce a new independent run. Historical
395-test and 416-test snapshots and their review evidence remain preserved.

The requirements matrix retains unresolved human and submission obligations:
source/privacy/reuse clearance, qualitative assessment, authentic demonstration
feedback, eight genuine meeting reports, prompt corrections/challenges, the supplied
English NeurIPS preprint template and student-written 7–8-page main text. The existing
chapter outline is unchanged. No public repository readiness, tag, final paper or
submission approval is inferred from passing technical tests.

## Separate general AI chat

**Chat med Aisha** opens first, with Norwegian conversation bubbles, a robot avatar, bounded
follow-up history, reset, loading and explicit retry alongside the existing
**Kommunal informasjon** mode. It preserves the municipal verification workflow.
General chat is visibly AI-generated and unverified. No municipal document or
municipal conversation is attached automatically. Use non-personal content only.

Choose an installed local Ollama model or a separately authorized OpenAI model.
OpenAI is never selected as a paid fallback. Both paid chat and optional web search
have separate server gates, default OFF. Search citations are displayed only from
actual completed search-tool annotations; they are not municipal approvals.
See [chat setup, limits and the first bounded API test](docs/provider-configuration.md#chat-med-aisha-ai--separate-general-conversation).

Use `.\.venv\Scripts\python.exe` for this project's environment, detected as
Python 3.13.7. The approved SDK installation is recorded in the setup update below.
The prepared genuine OpenAI smoke makes at most one call/512 output tokens and no
search, and must not run without explicit spending approval for the chosen model.
The key stays in the user's terminal/backend environment, never in Codex or frontend
code. No genuine OpenAI call has been made for this batch.

Evidence is retained in `output/aisha-chat-1ff51a8921d2405e9f2fcd5424fe6f8d/`.
Backend/offline tests, deterministic Node UI behavior, actual mocked HTTP checks
and a genuine local Ollama chat smoke are distinguished. Chrome startup failed
before rendering, so mobile/desktop rendering and actual accessibility-tree results
for this new mode remain unverified. The guide includes the synthetic browser
command for the user to run without paid calls. Prior exam evidence and the report
outline remain unchanged; this addition is not a final-paper draft or submission.

### OpenAI setup update — 2026-11-11

After explicit owner approval and a missing-SDK preflight, official OpenAI SDK
**2.54.0** was installed only in the project's `.venv` (Python 3.13.7). This supersedes
the earlier pending-installation note. `pip check`, six installed-SDK offline cases,
34 chat methods and all 459 offline regressions pass. No genuine OpenAI call was made.

The selected first model is **`gpt-4.1-mini`**. The public `.env.example` is a reference
only, with paid chat and web search OFF. Set the non-secret model variable in the
user's existing PyCharm terminal; do not move or print the temporary key. See the
[model-specific setup and one-call plan](docs/provider-configuration.md#sdk-installed-first-model-prepared-2026-11-11).
The proposed test is one request, 512 output tokens, 2048 prompt-text bytes and 20 seconds,
without retries or search. It still requires separate spending approval; these
limits are not a verified monetary billing cap. Application code, earlier review
evidence and the original Ollama/municipal budgets remain unchanged.

### Friendly interface and manual model choices — 2026-11-11

The main navigation is **Chat med Aisha / Kommunal informasjon**. General chat has
left/right bubbles, a robot avatar, keyboard-scrollable history, suggested prompts
that only fill the composer, a rounded send control, typing feedback, **Ny samtale**
and explicit **Prøv igjen**. Municipal search, verified excerpts, citations and
recorded source dates remain in the municipal mode. Raw JSON, model IDs, request
budgets and technical answer details stay out of the ordinary interface; existing
authenticated exports and CLI evidence remain available separately.

Only an installed, allowed **Lokal AI (Ollama)** can be selected automatically.
An activated OpenAI option requires a manual choice. If only OpenAI is available,
the selector starts empty. Disabled OpenAI is explained as an optional feature,
not a failure of local chat. Configuration is not proof of working connectivity.
`gpt-4.1-mini` remains the reference cloud model. A separately authorized advanced
choice can be prepared in backend settings; no advanced model is named or activated
by default. See the [configuration guide](docs/provider-configuration.md#manual-advanced-chat-model-default-off).

Start the existing application from the project root, with Ollama running and the
existing approved local catalog available:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.web --real-sources --provider ollama --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Open **http://127.0.0.1:8000**. Restart an older running server first. With no approved
catalog, use the same application in explicit fictional demo mode instead:
`.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.web --demo --provider mock --port 8000`.
The demo's municipal answers are synthetic; it does not fetch municipal pages.

This patch's commands, exact source hashes, complete test logs and failed browser
startup log are retained under `output/aisha-friendly-ui-826d3947a1b548b180668d1055f884f2/`.
The owner's reported completed API call is user-confirmed, not a newly observed
experiment. No paid call or live search was performed by the agent. Browser rendering
still needs a successful user-side check; Node DOM tests do not establish visual
or screen-reader correctness. These changes do not establish exam submission readiness.

### Category, chat welcome and safety corrections — 2026-11-11

Municipal mode retains all eight working topics and the official service-menu link.
Circular icons sit above their labels in a centered four-column/two-column layout.
The same local/cloud chat welcomes users with a robot and four icon suggestions:
**Forklar et tema**, **Hjelp meg å skrive**, **Hjelp med læring**, **Still et spørsmål**.
Each suggestion only fills/focuses the composer; sending remains an explicit action.

The configured `gpt-4.1-mini` option is shown as **GPT-4.1 mini**. Its label distinguishes
configured settings, owner-disabled paid access and a provider failure observed in
this page's last attempt. Refresh alone does not prove recovery; a successful explicit
retry clears that failure state. Disabled options remain visible but cannot be used.
Configuration is not verified connectivity. Ollama remains the automatic default;
paid authorization and search stay OFF unless separately approved by the owner.

Chat screening checks a separate NFKC-normalized copy, removes format/default-ignorable
markers and recognizes additional English name/contact signals, on both messages and
replies. Accepted original text is preserved. This heuristic can miss personal data
or reject benign text; it is **not** general identity/PII detection or a privacy guarantee.
Use non-personal content only. Search permission is rechecked before client construction,
before generation and inside the OpenAI worker before activating a search tool.
Revocation prevents a not-yet-dispatched search; it cannot retract an already sent request.

New raw tests, baseline/repair counterexamples and the frozen review patch are under
`output/aisha-security-categories-e897c14aa51241309b834645af00dc80/`.
Chrome still fails before DevTools startup; actual mobile/desktop rendering remains
unverified. No paid request, live search, dependency installation or credential inspection
was performed. Prior exam evidence and the report outline remain intact.

### OpenAI in both modes and name-field correction — 2026-11-11

Both **Chat med Aisha** and **Kommunal informasjon → Spør Aisha** now use the same
rounded provider controls: **Lokal AI (Ollama)** and the configured **OpenAI GPT-4.1 mini**.
Disabled cloud choices remain visible with a Norwegian activation explanation.
Only local AI can be an automatic default. Losing a selected provider disables
sending until that same choice recovers or the user explicitly chooses another.

Entering a mode refreshes local configuration metadata without inference or clearing
the query, answer or conversation. Healthy controls hide the recovery refresh button;
it remains available when the selected provider disappears or fails. A normal refresh
does not reset context. An uncertain failed reset must first be confirmed by explicit
reset/recovery before municipal questions can resume. Provider buttons never submit
the question form. Restart the existing server to load the new code.

Municipal OpenAI reuses `/api/answer`, `MunicipalWorkflowService`, whole-paragraph
verification, bounded correction, citations and recorded source-expiry warnings.
It does not use general-chat messages or history. Existing owner-controlled
`HAMAR_OPENAI_ENABLED` and `HAMAR_OPENAI_PRIVACY_AUTHORIZED` gates, exact configured
model, SDK and credential presence are required. Chat retains its additional paid-chat
gate. No flag is enabled by these UI changes. Discovery never reads the key value,
constructs an SDK client or checks cloud connectivity; actual authorized generation
loads credentials only on the backend. A configured option does not prove connectivity.

The shared normalized privacy check now also rejects English name fields with `:`
or `=`, including compatibility-width punctuation. Positive learning requests remain
covered, and AI notices use 13 px. Screening remains heuristic. New raw offline tests,
the failing reproducer, exact patch and independent review handoff are under
`output/aisha-name-fields-67261c1eb80f4bb9a5c5314c56e29af7/`. No new paid request,
live search, installation or browser-rendering result is claimed.

### Public source wording — 2026-11-11

Municipal cards use **Kilde**, **Svar med kilder** and **Fra kilden**. Internal review/
approval statuses and dates are kept in API/export evidence rather than the public
cards. Historical sources instead show: **Opplysningene kan ha endret seg. Se kommunens
nettside for siste informasjon.** Retrieval time is shown only when known; indexing
and approval dates are hidden. Synthetic examples stay explicitly labeled.
Source text, links, backend expiry/admission and refusal rules are unchanged.
The cumulative v2 patch and source-bound test evidence remain in the same evidence
directory; the frozen v1 artifacts are preserved separately.

### Local general-chat quality evidence — 2026-11-11

General chat now uses concise Norwegian instructions, prioritizes the most recent
explicit user topic and supplies only relevant entries from a small vocabulary
reference (SFO, PPT, BPA, DPS). This reference assists the model; it is not live
municipal evidence. Recognized ambiguous abbreviation questions use a clarification
instruction; this does not guarantee model compliance. Context routing is heuristic.
All ordinary answers still come from the explicitly selected provider. General
chat remains fallible and separate from the verified municipal workflow.

Municipal procedural/pricing/deadline questions receive a narrowly scoped,
zero-model-call referral to **Kommunal informasjon**. This application guidance
is labelled separately from model-generated answers, retained in bounded history
and still subject to privacy, authorization, rate, reset and publication guards.
It does not retrieve sources or automatically transfer messages between modes.

Reproduce the opt-in local evaluation from the project root with Ollama running:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m harness.chat_quality_eval --check-only --output output/ollama-quality-check-unique
.\.venv\Scripts\python.exe -B -X utf8 -m harness.chat_quality_eval --enable-local-llm --output output/ollama-quality-primary-unique
.\.venv\Scripts\python.exe -B -X utf8 -m harness.chat_quality_eval --enable-local-llm --suite additional --output output/ollama-quality-additional-unique
.\.venv\Scripts\python.exe -B -X utf8 -m harness.offline_tests
```

Use a new output directory for each run. The harness allows only the installed,
configured local model and loopback Ollama transport; cloud providers/search are
disabled. Primary (13) and supplementary (4) curated cases retain separate datasets,
raw texts, effective prompts, model digest, usage, budgets and worker-cleanup records.
HTTP success and keyword matches do not establish answer quality. Repeated tuning
makes these development cases, not held-out accuracy estimates. One fixed seed/model
does not establish reliability across other models, prompts or users; a fixed seed
also does not guarantee byte-identical replies across executions.

Actual before/after evidence is under
`output/aisha-chat-quality-fd74d11887f34a229b497efb6c10e054/`.
The tested 3B model still gives a wrong first-turn PowerPoint expansion and a flawed
photosynthesis explanation; some clarification questions have awkward Norwegian.
These remain explicit quality limitations. Restart the server and start a new
conversation before checking the new behavior. The separate insufficient-evidence
UI regression uses an actual municipal API refusal and preserves its raw backend
message while showing friendly public wording. No paid request, web search,
dependency installation or Git operation was performed in this batch.


### Request-bound evaluation and delivery — 2026-11-12

Use the project environment from the root. Python 3.12+ and Node.js are required
for the complete Python/UI regression (Node uses built-in modules). Normal
synthetic operation and mocked source/provider comparison need no credentials,
ignored municipal catalog or third-party Python packages. The installed optional
OpenAI SDK is not a cloud authorization; paid calls and web search remain OFF.

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
# Open http://127.0.0.1:8000; stop the foreground demo before reusing this port.
.\.venv\Scripts\python.exe -B -X utf8 -m harness.offline_tests --output output/NEW-offline-suite.log
.\.venv\Scripts\python.exe -B -X utf8 -m harness.request_bound_eval --output output/NEW-request-bound-evaluation --regression-log output/NEW-offline-suite.log
node harness/browser_smoke.cjs --unit
```

All evidence destinations must be new. Evaluation blocks real sockets/DNS and uses
fictional page bytes, approvals and URLs through the actual existing application
routes and provider adapters. Real-schema fixture flags are not claims that these
fictional pages exist or were fetched from Hamar. Historical-index mode is an
explicit in-process evaluation construction, unavailable as a deployed server mode.
This comparison is not a fresh checkout of COM 2/main or a field study.

The final comparison has 28 scenarios, two scripted adapters, two architectures
and two repeats:224 primary executions plus152 post-perturbation restoration checks.
Repeats are not independent users/model samples. With112 primary runs per mode,
historical/new case contracts pass64/112 versus112/112; actual task completion is
16/44 versus20/44. Same-request support is0/64 versus20/20 published responses.
These are scripted fixture outcomes. Correct source quotes are not truth or
usefulness certification; source observations and model dispatches are separate.
No-claim HTTP500 responses cannot pass a rejection test; exact status/code/call
counts, paragraph-ID/text/link association and real recorded receipts are checked.
Recovery statistics exclude fault-free controls and separate actually observed
faults from restoration controls ignored by the historical architecture.

Raw output, T1-T8, formulas/denominators, source hashes, red/green regressions and
independent review snapshots are under `output/aisha-request-bound-668a33baf0354fbc934447d829bdfae9/`.
The authoritative final run is `campaign-final-v2/`; earlier imperfect runs remain.
Byte-accounting corrections and checker mistakes are retained as genuine failures.
Separately, `local-ollama/` records three genuine local `llama3.2:3b` calls against
one fictional request-bound source fixture: three exact fixture answers and no
remaining workers. There were zero official source or cloud calls. This repeated
integration smoke is not a representative answer-quality or model-variance study
and is not pooled with the scripted campaign. `delivery-command-results.json`
records the normal synthetic CLI and original verification scorecard, both exit0,
with sockets/DNS blocked. This is not a fresh-clone test.
Existing earlier plots keep their original datasets. No new figure is claimed:
Matplotlib is absent from this project environment and nothing was installed.
Actual browser rendering/accessibility and a genuine clean clone were not certified.

Production source boundaries: exact approved Hamar URLs only; no model-selected
URLs, crawling, retries/fallback or arbitrary search. Staging caps accepted source
bodies at512KiB each, aggregate body/robots bytes at4MiB and source observations
at8. Source waiting shares the existing four-worker pool, per-tool timeout and
original run deadline. A queued worker rechecks active ownership and approval at
dispatch. Already-admitted blocked work retains its slot until it exits. Real
transport streaming/DNS/TLS/robots-wire-call limits still need implementation and
authorized verification; mock budgets must not be relabelled as live HTTP proof.
Generated-output reservations, prompt-byte limits and at most two model calls are
enforced; these are not a total input+output-token or measured billing guarantee.

Host isolation remains a limitation: application context/tool scoping and prompt
instructions do not establish Windows project-only filesystem reads. No personal
configuration, Windows setting or private file was inspected/changed. Stronger
isolation and synthetic outside-workspace denial tests require separate approval.

Before any real municipal source test, the owner must approve the exact URL scope,
current non-personal paragraph/input format and reuse/privacy conditions. The
documented candidates remain the eight exact URLs in `docs/real-source-workflow.md`;
they are not renewed approvals. A possible first source is the documented
`https://www.hamar.kommune.no/drikkevann/` plus its official robots policy, with no
redirect/crawl or linked-page discovery. This is a proposed access scope only,
not authorization or an existing live transport. Raw HTML may contain personal
information before filtering; source access is not enabled merely by changing dates.

The traceability matrix uses official rubric weights totaling100, without assigning
earned marks. Owner request-bound/UI criteria are labelled separately. The outline
contains only the eleven requested headings/keywords and a7.5-page main-text budget.
Students still provide final prose, authentic meetings/prompt excerpts, genuine
references, demonstration feedback and editorial judgment.

### Prepared submission procedure — NOT EXECUTED

Students first verify the actual public repository URL, `exam/final`, ownership of
all staged changes, the reviewed file hashes and a genuinely clean reproduction.
Any commit is a separate authorized action. Preserve main/COM2, all other branches,
worktrees and unrelated work. A file snapshot review is not a commit/tag approval.

```powershell
# Human checklist only; these Git operations were not run by the agent.
git branch --show-current
git status --short
git diff --check
git show --stat REVIEWED_COMMIT
git tag --list exam
# Only after separate approval and confirmation that exam does not already exist:
git tag -a exam REVIEWED_COMMIT -m "KIUA-2003 final examination"
# Publication is separately authorized:
git push origin exam
```

Never move or overwrite `exam`, especially after the deadline. The English paper
must use the supplied NeurIPS2025 preprint template, omit its checklist and have
7–8 main-text pages. Include the public repository URL and authentic appendices:
prompt corrections/challenges, one raw full evaluation and at least eight genuine
meeting reports. Mandatory demonstration is in weeks46–47; address real feedback.
Submission is via WISEflow on2026-12-03 at11:59AM per the official PDF. No paper,
meetings, feedback, publication, tag or submission is fabricated or executed here.


### Controlled public-source research and OpenAI dispatch repairs — 2026-11-12

Live acquisition is OFF. The existing municipal request-bound workflow remains
fail-closed without a current source observer. General chat now has a separate
approved-source research seam inside the existing backend, for both selected
providers; its registry/observer is absent by default. A web authorization flag
alone cannot enable it. Public chat never falls through to native SDK web search.
No real network request, paid call, installation or Git operation was made.

Research selects among exact server-approved public URLs using reviewed topic
keywords, gets new observations in each active request, verifies URL/body/robots/
date/nonce, compares manually scoped entity/attribute/period/geography/unit facts,
then asks the selected model for one exact excerpt. SDK tools stay OFF. Unsupported
quotes, source conflicts, source outages, invalid dates and revoked permissions
publish nothing and do not extend history. Final publication retains the live
nonserialized request capability under the existing session lock. Municipal service
prices/conditions and their follow-ups refer to Kommunal informasjon; a supplement
is not a municipal authority. Ordinary science/travel questions remain available.

Short elliptical research turns resolve to the latest substantive user question;
new complete topics do not inherit old sources. Current-information classification
is an incomplete heuristic, not general semantic intent detection. With search OFF,
representative weather/currency/current requests get explicit zero-call guidance.
Exact quotation establishes source traceability, not factual truth, entailment,
complete contradiction detection or usefulness. Conflicts require identical reviewed
fact scopes; unannotated semantic conflicts can be missed. Human quality review remains
necessary. No model receives file, shell, private-system or arbitrary-URL tools.

The prepared HTTPS transport is not wired into production. It requires live owner
authorization AND a reviewed full-response non-personal plain-text input boundary.
It rejects mixed/private/multicast/site-local/transition DNS results, connects to a
validated numeric address with certificate/hostname TLS checking, refuses redirects,
compression, authentication and changed robots, and bounds streaming, rate and waits.
Mock DNS/TLS/HTTP tests passed on Python3.12.10 and3.13.7; genuine remote behavior
is NOT VERIFIED. Already admitted blocked I/O can outlive caller abandonment and
retains its bounded worker slot. Prompt instructions do not establish host isolation.

The old HTML excerpt approvals do not prove that a full response is non-personal.
Filtering after receipt is not a no-processing guarantee. Resolve the input/privacy/
reuse interpretation before any activation; do not merely extend expiry dates.
Exact historical paragraph identities are in docs/reviewed-service-selection.json.
The following are proposed review scopes, not renewed or domain-wide permission:

| Source identity | Exact official content URL | Historical paragraph scope | Live status |
| --- | --- | --- | --- |
| hamar-sfo | https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/ | 5 exact hashes | NOT APPROVED |
| hamar-byggesak | https://www.hamar.kommune.no/byggesak/bygge-uten-a-soke/ | 5 exact hashes | NOT APPROVED |
| hamar-folkehelse | https://www.hamar.kommune.no/folkehelse-kunnskapsgrunnlag/ | 4 exact hashes | NOT APPROVED |
| hamar-bibliotek | https://www.hamar.kommune.no/kultur-og-aktivitet/hamar-bibliotek/ | 5 exact hashes | NOT APPROVED |
| hamar-kommuneplan | https://www.hamar.kommune.no/kommuneplan/kommuneplanens-samfunnsdel/ | 5 exact hashes | NOT APPROVED |
| hamar-drikkevann | https://www.hamar.kommune.no/drikkevann/ | 5 exact hashes | NOT APPROVED |
| hamar-parkering | https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/ | 5 exact hashes | NOT APPROVED |
| hamar-luftkvalitet | https://www.hamar.kommune.no/klima/luftkvalitet-i-hamar/ | 5 exact hashes | NOT APPROVED |

The additional policy URL is https://www.hamar.kommune.no/robots.txt. Approve both
the specific page and robots access. First propose ONE source, maximum two GETs,
no retries/redirects/crawl,10s source wait,512KiB page/64KiB robots and at least5s
between starts (or the stricter robots delay), within the90s run. This does not
authorize a request. The existing all-or-nothing request index remains. General
and supplementary source registries remain empty until exact URLs, paragraphs,
facts/period/units, current approval dates and processing rights are reviewed.
No supplemental site or invented feed URL has been activated. The machine-readable
review checklist is in output/aisha-research-readiness-b83678c4/source-access-review.json.

All general OpenAI dispatches now recheck live paid/enabled/privacy authorization,
selected-model/advanced permission immediately before SDK I/O, also with search OFF.
Injecting a client alone cannot bypass these gates; fixture policy overrides are
explicit and used only with mocked providers. Municipal OpenAI generation and
correction require completed with no error BEFORE reading/parsing claims JSON.
Actual red evidence reproduces6 unauthorized dispatch/history cases and8 invalid
completion acceptances; the same repaired regressions pass. Exact controlled-source
verification, local default, one-call chat budgets and no paid fallback remain.

Final current offline regression:556/556 methods,0 failures/errors, exit0.
Targeted research/chat/transport/provider/municipal/run checks:219/219, exit0.
The22-group Node model passes; this is not native browser/AX certification.
The prior224-primary/152-restoration comparison was rerun with status-complete SDK
fixtures and retains its headline counts. The separate new research campaign has
20/20 declared synthetic API contracts; neither is genuine model/source accuracy.
Old source/chat evidence, genuine failures and the earlier552-method run remain.

Reproduce offline preparation using NEW destinations, without credentials:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m harness.offline_tests --output output/NEW-offline.log
.\.venv\Scripts\python.exe -B -X utf8 -m harness.research_eval --output output/NEW-research-preparation
node harness/browser_smoke.cjs --unit
```

The preparation command performs only mocked research, static file/asset/dependency
inspection, and unscored quality-review preparation. It produces32 prospective
purposive cases, not a statistically representative sample or executed study. Two
human reviewers should independently rate correctness, relevance and utility0–2,
record material unsupported claims separately, and discuss uncertainty/Norwegian
clarity. Historical17 local responses have34 empty reviewer slots with raw hashes;
they are development evidence, not current or held-out research quality. No score,
meeting, reference, feedback or report conclusion is invented. The chapter outline
is unchanged: eleven English headings/keywords only; students write the paper.

delivery-inventory.json records an explicit allowlisted source/assets/fixtures
inventory, local static imports and optional/dynamic dependencies. Static coverage
does NOT establish Git tracking, clean-clone execution, public availability or host
isolation. Python3.12+ and Node are needed for full checks; OpenAI is optional
with requirements-openai.txt (tested SDK2.54.0). No install was run. .venv is not
published. output/ is ignored: raw results/manifests require a separately reviewed
evidence export/appendix, with credentials/personal paths excluded from publication
copies while originals and hashes remain preserved. The historical raw archive may
need authentic originals absent from an ordinary clone. No private catalog was read.

Prepared push sequence, NOT EXECUTED: human confirms exam/final/main preservation,
the public repository URL and ownership; reviews exact source/dependency/evidence
allowlists; separately approves a commit; reproduces from an actual clean clone;
Verifier checks that committed revision; human separately approves the explicit
exam/final push. Verify exam does not exist and authorize its immutable reviewed
commit/tag/publication separately. No cleanup, all-branch push or tag overwrite.

```powershell
# Human plan only — NOT EXECUTED; each write needs separate approval.
# git push origin exam/final:exam/final
# git tag -a exam REVIEWED_COMMIT -m "KIUA-2003 final examination"
# git push origin refs/tags/exam
```

The current final static inventory is `output/aisha-research-readiness-b83678c4/delivery-final-v3/delivery-inventory.json`; earlier preparation inventories retain their own source hashes.

Final three-turn boundary correction: municipal admission and research selection share the latest-substantive-user resolver. Water/parking sequences through Og prisen? stay zero-observation/zero-model for both providers. Current source-bound results: `output/aisha-research-readiness-b83678c4/full-boundary-repaired-suite.log`, `output/aisha-research-readiness-b83678c4/baseline-final/`, `output/aisha-research-readiness-b83678c4/research-final/`. Earlier snapshots/results remain immutable.
