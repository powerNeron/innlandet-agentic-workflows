# Final submission readiness — 24 November 2026

**Not ready for publication or submission.** This is the current evidence map,
not the scientific white paper, a grade, or an independent publication approval.
Historical logs and previous candidate manifests remain historical evidence.

The authority is the complete five-page [official assignment](project_KIUA_2003.pdf),
SHA-256 `4c41b5078656301d3c3aab9893299692fe65337b5261409b7d1c063f1d0fe6e5`.
The existing [requirements register](requirements.csv) contains 105 requirements;
its older evaluation references do not establish acceptance of today's code.

## Work ownership and acceptance boundary

The owner authorizes parallel work with exclusive file ownership. The separate
Verifier writes parser/extraction/relevance code, source diagnostics and their
targeted tests. Implementer owns this file, README, CHANGELOG, the report outline,
the independent web/CI cleanup and request-bound evaluation imports. No one may
approve their own code. Source changes still require a separate read-only review.

The integrated worktree is **not frozen** while either contributor is editing.
Historical whole-worktree manifests cannot approve subsequent documentation,
CI or runtime edits. Create one combined final binding after both handovers;
do not create competing version-named production modules. No commit, push,
merge, reset, tag or file deletion is authorized by this cleanup.

## Current application gate

There is one active application: `python -m hamar_agent.web --enable-live-research`.
Both model adapters use `InternetResearchService`. V5/V6 names under ignored
`output/` identify preserved historical experiments, not alternative applications.
The reviewed-source CLI and COM 2 workflows remain supported interfaces, not
duplicates to remove without checking their callers.

The ordinary-terminal Elverum run retrieved four real HTML documents but returned
HTTP 422 / `research_no_sources`, without model generation. The specific official
article had 39 `form_control_conditions` rejections. The retained evidence does
not identify the qualifying control. The new inspection records closed control
types, ownership and action flags without HTML, arbitrary labels or field values.
A new ordinary-terminal inspection and actual source-backed chat are required.
The current Codex attempt is blocked before HTTP with WinError 10013.

The newer ordinary-source-chat receipt under
`output/aisha-source-trace-20261124-3d9e781c/` is an actual HTTP200 failure,
not a pending network test. Its source-inspection SHA256 is
`40ee1c41c05e056240688ad13e27cb087caff411b690fdc8a14ee731e9eddf9e`.
Both ordinary receipts parsed166events and emitted zero units. The newer trace
identifies the first rejection precisely:40 `unrepresented_annotations`, all
`unrepresented_attribute_text` for `aria-label`. Section node189/owner[1,2]
rejects one unit; node191/owner[1,3] rejects39. One additional row is context-only.
Five procedure-bearing blocks92,93,95,97,106 are present and pass the public
screen; block95 is a lead-in context row. Heading detection is not the missing
step. Thirty-nine decisions also carry the independent [1,3] control barrier.

### Exact source-blocker handover to Verifier

The first failing condition is in `ServiceHTML.annotation_rejection()`:
`if normal(value) not in represented`, where `represented` contains complete
visible heading/group/paragraph components. `_start_metadata()` retained the
section's literal annotation, but `reviewed_html_units()` assembled only visible
components before requiring the annotation to be present verbatim. Thus a safe
accessible section label absent from those components rejects all its descendants
before relevance. The actual label values are not retained in diagnostics and
must not be guessed. Removing all `aria-label` checks would also remove genuine
qualifications and is not an acceptable repair.

Minimal recommended direction: preserve applicable, privacy-screened literal
annotations in the existing owner-scoped qualification/context assembly before
the one canonical annotation check. Keep their original node identity and full
text; they must not silently supply an unrelated service or unverified price
period. Unsafe/ambiguous annotations, unresolved nonempty references and omitted
control conditions must continue to refuse. Do not add an independent bypass
or a service/URL-specific rule.

A focused synthetic API counterexample on the same unchanged source7e467332
uses a normal article with H1 `Frøbytteveiledning`, H2 `Slik søker du` and the
paragraph `Du søker frøbytteveiledning via kommunens digitale skjema.` Both chat
flows return200 and preserve the paragraph without a section annotation. Adding
only `aria-label="Hovedinnhold"` to that section produces422/research_no_sources
and zero model calls in both flows. This is a synthetic positive regression,
not the unknown real attribute value. An unresolved
`aria-describedby="missing-target"` still correctly refuses in both flows.
The focused receipt is `source-annotation-probe.log` in the Implementer component
evidence directory; no actual source HTML or field values were retained.

