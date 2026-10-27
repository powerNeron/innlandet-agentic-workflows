# Reviewed real municipal workflow, local implementation

## Current operation

Python 3.12.10 and standard library only. Ollama 0.40.3 and llama3.2:3b were already installed. No packages or models were installed/downloaded. All changes remain local and uncommitted on feat/full-system-web. The previous robots implementation/test/review report are preserved.

The user explicitly approved transient official HTML acquisition and retention of individually reviewed public service excerpts. This supersedes the application full-document exclusion rule, but does not resolve the stricter wording of the course assignment. See the separate requirements matrix.

## Exact approved URLs

Eight URLs, 39 whole reviewed paragraphs, seven backend categories covering eight service cards. The bounded metadata registry is docs/approved-service-pages.json; the administrative URL/paragraph-hash selection is docs/reviewed-service-selection.json. These are expiring explicit manifests, not domain-wide approval. Reviewed 2026-10-21; expire 2026-10-28. Empty default registries remain safe for callers that do not explicitly load these manifests.

- hamar-sfo: https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/ (5 paragraphs; oppvekst)

- hamar-byggesak: https://www.hamar.kommune.no/byggesak/bygge-uten-a-soke/ (5 paragraphs; bolig)

- hamar-folkehelse: https://www.hamar.kommune.no/folkehelse-kunnskapsgrunnlag/ (4 paragraphs; helse)

- hamar-bibliotek: https://www.hamar.kommune.no/kultur-og-aktivitet/hamar-bibliotek/ (5 paragraphs; kultur)

- hamar-kommuneplan: https://www.hamar.kommune.no/kommuneplan/kommuneplanens-samfunnsdel/ (5 paragraphs; politikk)

- hamar-drikkevann: https://www.hamar.kommune.no/drikkevann/ (5 paragraphs; teknisk)

- hamar-parkering: https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/ (5 paragraphs; teknisk)

- hamar-luftkvalitet: https://www.hamar.kommune.no/klima/luftkvalitet-i-hamar/ (5 paragraphs; miljo)


## Run the existing local application

From the repository root:

```powershell
python -X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Open http://127.0.0.1:8000. The server is bound only to 127.0.0.1. Default terminal startup also uses real mode with the local reviewed catalog. Missing/expired catalogs fail startup; they never trigger a synthetic fallback. No web request enables fetching, approves URLs or accesses credentials. The existing local catalog is output/municipal-catalog.json (ignored generated data). Searches do not fetch pages.

Direct CLI with exclusive JSON saving and identical JSON stdout:

```powershell
python -X utf8 -m hamar_agent --real-sources --source hamar-drikkevann --model llama3.2:3b --ollama-timeout 90 --output output/NEW-result.json
```

Output filename must not exist. Parent must exist. Real mode refuses --fixture, --provider mock and --fallback-to-mock. Use --demo explicitly only for offline development/testing:

```powershell
python -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
```

Never run both servers on the same port. Stop the foreground server with Ctrl-C. If necessary, `ollama stop llama3.2:3b` stops model inference; no such command was executed during this implementation.

## Reproduce reviewed acquisition

The initial import was run against all eight official URLs before the privacy fail-closed change; no raw HTML was saved, but transient parsing could still process personal information. **All raw HTML acquisition and import are now disabled**, because excerpt filtering cannot guarantee that personal information is never processed. `fetch-reviewed --enable-live` fails before network setup; `import-snapshot` fails before opening the snapshot; the administrative importer fails before any request. Do not run the legacy command below. Existing reviewed catalogs can be read until approval expiry, but do not renew them from HTML.

```powershell
python -X utf8 -m hamar_agent.municipal_import --selection docs/reviewed-service-selection.json --approvals output/NEW-approvals.json --output output/NEW-catalog.json --enable-live
python -X utf8 -m hamar_agent.web --real-sources --catalog output/NEW-catalog.json --approvals output/NEW-approvals.json --model llama3.2:3b --ollama-timeout 90
```

Historical review scope was service_excerpts. Whole paragraph hashes were individually selected; unselected paragraphs, captions, scripts/forms and linked pages were not retained. The older importer still parsed the full raw response transiently, so this historical processing is not treated as proof of full assignment privacy compliance. Current real execution reads only the exact-hash approved local catalog and rechecks limited contact patterns; there is no general automatic named-entity/privacy guarantee.

The former administrative importer used exact official HTTPS URLs, robots checks, pinned TLS, redirect/authentication/noindex/compression rejection, ten-second timeouts, 512 KiB limits, and rate limits. These transport controls did not solve the earlier processing of full HTML, so both live retrieval and raw snapshot import now fail closed. Re-enable only after an acquisition format can guarantee personal information is not received or processed.

## Real Ollama contract and mandatory verification

JeppeGs's ollama_provider.py, correction.py, summarize.py, verify.py, revision.py and schemas.py remain unchanged. real_sources.py adds a catalog-scoped application adapter using the actual OllamaClient, existing claim parser, verify_claims and CorrectionResult protocol. It never relabels municipal content synthetic. MunicipalResult is an additive WorkflowResult with source_provenance and evidence_policy; existing shared Result stays unchanged.

The real model selects one whole reviewed paragraph through constrained JSON decoding. This is deliberately an extractive answer, not a free-form paraphrase or an independent fact-check. The transport schema ties text, evidence_quote and paragraph_id to an actual same source paragraph. It never fabricates a response when the model is unavailable. Locally assigned claim record IDs c1... are not evidence IDs; paragraph IDs and evidence text are never normalized or guessed.

After EVERY initial response the application calls JeppeGs's verifier and independently requires claim text == full quote == actual paragraph text. This preserves numeric roles, dates, fees, deadlines, negations and conditions within that paragraph, instead of trusting a citation ID or checking only that a number occurs somewhere. Unsupported/partial/reordered claims cannot be exported as supported. If findings exist, at most one correction-provider call is allowed, then mandatory independent re-verification runs. Unresolved findings or verifier/provider failures produce no result/download. No unchecked model text or hallucinated personal details are retained in correction history: sanitized findings and attempt counts remain, rejected candidate text is omitted. The source provenance includes exact official URLs, retrieval/index timestamps, raw/text hashes and approval expiry. Real search input is not echoed into exported JSON. No prompt or raw-response logging is enabled.

Budget: at most two model calls per answer, each capped by the existing 24000-character prompt guard, num_predict=700 and bounded response body. This bounds generated output to 1400 tokens requested at most; actual usage token counts are not available from the unchanged client and must not be invented. Per-call timeout is bounded (90 seconds in examples); it is a socket timeout, not a proven hard overall wall-clock deadline. No paid API is configured. Each run stops on missing source, failed verification, provider failure or the single unresolved correction.

## Test evidence and observed failures

- Final offline suite: 227 passing, zero failures/errors; real sockets and DNS blocked. All original 193 tests are preserved and still pass. New municipal tests use clearly fictional source content, never scraped material. Existing retrieval tests retain TLS, redirect, SSRF, MIME, size, timeout and cleanup coverage.
- The initial live import succeeded for eight sources and 39 selected paragraphs, with no raw HTML persisted.
- All eight service search terms return real sources: skole, bolig, helse, vann, miljo (use Norwegian spelling in the UI), parkering, kultur and planer. Additional smoke queries: vanntrykk, SFO, bibliotek, luftkvalitet. Title-only hits are searchable but do not satisfy the answer evidence guard; unsupported/no-match queries remain insufficient evidence.
- Real local model harness: 13/13 passed (eight source runs and five portal answers). Each returned one whole reviewed paragraph, actual provider ollama:llama3.2:3b, synthetic=false, official provenance and no final findings. Original run times were approximately 1.0-2.1 seconds per case; exact rows are in output/real-smoke-20261021/summary.json. These are real inferences, separate from offline tests.
- Separate real correction fault injection: an initial wrong water-pressure claim was injected programmatically; the actual installed Ollama corrected it in one call, mandatory re-verification had zero findings, and rejected candidate text was not retained. Result: output/real-correction-smoke.json. This is an injected initial fault plus real correction, not an unmodified two-call model success.
- Chrome/Node browser harness passed desktop 1440x1100, tablet 820x1180 and mobile 390x844. All eight service searches, real answer, visible citations, source selection and two JSON downloads passed. Title and exact footer asserted; background decoded at 947x372; no horizontal overflow and keyboard Tab reached a link. Screenshots were visually inspected. Evidence: output/browser-real-final/.
- Honest failures and repairs: generic claim decoding initially returned too many claims/incorrect record IDs and failed safely. The real adapter now constrains selection to one actual full evidence record and locally assigns record IDs. Browser checks found the school card still used a demo-only search term and the answer button depended on echoed search input; both were fixed and the same browser check passed. One CLI message regression was repaired while preserving the old synthetic error contract. An intermediate rate-delay assertion failed; compatibility for old full-document tests was restored while real excerpt acquisition keeps the official five-second minimum.
- Known robots defect from the previous run remains fixed: longest matching disallow overrides broad Allow: /; /sok/ is not fetched. The original urllib parser had incorrectly allowed it.

Commands to rerun checks (NEW destinations required):

```powershell
python -X utf8 -m harness.offline_tests --output output/NEW-offline-log.txt
python -X utf8 -m harness.real_source_smoke --enable-local-llm --output output/NEW-real-smoke
python -X utf8 -m harness.browser_smoke --enable-local-llm --output output/NEW-browser-smoke
```

The browser check additionally uses already-installed Chrome and Node.js. These are optional manual-test tools, not Python runtime dependencies. Nothing is installed by the harnesses.

## Limitations and ownership

Coverage is deliberately small and does not include every service, every fee table or current live sensor data. Search uses exact token matching, not semantic search; answers select one eligible paragraph and may be unhelpful for broad queries. No result guarantees municipal facts are current, globally consistent or semantically true. Source conditions spanning several paragraphs still need human reading of the official page. The source review expires on 2026-10-28. An expired selection requires renewed actual review, not automatic date extension.

The older default synthetic workflow remains available only through explicit fixture/test/demo entry points. powerNeron owns this integration, extraction, approvals, server/UI, output and test harnesses. JeppeGs retains ownership of core LLM/verification/evaluation modules; none was silently rewritten. The scoped real adapter intentionally has a stricter extractive contract. The background, all eight cards, glass panels, central search, official municipality link, exact creator footer and independent student disclaimer are preserved. No logo or official-service claim was added.

No Git add, commit, push, pull, merge, rebase, reset, stash, branch change or GitHub modification was performed. Course compliance is not declared: see assignment-requirements-matrix.md for actual missing/unknown requirements.


## Historical final local verification and complete changed-file list

The observations and file list below record that earlier integration, not a fresh run or a list of files still active on main. The archived [portal record](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/search-portal.md) and [municipal source review](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/municipal-source-review.md) remain available at the historical revision and in the local archive branch. Follow the root README for current operation.

The final 13/13 real inference rerun is saved in output/real-smoke-final/summary.json. An actual `python -m hamar_agent.web --real-sources` subprocess startup also passed portal metadata (eight real documents), background SHA-256, search, real answer, mandatory verification (zero findings) and exact JSON download; artifact output/actual-server-smoke.json. The browser harness was repeated successfully against the final integrated service in output/browser-real-verified/. The final offline raw log is output/offline-evaluation-227.txt: 227 tests, zero failures/errors. JavaScript syntax checks and Git whitespace checks passed. All generated evidence is local ignored output, not source HTML.

Existing baseline HEAD remains 81645cb1d8782c7764f7264e54dbf1153cc292d4. No Git metadata mutation or GitHub operation was performed; read-only status/diff/tag inspection only. Existing background SHA-256 remains f87040eceeb4e9be60bc1c4ef517fd40d5bb44b166700e1922289029d01a4242. Core provider/correction/verification/revision/parser/shared-schema files compare unchanged to HEAD.

- AGENTS.md
- README.md
- SPEC.md
- docs/full-system-contract.md
- docs/full-system-web.md
- docs/search-portal.md
- docs/source-review-process.md
- hamar_agent/__main__.py
- hamar_agent/html_extract.py
- hamar_agent/portal.py
- hamar_agent/portal_sources.py
- hamar_agent/web.py
- hamar_agent/web_assets/app.js
- hamar_agent/web_assets/index.html
- docs/approved-service-pages.json
- docs/assignment-requirements-matrix.md
- docs/municipal-source-review.md
- docs/real-source-workflow.md
- docs/reviewed-service-selection.json
- eval/test_municipal_workflow.py
- eval/test_robots_policy.py
- hamar_agent/municipal_import.py
- hamar_agent/real_sources.py
- hamar_agent/robots_policy.py
- harness/browser_smoke.cjs
- harness/browser_smoke.py
- harness/offline_tests.py
- harness/real_source_smoke.py

## Historical verification observation recorded on 2026-10-21

The following observation is preserved verbatim from the former internal preparation note `docs/compulsory-2-report-preparation.md` before its removal. It describes that audit and its worktree, not current verification or the present catalog state:

> On 2026-10-21 this audit reran 229 offline tests successfully; the opt-in synthetic Ollama smoke was attempted but the local model runtime returned HTTP 500. The municipal catalog required by the real-source harness is absent from this worktree, so no new real-source inference result is claimed.

The 229-test audit is a separate historical observation. It must not be combined with the other test suites above or treated as a successful real-model run. No tests or model calls were repeated when this observation was relocated.
