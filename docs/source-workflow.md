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

## Historical integration fixture approval

The guarded registry includes the reviewed, explicitly fictional `synthetic-verification-demo` fixture with its exact path and fixed LF/CRLF-normalized SHA-256. Arbitrary paths, unknown IDs and modified fixture content remain rejected. This local fixture approval does not approve a municipal URL or authorize retrieval. The original integration record reported 12 setup errors in a 77-test run before fixture registration, followed by all 77 tests passing offline; these are historical observations, not current suite totals. The [original approval record](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/integration-fixture-approval.md) remains archived.

The isolated HTTP transport is not permission to fetch real pages. Its documented controls include exact approved HTTPS URLs, TLS validation, no redirects/proxies/cookies, bounded UTF-8 text responses, timeouts, optional byte hashes and sanitized errors. These controls do not prove personal-data absence, provide an overall execution deadline or establish network-level egress isolation. Keep production retrieval disabled and follow the current source-review boundary. See the [historical transport record](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/approved-http-retrieval.md) for the original implementation and test conditions.

## Validation record

All 25 tests passed on Python 3.12.10: 9 existing scaffold tests and 16 new source/workflow tests. These cover approval before reads, immutable default registry, changed content, line-ending portability, malformed approved JSON, oversize and missing files, ID mismatches, injected responses, invalid result shapes, provider failures, no premature summarizer calls, no partial JSON and offline CLI compatibility. Temporary fixtures are synthetic only. No live retrieval or paid API was used.

The previous evidence follow-up suite belongs to a different local branch and is not counted in these 25 tests. Its six regression cases are preserved in commit e833983.

## Sanitized implementation prompt record

User authorized preserving pending work in a local commit, fetching updates, branching from origin/main and implementing only powerNeron's offline components. Remote writes require another approval. No credentials or personal data were used.


## General source-aware routing addendum (2026-11-18)

Sanitized request: extend the existing assistant across legitimate topics,
close the English municipal-fee bypass V-01c, retain the school repair and all
source/privacy controls, and obtain independent review without commit/push.
This addendum supplements the historical component agreement above.

Architecture and bounded implementation plan:

| Decision | Existing boundary and current implementation |
| --- | --- |
| Plain model chat | `ChatBackend.generate` now obtains one `QuestionPlan`; stable explanations, programming, science, history and creative work keep the normal adapter path. |
| Source duty | `question_router.py` projects NO/EN concepts and evaluates municipal/temporal duties before any answer model. Unknown local factual requests fail closed. A local semantic hint may escalate or request clarification, never remove mandatory duty. |
| Context | `QuestionRouter.resolve_context` inherits bounded user ellipses only. Assistant text is not evidence; explicit municipality changes replace the prior place. |
| Permission | `ChatBackend.search_allowed`, owner enablement, reviewed policy expiry, provider gates and per-request run controls are independent of classification. A classifier cannot approve a URL or enable search. |
| Discovery | `ResearchService.plan` selects approved source identities and geography first, then lexical concepts or an injected semantic/index nomination of eligible IDs. Municipal tier1 remains mandatory. No nominated URL can become an approval. |
| Retrieval | `LiveResearchService.prepare` first uses the reviewed non-personal full-text catalog through the existing `PreparedPublicTransport`; the existing typed municipal HTML path remains separate. Both paths obtain new request-bound observations. |
| Admission | Full-text sources require exact approved bytes, robots and expiry. Dynamic HTML retains narrow service/directory fields, privacy screening, script exclusion, dates and footnote/article controls. No unrestricted prose or person/contact harvesting is introduced. |
| Generation | Ollama and OpenAI receive the same selected binding, never raw HTML. Exact source-specific transfer approval is required for OpenAI. Local classification receives only the already-validated user question. |
| Publication | Binding verification, exact complete excerpt matching, conflicts, current-request receipts, revocation and web publication guards still apply. A recent fetch is not proof of current facts or completeness. |

Acceptance: both adapters must reject unsupported NO/EN fees/rules before
answer dispatch; stable topics stay open; updated facts require authorized
sources; follow-ups recheck sources and change municipality correctly; the
school list never asserts unproven completeness. Changed bytes, conflicting
facts, unapproved transfer, foreign/unknown IDs, SSRF, DNS, redirects, robots,
privacy and injection remain refusals. Run the guarded full Python suites,
UI contracts and research contracts, then bind exact files/evidence to SHA-256
and obtain a matching independent Verifier receipt.

`--enable-local-router` optionally uses an already installed Ollama model
(`--router-model`). It adds at most one 128-output-token classification call
inside the same token/byte/time budget; normal chat keeps one answer call.
There is no cloud classifier, installation or model download. Helper errors or
unusable/low-confidence output require clarification. Deterministic municipal
and freshness duties run before this helper.