There is also a separate downstream obstruction: five buttons309,316,323,329,335
taint owner[1,3]. They have controls references to unique but blocked div targets,
no inline event handler and unknown action semantics. Those facts do not prove
that the controls are harmless. Keep the control barrier until their complete
qualifications are safely represented or their non-factual role is established.
Fixing the literal-annotation failure alone does not demonstrate an answer.
No third unchanged PyCharm test is requested: Verifier owns the production fix,
the same ten negative/six English regressions and the next changed-code actual
test. Implementer has not edited the reserved source files.

The grammatical rejection of “You apply by completing the form for this service.”
was reproduced in all six municipality/adapter combinations and repaired. The
ten exact historical wrong-service cases still produce no incorrect verified
answer. These are synthetic API results, not real-source or real-cloud results.
Verifier's source receipts are in
`output/aisha-finalisation-20261124-2f4145eb/`; each receipt states its own hashes
and test boundary. A final full regression and frozen candidate are still required.

Implementer's independent component checks and preserved before-files are in
`output/aisha-project-quality-20261124-fc2508fd/`. They do not certify municipal
coverage or the final combined version. Actual local Ollama inference succeeded
on a fictional grounded source, and a general-chat request returned HTTP200.
The latter used an incorrect name for CO2, so transport success must not be
reported as semantic quality. No paid OpenAI inference was performed.

## All 100 rubric points

Weights below are the assignment's weights, **not points awarded**. No assessment
of academic credit is inferred from a software test count.

| Criterion | Weight | Status | Existing evidence | What remains before acceptance |
|---|---:|---|---|---|
| R01 Problem value and local fit | 5 | PARTIAL | README, SPEC, Norwegian resident flows and three-city pilot | Demonstrate useful real answers; substantiate local value without inventing user research |
| R02 Definition of success | 10 | PARTIAL | requirements register, mechanical checkers and explicit source/municipality/rights gates | Bind measurable success and limitations to the final evaluated version |
| R03 Architecture and decomposition | 10 | PARTIAL | web/chat, router, discovery, bounded retrieval, model adapters and verifier | Put the current architecture and agent/control responsibilities in the paper; old architecture figures are historical |
| R04 Context engineering | 10 | PARTIAL | separate system/user messages, JSON untrusted source data, complete-unit checks and context regressions | Complete independent review and actual-source validation of the corrected context logic |
| R05 Automation and reproducibility | 10 | PARTIAL | canonical CLI, evaluation harness, runtime/source hashes | Successful ordinary run, clean reproduction and exact release binding |
| R06 Evaluation harness quality | 10 | PARTIAL | fixed fixtures, source contracts, request-bound campaign and raw logs | Fresh full final regression on Python3.12/3.13, UI contracts and actual-source results |
| R07 Fault injection and causal analysis | 15 | PARTIAL | input/source injection, dependency outages and original red/green receipts | Explain the two selected official classes and their causal chains in the paper |
| R08 Repair and regression evidence | 10 | PARTIAL | exact ten negatives, six English positives and independent read-only probes | Full regression after the last change and independent review of one unchanged final candidate |
| R09 Novelty of perspective | 5 | PARTIAL | source-controlled municipal guidance, accessibility target and finite trust boundaries | Student argument in the actual paper; no invented field validation or novelty claim |
| R10 Logical argumentation and honest reporting | 5 | PARTIAL | failures, withdrawn candidates, scoped synthetic/actual results preserved | Discuss quantitative results and actual answer usefulness; HTTP200 does not prove correctness |
| R11 Human-in-the-loop control | 5 | PARTIAL | source/transfer/cost permissions, revocation and bounded run controls | Show operator stop/review workflow and discuss residual privacy/source risks |
| R12 Clarity and compliance | 5 | NOT VERIFIED | official register, change log and historical prompt/evaluation evidence | Finished paper, correct template, authentic appendices, demo evidence and final repository/tag |
| Total rubric coverage | **100** | **PARTIAL** | Every weighted criterion is mapped | **No grade or publication PASS assigned** |

## Mandatory delivery gaps

| Delivery | Status | Required evidence/action |
|---|---|---|
| English white paper, 7–8 main pages | NOT VERIFIED | No finished paper located in the project or the inspected linked worktrees; `report_outline.csv` is only an outline. Obtain genuine author material and produce the actual paper |
| Provided NeurIPS 2025 template | NOT VERIFIED | No template/build located. Use the provided template with `preprint`; omit the checklist; verify the rendered main-page count |
| Quantitative and qualitative results | NOT VERIFIED for final version | Historical results exist. Re-run after the last fix; keep failed runs, distinguish mocks from actual models and discuss actual answer usefulness |
| Two chosen stress-test classes | PARTIAL | Input perturbation/source injection and dependency failure/outage/rate limiting are the selected official classes. Use the recorded synthetic protocols and genuine red/green receipts; distinguish absorption from repair |
| Safe operation and stop control | Final verification pending | Check request, byte, time, process and model/cost limits and actual revocation; do not claim a global GPU stop mechanism that is not implemented |
| Prompt excerpts and one complete raw evaluation log | Historical material exists | Select genuine excerpts and one complete final evaluation, bound to the delivered code, without secrets or personal data |
| At least eight authentic meeting reports | NOT VERIFIED | Dated technical notes and an incomplete meeting register are not eight confirmed meetings. Obtain genuine dates, participants, decisions and actions; do not fabricate them |
| Mandatory demo and feedback | NOT VERIFIED | Obtain actual weeks 46–47 demonstration and feedback records; discuss genuine failures and resulting changes |
| Public repository and `exam` tag | NOT VERIFIED | Verify the public URL and exact published commit after authorized publication; tag the reviewed submission commit only with authorization |
| Wiseflow submission | Pending | Official deadline: 3 December 2026 at 11:59. The delivered commit must remain unchanged after the deadline |

No paid OpenAI inference, actual browser/screen-reader evaluation, complete
46-municipality factual coverage or general anonymity guarantee is established.
Only Hamar, Elverum and Gjøvik are active pilots. V-C01 remains OPEN until the
required genuine source excerpts and their answer quality are verified.

## Why the development stalled

The stages have different responsibilities and must retain different contracts:
search nominates URLs; the HTTP layer validates transport; the parser preserves
whole content and qualification context; relevance matches the requested service;
publication verifies the exact supported quotation, provenance and transfer rights.
A parser label is not factual approval, and a URL match is not service support.

Three observed failures demonstrate the boundary problems. The outer page form
removed prose before relevance; the independent Du/You and lexical positives
bypassed purpose validation; omitted-control protection then refused39units in a
real source. The first two have finite before/after evidence. The exact control
behind the third still needs real-node diagnostics; its source cannot be guessed.
Annotation/reference identity must survive between parser and admission, even
when two labels have identical text. Verifier owns those fixes.

Synthetic fixtures often use a small main/p shape, while real CMS pages contain
wrappers, widgets and annotated headings. Mechanical quote checks also cannot
assess semantic truth: the local free-chat CO2 terminology failure illustrates
this. The practical repair process is one representative actual journey before
coverage claims, plus positive and negative fixtures that preserve the diagnosed
DOM/context structure. Do not remove layered security gates merely because some
checks overlap; share a purpose rule across acceptance paths and keep transport,
privacy, conditions and transfer checks independently testable.

## Independent component evaluation, 24 November

These observations concern Implementer's cleanup, not a final whole-project PASS.

| Check | Observation | Boundary |
|---|---|---|
| Web/provider/Ollama/runtime/exam-link tests | 113/113 on Python3.12 and3.13 | Synthetic transports and mocked cloud; no paid call |
| Run control/evaluation/source-update checks | 64/64 on Python3.13 | Synthetic fault injection, revocation and budget controls |
| Node UI contracts | 39/39 | Deterministic DOM; not browser rendering |
| Actual HTTP startup and local assets/options | 6/6 HTTP200 | Synthetic service, zero inference and zero public retrieval; verifies the served canonical image |
| Real local Ollama with fictional reviewed source | 4/4 smoke cases; one genuine inference | Correct exact source quote; not municipal factual validation |
| Real local general-chat API | HTTP200; one genuine inference | Agent review found incorrect CO2 naming; human qualitative review remains required |
| Chrome and Edge synthetic browser checks | Both failed before DevTools, exit2147483651 | GPU/process and isolated-profile errors; browser/mobile/keyboard rendering NOT VERIFIED; no sandbox flags disabled |
| Request-bound campaign | 224primary +152recovery executions; validation passed | 28fictional cases, two architectures, two scripted providers, two repeats |
| Source-copy reproduction | Four commands exit0: synthetic normal run,113component tests,39UI contracts and one complete scripted evaluation | Python3.12 with -S; no site-packages,Git metadata,venv,private catalog or credentials; snapshot-bound, not a clean OS/install or final freeze |

The campaign's denominators prevent a misleading overall accuracy claim:

| Campaign metric | Simulated historical index | Request-bound architecture |
|---|---:|---:|
| Desired current-policy contracts | 64/112 | 112/112 |
| Completed answerable tasks | 16/44 | 20/44 |
| Correct published fixture text | 60/64 | 20/20 |
| Exact citation association | 64/64 | 20/20 |
| Same-request source-supported publication | 0/64 | 20/20 |

This is a controlled fictional comparison, not measurement of the actual main
branch, live web availability or model accuracy. Raw logs, dataset, formulas and
tablesT1–T8 are under the component evidence directory. No human ratings are
invented; the science answer and actual municipal failure remain qualitative
negative observations alongside successful transport/contract checks.

RunState defaults reserve at most1400generated tokens,64000prompt bytes,two calls
and90seconds per workflow run; chat paths may select stricter policies. Four
workers bound residual work. Deadline/revocation blocks subsequent publication;
caller abandonment does not promise that a remote inference/GPU has stopped.
OpenAI stays subject to separate cost/privacy/transfer permissions. Source
HTTP/DNS/robots limits and the final exact-claim checks remain Verifier-owned.

The existing report outline now maps7.5planned main pages to the current
architecture, evaluations, two stress classes, limitations and student reflection.
It is keywords and a page budget, not a completed paper or rendered page-count
check. No provided NeurIPS style file, finished paper, eight qualifying meeting
reports or genuine demo record was found here. Student-authored material and
human editing are necessary; coding sessions cannot be relabelled as meetings.

## File ownership and cleanup plan

| Files or area | Dependencies and risk | Action |
|---|---|---|
| `hamar_agent/web.py` | Shared HTTP/UI boundary; preserve all request and publication guards | Removed unused RATE_SECONDS import only; selected web/provider contracts rerun |
| `hamar_agent/web_assets/index.html` | Accessible information text; no design or navigation change | Corrected obsolete claim that internet search is absent; kept uncertainty/privacy/source cautions; web and Node checks rerun |
| `harness/request_bound_eval.py` | Imports synthetic fixtures and the existing adapters | Removed five unused imported names only; complete scripted campaign rerun |
| `.github/workflows/offline-tests.yml` | Hosted Python/Node availability; no credential or package step | Add Python3.12/3.13 matrix and Node UI contracts; hosted execution NOT VERIFIED until authorized publication |
| README, READINESS, CHANGELOG, report_outline.csv | Student deliverables and current/historical evidence distinction | Maintain existing documents; no extra report or paper variant |
| `live_research.py`, `discovery.py`, `html_extract.py`, `internet_research.py`, `research.py` and their targeted tests/diagnostics | Security/context interfaces; another agent owns active edits | Read-only here; forward unused imports/helpers and counterexamples to Verifier |
| `portal_sources.py` socket compatibility import and older source/provider interfaces | Public compatibility namespace, legacy CLI and regression callers | Preserve; an AST unused-name observation alone does not prove safe deletion |
| Ollama/OpenAI adapters, local catalog workflow and synthetic skeleton | Distinct supported modes and source-transfer rules | Preserve; no forced consolidation across different trust contracts |
| `output/`, `resultat/logger/historisk/`, COM2 evidence | Historical, version-bound observations and required appendices | Preserve; output is ignored and is not an alternative production implementation |

No NotImplementedError was found in the active search modules; the public
provider Protocol is a type contract, not the runtime search implementation.
DDGS and the optional configured SearXNG provider are the concrete adapters.
Unsupported PDF/Office extraction stays explicitly unsupported. Package setup,
browser availability and real source coverage are not filled in with fake data.

## Cleanup proposal — no deletion authorized

One file is confirmed redundant:

| Proposed removal | Retained canonical file | Proof | Action |
|---|---|---|---|
| `hamar_agent/hamar-background.png` | `hamar_agent/web_assets/hamar-background.png` | Identical 289,541 bytes; SHA-256 `f87040eceeb4e9be60bc1c4ef517fd40d5bb44b166700e1922289029d01a4242`; web handler serves the `web_assets` file | **Owner approval required; not deleted** |

Static searches found no callers of `live_research.procedural_reference` or
`eval.test_internet_research.fake_ddgs_components`. These are in Verifier-owned
files; the findings were handed over rather than edited in parallel. Confirm
compatibility and run the relevant regression before removing them. Historical
frozen source copies, raw logs, COM 2 artifacts, Git branches/history and local
files are protected. No directory or historical evidence is proposed for deletion.

The sole writer cannot approve their own release. An independent read-only
review of the exact final hashes, followed by owner authorization, must precede
commit, push, tagging or submission.