Limits: the inspectable concept projection is not complete language
understanding. The default policy has no reviewed general-topic documents and
no public search-index adapter; broad current-fact coverage is NOT VERIFIED.
The topic-independent catalog/discovery interface supports approved documents
without adding a new municipal service keyword, but unknown raw HTML is not
automatically approved. Source review and any external index/transfer provider
remain explicit owner decisions. Institutional names may be documented;
individual contact details and personal records remain prohibited.


Routing hardening after independent candidate review: explicit temporal facts
cannot be exempted by a technical formatting word; semantic source nominations
are unioned with matches before authority selection; optional cloud approval is
checked before source fetch. The reviewed46 identity roster is available for
routing even when retrieval is disabled, without granting transport rights.
Subject-less detail ellipses share one NO/EN function-word analysis. Unparsed
qualifiers and dependent questions after a sourced topic ask for clarification
before answer generation; clarification never becomes a new service anchor.
A question/explanation prefix alone cannot erase source duty. Clear technical
subjects, explicit word definitions or explicit new-topic markers can establish
a separate task. This conservative context rule can request clarification for
an unfamiliar new subject; it is not universal semantic understanding.
Actual private market prices also require fresh general sources, while whole
price-formation explanations remain general knowledge. No country/global or
unreviewed URL discovery is enabled by language classification.


Known open MEDIUM (independent candidate5): after a municipal source-bound turn,
"Hva er demokrati?", "What is democracy?", "What is photosynthesis?" and
"Explain democracy." can ask for clarification rather than switch immediately.
These topics work as first questions. The conservative guard intentionally does
not infer a new subject from a what-is/explain prefix alone. Four scripted API
contracts confirm "Nytt tema: Hva er demokrati?" / "New topic: What is
photosynthesis?" after an SFO source turn on both adapters. This is a documented
conversation limitation, not complete general semantic routing. The final
Verifier must report it separately from closing the HIGH source-duty findings.


Frozen-v2 addendum (2026-11-18): the immutable frozen-v1 and its independent
receipt remain historical. A new own negative found that tomorrow/next-period
wording could bypass the temporal gate; the shared relative-calendar grammar
now includes future and recent periods (not a new subject-specific exception).
Eight both-adapter future/relative cases refuse before answer dispatch. The
source-only harness and general research metrics now include the exact
question_router.py SHA-256; a synthetic regression checks the recorded hash.
This closes the source-probe version-coverage gap, not genuine acquisition.
Frozen-v2/manifest.json supersedes v1 and needs its own matching independent
receipt. G-01 and all actual-source/model/native-browser limitations remain.


Frozen-v3 addendum (2026-11-18): v2 remained FAIL after independent testing of
weekend/two-days/kommende-helg variants, despite689 green methods. The remaining
root cause was a global explanatory-prefix exemption for variable subjects.
That exemption is removed: weather/currency/inflation/population facts require
sources by default; only a whole concept or mechanism explanation matches the
stable path. Calendar-word coverage is therefore not the safety boundary for
these subjects. Twenty final scripted negative/concept-positive provider/cases
pass with the exact router hash. Full logs are offline-final-v5-py312/313 and
research-final-v5; frozen-v3/manifest.json requires its own matching receipt.
V1/v2 manifests, failed cases and receipts remain unchanged. G-01, incomplete
general-source coverage and actual-production NOT VERIFIED remain explicit.

V3 final binding uses offline-final-v6-py312/313 and research-final-v6. The earlier v5 cohort is retained as an intermediate candidate. Whole stable-concept admission uses exact concept nouns; compound forecasts/numeric population subjects cannot inherit it. The added Norwegian forecast-compound RED is retained, and the exact final proof is v3-variable-facts-final-v2-green.json (24/24 scripted negative/concept-positive contracts). Frozen-v3 requires a separate matching independent receipt.


## Three-municipality/simple-UI architecture decision (2026-11-20)

Sanitized request: continue exam/final, simplify entry for older/first-time users
with the supplied welcome and two model choices, activate only Hamar/Elverum/
Gjovik, retain46records and previous work, investigate municipal information
beyond old topics while preserving source/privacy controls, test without paid
calls/installations/Git writes and obtain independent review.

The initial HEADa633b343437c60e7a7dd3d593fb84f37c0e2164a was externally created;
initial dirty documentation/audits and untracked question_router.py are preserved
in baseline hashes/beforefiles. The old interface had separate chat/municipal
views, multiple per-provider choices and Hamar-specific presentation. The source
policy had46identities and no separate active scope; unknown HTML topics stopped
before an official request. Generic reviewed full-text RAG already existed.

Bounded plan and acceptance:

| Boundary | Files / implementation | Acceptance |
| --- | --- | --- |
| Entry and welcome | web_assets/index.html,style.css,app.js | Exactly2stacked pink entry buttons; exact supplied welcome/5steps; native details; safe cost/privacy/source disclosures. |
| Model/context | app.js,chat.py | Exact mini/local choice;0generation on navigation; no unavailable fallback; same-model Back preserves history/draft/revision; model change requires acknowledged reset. |
| Active coverage | research.py,live_research.py,portal.py,web.py,docs/innlandet-research.json |46unchanged identities +separate3active IDs;43inactive places refuse before catalog/HTML/DNS/SDK; browser cannot override scope; publication rechecks scope. |
| Broad topics | live_research.py,question_router.py | Topic-independent approved-text answers on both adapters and municipal APIs; explicit locality/short follows; unknown HTML discovery never becomes approved evidence. |
| Safety | existing transport/admission plus regression suites | Preserve robots, pinned DNS/TLS, no redirects, privacy/injection, sizes/time/resource/kill/revocation and exact source receipts. |
| Verification | existing eval files/browser/research harnesses | Whole socket-guarded Python suites on both runtimes, Node contracts, exact-version independent review; native/real-source evidence separated. |

The new generic HTML path only discovers review candidates, at most6requests
within the existing session bound, same official host/depth2/native GET. Unknown
text is discarded before model/index/export; diagnostics contain host/digests/
counts. It does not infer anonymity, factual truth, paragraph approval or broad
usable coverage. Actual source/body reviews and any external-transfer consent
remain required. The source-only harness inherits the same active policy.

The existing raw-user-context safety remains. This phase does not close the
separate V-T02 HIGH recent-date/news bug or other r4 general-routing limits.
No declaration of clean checkout, production, universal information retrieval
or academic compliance follows from the scoped710-method/32VM-group cohort.
Chrome/Edge rendering and screen-reader behavior remain NOT VERIFIED after
both isolated starts failed before DevTools. No permissions/security settings
were changed or bypassed.


Pilot final validation addendum: generic discovery never sends unreviewed user
wording as remote search parameters. Topic matching stays local; native search
parameters can use only reviewed non-personal catalog vocabulary for that city.
With the shipped empty catalog this means bounded official navigation only,
not arbitrary remote free-text search. The regression includes a GET form and
checks that unknown words never become query parameters. Final full logs for
this hardening are offline-final-v2-py312/313 and research-final-v2; UI assets
remain identical to the32-group ui-final-v1.json result. No actual source/model
or paid call was made and the current three-city scope is not blanket source
or personal-data approval. Independent matching frozen review is required.


## Automatic evidence architecture and approval process (2026-11-20)

Sanitized owner request: continue the current exam/final work, close V-T02 and
remaining routing defects, attempt municipal facts automatically for the three
active places, support topics beyond categories on both adapters, preserve UI
and privacy/security, distinguish discovery/acquisition/admission/publication,
prepare externally approved source-only trials, freeze and independently review.
No new network, model/payment, install or Git mutation is authorized by this note.

| Decision | Existing component and scoped change | Acceptance |
| --- | --- | --- |
| Stable/current/municipal/ellipsis | question_router.py | Shared event/calendar source duty precedes answer dispatch; whole stable definitions remain direct; capitalization is not a municipal entity. |
| Automatic chat | chat.py managed_reply/generate, existing automatic_municipal flag | Owner-enabled LiveResearchService + Send performs fresh research with web_search=false; both adapters, no category. No startup/typing fetch. |
| Reviewed selection | research.py plan + optional reviewed discoverer | Metadata can nominate approved IDs; exact official authority/place first. Browser/model cannot add URL rights. |
| Fresh input | live_research.py and existing pinned transport | Exact URL, new request ID, robots, DNS/TLS, no redirect, byte/time/resource/kill limits; no-cache. |
| Generic HTML admission | explicit ResearchApproval HTML input/units | Whole raw snapshot hash + separate input-review evidence + exact context units; no SERVICE_WORDS relaxation for automatic unreviewed HTML. |
| Publication | existing ResearchBinding/extractive verification | Quote must equal an approved unit; source/municipality/approval/scope/owner/transfer recheck; conflicts refuse. List complete remains unproven. |
| Unknown sources/documents | bounded discovery | Host/digests/counts only;0admitted excerpts/0answer model. PDF/Office is unsupported evidence, not silently extracted. |

Safe, scalable approval procedure (a proposal, not a new permission):

1. The owner identifies an exact official HTTPS URL in one active municipality,
   purpose, intended fields and required use period. Identity metadata or domain
   membership alone is insufficient. Reject individual contacts/records and
   unsupported document types before granting access. No raw user query goes
   to an unreviewed remote search endpoint.
2. Obtain an explicit, time-bounded permission for transient acquisition of that
   URL and robots.txt. Review the page/document in an authorized environment.
   Keep raw bytes transient; hash the full snapshot. Retain only independently
   reviewed non-personal complete units and sanitized evidence hashes. No raw
   HTML, unselected names or source-preview dump is an audit artifact.
3. Review complete heading/article/condition/footnote context. Record the exact
   normalized "heading | condition | paragraph" unit, source URL/title/keywords,
   content type/tag, whole input hash, robots hash, reviewed_on/expires_on and
   input_review_evidence_sha256 in the existing source policy. Each monetary
   unit needs a literal whole amount and conflict key (entity,attribute,period,
   municipality,unit). Ambiguous multi-price and unresolved notes are rejected.
4. Have an independent reviewer validate the prepared unit, input/privacy/reuse
   grant, period, authority, relevance and conflict annotation. External transfer
   of THESE units requires an additional explicit per-source grant; it does not
   cover raw HTML, unrelated content or a new snapshot. Provider permission is
   separate. The stricter course no-processing requirement remains unresolved
   by an application permission and is not declared waived.
5. Validate the bounded policy offline, retain previous versions/evidence, and
   run source-only --live-sources --reviewed-only after the exact external test
   grant. Only robots and selected exact reviewed URLs may be fetched;0models,
   0paidcalls. Record fetch/publication/update/effective dates separately. Then
   independently approve the integrated frozen candidate, never its own author.
6. Use an expiry/revocation queue and batch human reviews for new topics. Any
   raw-hash or unit/context drift immediately withdraws the answer capability;
   a changed technical nonce is still drift. Never auto-extend expiry or accept
   a substring, lowercasing or a calendar word as a new privacy/source approval.

The current default catalog has0approved generic sources. Broader actual useful
coverage is a permission/content readiness gap, not solved by green mocks. The
first external permission proposal may cover only these EXACT connectivity
inputs: https://www.hamar.kommune.no/robots.txt and / on that host;
https://www.elverum.kommune.no/robots.txt and / on that host;
https://www.gjovik.kommune.no/robots.txt and / on that host. No such new request
has been executed. A connectivity/root result does not approve a service
paragraph or demonstrate an answer. Each service URL requires its own review.

V-T02 was reproduced8/8 before edits. The router now requires evidence for
actual event/report subjects independent of calendar wording, recognizes shared
NO/EN date/weekday/relative-time forms and uses the actual year for nearby-year
references. Only whole concept/mechanism explanations are exempt; appended
Python/math/explainer language cannot erase a fact request. Named-entity role
and whole standalone definitions also repair tested Java/Rust/country/element
false positives, What-is-weather and natural new-topic examples. Language
understanding is inspectable and incomplete; no universal semantic guarantee.
A first standalone-definition candidate accidentally admitted "What is included?"
after a sourced topic; the existing negative regression exposed it and was
retained. Referential/attribute fragments still clarify or inherit source duty.

Independent candidate review found HTML-C01 (a discarded ancestor heading was
stored at level7 and erased by a subordinate heading) and HTML-C02 (fact_value
was checked as a substring, allowing50 to describe250/350 and hide conflict).
C01 now preserves actual heading levels and unknown non-heading scope; C02
requires a whole unambiguous monetary value and literal reviewed period. Red
and green evidence is retained separately; final exact-frozen review is needed.


Final offline evidence for the automatic-source phase:722/722 methods on both
Python3.12.10 and3.13.7,0failures/errors/skips with socket/DNS guards and identical
before/after source hashes. The721-method final-v1 cohort remains a retained
intermediate; final-v2 adds the explicit foreign-municipality-unit refusal.
UI assets are unchanged and32/32Node VM groups pass. Research:20general,
34regional (44requests),93automatic cases (78approved synthetic HTML answers,
15controlled refusals). The matrix is not a real-answer correctness score.
All successful rows are exact reviewed-unit contracts; no real source or model
has been called. No complete-list, general anonymity, production or academic
claim follows. Matching final independent frozen review is still required.

The exact6-URL connectivity plan and model-free probe are prepared under
output/aisha-auto-sources-20261120-764dca4d/. The probe's default dry-run was
executed with sockets/DNS forbidden and made0requests. Actual execution remains
AWAITING OWNER APPROVAL. It follows no links, parses no HTML and records only
controlled transport metadata/hashes. Source paragraph approval is separate.
After explicit approval, run from ordinary PyCharm PowerShell on the same UTC
date as the plan (a later date needs a renewed finite plan):

```powershell
.\.venv\Scripts\python.exe -B -X utf8 output/aisha-auto-sources-20261120-764dca4d/https_connectivity_probe.py --execute-approved --approved-plan-sha256 2d9435ed2305db1e6dd6a04a70e89ae14c0f9f7c4b3ad66fc1a0d01fd38746fa --output output/NEW-pilot-connectivity
```

A successful connectivity report is NOT evidence that SFO/schools/other facts
were obtained. No new paid call, installation, model download or Git mutation.
main/COM2/prior files and untracked contributor work are preserved. The known
untracked question_router.py dependency is included in the new freeze/patch;
no clean-clone/publication claim is made. Native-browser/screenreader/usability
limitations from the previous phase remain NOT VERIFIED; UI was not redesigned.


### Relative-period follow-on: frozen-v1 is FAIL, not final approval

The first automatic-source freeze cf5f19e9d8dd4ce7f336299591dee8279a1e321ae49fddc5207b956aa2e9cd82
had matching722-method green suites but a new independent period-HIGH: an exact
2026 fee unit could answer next-year/i-fjor/om-to-aar requests. Explicit2027
was already refused. Red probe and beforefile remain retained. A first fix
still missed an unresolved season/month; those red cases are also preserved.

The shared fee-period validator now reconciles explicit and relative NO/EN
years against the actual system year, accepts only a matching literal source
period, and refuses conflicting or unresolved calendar constraints. Calendar
names/months/seasons without a resolved explicit year never borrow the fetch
or publication year. Unclear school/season/month periods request a concrete
year/date; billing units permonth/year remain distinct from target dates.
Calendar nouns and possessive municipality wording are not new place names.
Both models share this gate before generation. A nonretryable useful period
message replaces an undocumented amount.44scripted positive/negative cases use
four source years with the same current publication/fetch year, including
matching future/past answers, conflicting years and unresolved season/months.
The new full cohort is723methods. Final binding is offline-final-v3-py312/313,
research-final-v3 and frozen-v2/manifest.json, pending matching independent
receipt. Earlier v1/v2 run logs and frozen-v1 are unchanged historical evidence.
No real source permission, network/model/paid call or Git mutation follows.


V2 final addendum: unresolved month/season names now require a concrete period,
including til-vaaren/fra-januar; fetching/publication never supply the missing
year. The44-case relative-period contract includes legitimate current/past/
future literal years and unresolved or contradictory alternatives on both SDKs.
Calendar words after prepositions are not municipality names. The two remaining
concrete G-01 forms are repaired by parsing standalone information/explanation
request wrappers, not by adding a science-topic whitelist.14new provider/cases
preserve attribute/deictic source duty and allow explicit new topics. This is
still not universal semantic understanding; unfamiliar/ambiguous wording may
clarify safely. Final full count is724methods, superseding the intermediate723
plan. Final-v3 logs/research and frozen-v2 plus its own independent receipt bind
the exact accepted local candidate. The failed v1, its722passing test logs and
all red/green receipts are preserved unchanged. V-C01 actual source/approval
coverage remains open; all genuine acquisition/model/native results remain
NOT VERIFIED and the finite HTTPS permission request is still pending.


Final safety follow-on: a broad new-topic wrapper candidate was rejected after
independent compound-attribute counterexamples. Its beforefile/red evidence is
retained. Independent-topic parsing now retains original definite-article cues,
uses compound attribute roots, and treats uncertain definite wrappers
conservatively; existing source/temporal gates run first. Tested natural
photosynthesis forms work, while age-limit/admission/property references cannot
erase the source context. Conservative ambiguity remains a documented limit,
not a universal semantic guarantee.22wrapper provider/cases are regression
coverage; the existing referential negatives are unchanged.

Two additional permission repairs are included. LiveSession snapshots and
rechecks reviewed_only even for legacy/empty-catalog transport, so a mid-fetch
restriction revokes the old capability. Historical sourced assistant quotes
were previously retransmitted as normal model history even after source
transfer revocation. The server now uses its already separate display/model
histories: full answer/citations remain visible; model history receives a
neutral placeholder for source answers. User turns still establish topic and
municipality. New sourced turns always fetch anew; ordinary non-source model
history is preserved. Both adapters and later general topics are tested.
Independent retests of the new permission negatives are green; raw historical
red/green evidence remains separate and unchanged.

The final full regression is726methods on each Python runtime in
 offline-final-v4-py312/313; earlier v3 was started before these confirmed repairs
and is intermediate, not final acceptance. Research-final-v4 and frozen-v2
bind the final integrated state and require their own matching independent
receipt. Approved UI/policy/46record bytes are unchanged in this phase. The real
source catalog remains empty and actual HTTPS/content/model/native quality
remains NOT VERIFIED; the separate finite network approval question is pending.


MIME-parity finalization: the same approved2026 fee was found answering next-year
questions through the plain-text catalog. That red proof is preserved. Literal
and relative period/date helpers now live in research.py and are re-exported
by live_research.py for compatibility. The COMMON request binding enforces
monetary period/valid-from/to constraints, independently of HTML/plain transport
or adapter. Explicit reviewed fact_scope periods can support plain-text units
without a printed year; receipts mark this reviewed basis separately. They are
never inferred from retrieval/publication. Reviewed municipal monetary units
in either MIME need a conflict scope and a whole matching amount.250 and250,00
compare equally;250/350 conflicts refuse. An existing injection fixture gained
correct explicit999/period annotations so its original injected-source/model-
quote assertions still execute; no assertion was removed. HTML robots-hash
drift now stops before the page request.28independent MIME-parity probes pass.

The earlier full-v4 has726green methods but predates this shared policy and is
retained as intermediate. Final binding is727methods in offline-final-v5-py312
and py313, research-final-v5, unchanged UI32 and frozen-v2/manifest.json with its
own independent receipt. Known finite failures are addressed, not all possible
language/format semantics. Actual source coverage (V-C01), native accessibility,
real model quality and production readiness remain NOT VERIFIED. No external
request, paid call, installation, Git operation or real-source permission was
performed/granted by these repairs.


Final binding note: the common monetary/date gate is727methods after the plain-
text parity regression. Approved municipal monetary annotations now use the
same whole-amount/conflict checks across both MIME types; plain review scopes
are marked as such, not confused with literal source dates or retrieval dates.
The prepared injection-data fixture remains an actual injected instruction and
its original1model/unapproved-quote refusal assertions remain unchanged.
Only offline-final-v5-py312/313 and research-final-v5 are the final pre-freeze
cohort;726-method v4 is retained as a pre-parity intermediate.727is a test-method
count; the separate automatic matrix has93cases, not93real service trials.


Frozen-v3 superseding note (2026-11-20): frozen-v2 is withdrawn after a
confirmed definite-variable V-T02 counterexample. "What is the weather?" and
"What is the population?" were normalized into bare concept exemptions and
dispatched both SDKs without evidence. The raw-turn freshness obligation now
survives context normalization; definite variable lookups require sources.
Bare "What is weather?", definitions and whole mechanisms still use general
chat. The added regression covers20 negative provider/live combinations,
16 stable controls and both direct routing and conversation planning.
Final binding is728methods in offline-final-v6-py312/313, research-final-v6,
unchanged UI32 and frozen-v3/manifest.json, subject to its matching independent
receipt. V2's727green tests/initial receipt remain historical evidence only;
its separate superseding FAIL must not be presented as acceptance. One earlier
parallel independent3.13 run had a timing-sensitive deadline-error-code
mismatch in an unchanged test;20isolated repeats and the serial full727run
passed. That observation remains visible rather than removing assertions.
Actual public source coverage V-C01 remains OPEN: no approved real excerpt
catalog is installed. No new external request, model call or Git operation.


## 2026-11-21 - Authorized finite connectivity and publication candidate

The owner approved exactly six HTTPS GET inputs: /robots.txt and / on each of
www.hamar.kommune.no, www.elverum.kommune.no and www.gjovik.kommune.no. This is
a finite connectivity grant, with no link following, raw HTML retention,
service-excerpt approval, model call or cloud transfer. A new date-bound plan
was created; all older plans, frozen versions and test evidence were preserved.

Actual pinned-transport trial at2026-11-21T02:26:35Z: all three robots attempts
failed with PermissionError/WinError10013 and research_unavailable. Consequently
all three root-page GETs were NOT ATTEMPTED. No HTTP response, MIME, robots
permission or content hash could be verified. This is an environment-blocked
trial, not successful municipal acquisition. No bypass, proxy, security change,
extra URL, model/payment or raw HTML retention was attempted. Local ignored
evidence: output/aisha-publication-20261121-3ba1ab9a/https-live/
https-connectivity-result.json. Renewed exact plan SHA256:
66da65f48908c22dd89e8cf7cf50b5ec31d509ac6deeda9915272e0a2edcbd9b.

The last exact frozen-v3 implementation had independent SCOPED PASS:
manifest1b595fa7b035fd929d7f39f0cc1fbaaf085e671d58352e1f1754bd6bfbd2840f;
receipt90e9637db1fe5a3d701db9b706f8134b4ff53eac5e674b726500c20a31237423.
Its728-method tests on each Python,32 Node VM groups and316 independent
expectations do not prove actual source/model/browser performance. This
publication follow-on changes documentation only; runtime/test/UI/policy bytes
remain the same. Fresh serial regression and a matching publication manifest/
independent receipt are required before commit. Raw generated output remains
local and ignored; it must not enter the publication candidate.

V-C01 remains MEDIUM/OPEN for actual generic source/approval readiness.
The generic real excerpt catalog has0approved entries; only Hamar, Elverum and
Gjovik are active while all46 identities remain retained. PDF/Office content,
personal contact records, native browser/screenreader checks, actual model
quality and broad live municipal coverage remain unsupported or NOT VERIFIED.
Conservative language/context limits and the prior LOW timing observation
remain documented; no full-production or academic-grade claim is made.

Sanitized owner instruction: preserve both contributors, main, COM2 and all
history; rerun full offline/UI checks, review exact bytes and exclude secrets/
personal data/generated clutter. Conditional commit and push are authorized
only to origin/exam/final after no open HIGH and matching independent review.
No force push, rewrite, merge, deletion, installation, model download or paid
API is authorized. GitHub failure must stop remote attempts and hand back one
PowerShell command at a time for the ordinary PyCharm terminal.


## Five-step welcome acceptance,23November2026

Sanitized owner request: implement the final five-step Norwegian introduction
inside the existing app; large accessible pink actions, one visible panel,
back/restart/skip, direct local/mini chat, preserve history/provider/source/cost
controls, full regression and exact independent review before conditional Git
publication. No installation, paid inference, deletion or main/COM2 change.

Acceptance: step navigation and intro restart make0API/source/model/reset calls;
restart preserves the conversation; step focus and skip target remain visible;
late provider metadata cannot change steps or steal subsequent focus; only the
explicit model entrance loads metadata, and only Send generates. Existing
unavailable-model and failed-reset guards continue to apply. The exact supplied
copy is captured separately in local acceptance.json for independent comparison.

Source approval is still URL/input/whole-unit specific. The prepared nine-case
queue has three questions per active municipality, four exact historical/owner
URL candidates and five explicitly missing service URLs. All approvals, source
hashes and excerpts remain unset. No expired approval is renewed automatically.
The renewed six-URL connectivity plan awaits explicit confirmation; new source
facts/OpenAI source transfers require separate review. No external source or paid
call is made by intro navigation or this candidate's validation.

Actual local model proof is a single fixed arithmetic reply, not service coverage.
Chrome/Edge startup failures are retained as NOT VERIFIED native/accessibility
checks; computed contrast/Node behavior do not certify full WCAG or screenreader
compliance. V-C01 and conservative semantic/format limits remain open. Full
Python3.12/3.13, Node and research contract artifacts and matching independent
manifest review are required before publication; previous logs are unchanged.


## Reopened source-integrity and context repairs,23November2026

Sanitized owner instruction: honor the independent PUBLICATION FAIL, read the
whole report, repair V-02b/details-fieldset and V-02c/image-footnote gaps, G-01
new-definition context and I-01 welcome purpose/inclusion, add negative/positive
regressions, run both Python/Node/source and separate external acceptance suites,
freeze new bytes and obtain independent exact-version review. No Git writes,
paid API, unapproved HTTPS or automatic real source approval.

Acceptance: an undated sibling cannot borrow another group's year; full native
group labels remain in each applicable unit or cause refusal. A lost nonheading
condition cannot be cleared by a child H2 and lasts until the scope closes. The
next clean sibling still works. Any recognized image annotation cue yields an
unsupported-note marker with zero image fetches and zero model dispatch/history
for the unsafe price. No omitted footnote is guessed. Safe prices in their own
scope and a clean decorative-image control remain usable.

G-01 recognizes whole indefinite NO/EN definition clauses with ordinary manner
modifiers, preserving the original article. This proves a new subject without
introducing an explanation-prefix exemption: explicit municipal/price/current
facts remain source-bound and referential fragments still clarify. I-01 adds
only two authorized inclusion/purpose paragraphs; all five steps are preserved.

RED replay: original immutable snapshot gives8/20 source-scope and2/32 continuity
failures. The external scripts themselves are unmodified; GREEN must record a
new target binding, source file paths/hashes and0failures across84acceptance rows.
The old wrapper's pinned snapshot must never be mistaken for repaired code.
Additional native-group long-label and independent positive sibling probes are
required because the first repair candidate exposed another HIGH dropped-label
case; its red evidence is retained. Publication remains blocked until a new
explicit PUBLICATION PASS. V-C01, native/format and genuine-provider limits and
historical PUB-T01 remain visible and are not closed by synthetic green counts.


## 23 November 2026: simple chat, needs context and reviewed navigation

Acceptance: shared deterministic municipality/service context for both providers; no source or model request on typing, topic suggestions or navigation; separate server-owned model banks and drafts; fresh authorized research on each submitted factual question; fail closed before generation if evidence is absent. Rate limits and a single pending gate are shared across banks. Reset/expiry/stale revisions cannot resurrect another bank or a late answer. Explicit clinical self-description fields are screened before any retention/fetch/SDK; this is a conservative known-field screen, not a universal privacy proof. English home-help aliases distinguish data cleaning/shopping-list tasks from care needs; output-format words never release municipal source duty.

A reviewed source may carry up to two `navigation_links` records, each with `url`, `purpose` (`service` or `application`), `reviewed_on`, `expires_on` and `evidence_sha256`. The exact HTTPS destination must share the municipality's approved host; queries/fragments/encoded paths, expired/revoked approvals, wrong municipalities and unrelated topics do not produce links. These grants authorize navigation metadata only, never retrieval, unknown HTML or OpenAI content transfer. UI states that target content is not fact-verified, and opening an application is not applying. No real link grants were installed.

V-C01 review sequence: document exact candidate URL and permitted transient input; owner reviews non-personal input and reuse; retain only complete approved paragraphs with all headings, article/group context, period, monetary scope and footnotes/conditions; record source/input/robots/excerpt and reviewer evidence hashes with expiry and revocation; independently review the entry; grant OpenAI transfer separately per source; run source-only exact URL probe, then adapter tests within owner cost policy. Unknown documents remain candidates, and unsupported formats require a separately reviewed parser. The queue preserves four earlier documented URL candidates and exact-URL gaps, and adds day-centre/home-help gaps without invented paths. No external retrieval is authorized by adding a queue row.

Sanitized prompt summary: user requests a simple accessible chat for older/novice users, nine editable municipal suggestions, natural need→municipality→details continuity, automatic approved research at Send, direct approved service links, safe model switching and independent frozen-version review. Earlier source/security/high-fix and all-three-pilot boundaries remain mandatory. Evidence: `output/aisha-simple-chat-20261123-fbe365d7/` (excluded from Git publication).

Production entry correction: the actual web CLI now passes `reviewed_only=True`. An enabled flag alone cannot broaden missing exact approval into typed HTML admission; a startup regression checks both provider services share this object and an unknown service never invokes `_discover`. The older narrow typed profile remains available to explicitly injected synthetic/regression fixtures. Whole municipal term definitions share a bounded deterministic classification across the router and application guidance, so a stable definition does not inherit a factual service duty; place/date/value requests retain the gates.

Independent final review of simple-chat freeze v1 found a MEDIUM reset-barrier regression on A→B→A after an unsuccessful explicit reset. The corrected client stores reset-required state per bank, keeps recovery visible and refuses Send until a matching acknowledgement. Model navigation cannot clear the barrier or reset the other bank. The immutable v1 and counterexample are retained; a new v2 snapshot/review is required.


## 23 November 2026: combine fetched511 and reviewed Aisha snapshot

Sanitized user instruction: integrate the existing26 local Aisha files (e781537a frozen-simple-chat-v2) with the13-file fetched511b028 contribution, preserve both developers' code/tests/log entries, regress the exact combined tree, obtain independent publication review and publish only exam/final. No paid calls, new source retrieval grants, destructive history operations or main/COM2 changes.

The incoming commit is a direct child of a633b343. Raw local/untracked files, all13 base/incoming blobs, original index and cumulative patches are backed up with SHA256 before integration. Non-overlapping incoming files remain exact copies; two overlapping test files use a clean three-way content merge, and the incoming dated CHANGELOG block is appended verbatim after the full local prefix. One newer local portal mock also needed to select the last Ollama user message and assert separate roles; no feature or test was removed.

Ollama source prompts now separate trusted policy from untrusted JSON title/paragraph data. Reviewed adapters and test/evaluation consumers read the user data rather than the system slot. Existing byte/token/call/time/response controls remain. This is message-boundary hardening, not a model-quality or universal prompt-injection claim. No sources or external transfers are newly approved.

Git plan: after an isolated synthetic proof and precondition checks, an index-only read-tree without -u plus ancestry-checked compare-and-swap ref advance can put HEAD/index at fetched511 without writing any working file; the operations are not jointly atomic, so failure stops the sequence. Only a separately reviewed final commit may then be created, with511 as direct parent. The current Codex attempt stopped at index.lock permission denial, before any ref update; normal-terminal continuation is required if the environment remains blocked. Evidence and exact status remain in the output phase; no bypass/reset/rebase/force is permitted.
