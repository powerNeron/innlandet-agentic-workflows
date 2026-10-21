# Local Ollama application integration, 2026-10-21

## Preservation and ownership

Initial branch: feat/full-system-web, previously based on 9102ae2. All uncommitted portal, application, tests, documentation and both background image copies were preserved in 0f98ab9 (29 files). Backup: backup/full-system-web-before-main-20261021. Image SHA-256: f87040eceeb4e9be60bc1c4ef517fd40d5bb44b166700e1922289029d01a4242. No file was discarded. Main advanced to a21d1cc (PR #7 merge, provider work cf8608a). Regular merge 3543a1d preserved both histories with no conflicts. Unrelated e833983 is not an ancestor.

powerNeron owns runtime composition, orchestration, source restrictions, portal, CLI/server, JSON and integration tests. JeppeGs owns summarization, Ollama transport/prompts, verification heuristics, correction implementation and evaluation. Those modules and shared schemas are unchanged relative to fetched main.

## Compatibility and implementation

No shared schema changes were needed. Existing Summarizer.summarize and tuple correction callbacks still work. runtime.py adapts the actual CorrectionProvider.revise result and composes the actual Ollama classes. workflow.py retains provider correction findings and provenance, independently reverifies, and bounds corrections to one attempt. CLI and server share provider selection and dependency injection; prepared portal answers use the same service. UI labels the actual result provider, fallback and the new uncertainty/unsupported findings.

The first local structured response failed the existing paragraph_id contract. Application transport composition now requests a four-string JSON schema rather than generic JSON mode, delegating all HTTP controls to the existing provider transport. This does not guarantee valid evidence IDs. The internal _local_post import is a documented compatibility seam for a future agreed public export.

## Verification evidence

Baseline after preserving local work: 159 offline tests; after merging main: 168; final integration: 185 passing tests, including 17 new runtime integration cases. Complete suite executed with socket creation and getaddrinfo blocked, so no real network or paid API can be used. New cases cover actual provider composition with fake transport, structured format, correction results/findings, bounded unresolved correction, correction errors, explicit fallback and strict failure, uncertainty, CLI stdout/saving, portal provenance, web run/answer/download, and startup configuration.

Real local smoke tests are separate from offline results. Ollama 0.40.3 and llama3.2:3b were already installed; nothing was installed or downloaded. The first cold standalone smoke timed out. The first warm application call returned a malformed paragraph_id and failed safely. After requesting structured output, the actual CLI completed in about 3.6 seconds with provider ollama:llama3.2:3b. It produced two uncertain claims with uppercase P1/P2 IDs absent from the lowercase source IDs. The verifier correctly retained two invalid-reference findings, two uncertainty findings and one conflicting-claims finding. One real correction attempt completed but did not resolve them. This demonstrates real inference, wiring and honest failure findings, not reliable factual answers or a successful quality evaluation.

Chrome headless browser tests on desktop 1440x1100, tablet 820x1180 and mobile 390x844 passed against the actual local mock-mode server. All eight service searches worked; source selection, answer rendering, citations and two JSON downloads worked. Background decoded at 947x372 and was the active CSS image. Title and exact creator footer matched, no mobile horizontal overflow, keyboard Tab reached a link. Screenshots were captured in the system temporary folder and visually inspected. The source image is low resolution and will look softer on large screens; original asset preserved.

## Limitations and remaining work

No municipal page is approved. Both production registries remain empty; no live retrieval occurred. Existing allowlisting, robots, provenance and privacy review are preserved, not bypassed. Search coverage is eight synthetic demo documents by default. Current real Ollama summarizer/corrector explicitly refuse non-synthetic sources; JeppeGs must agree and implement real-source support before actual municipal AI answers. He also owns prompt/evaluation improvements for invalid references and unresolved uncertainty. Evidence excerpt and heuristic checks are not semantic truth verification. Model latency and cold starts vary; startup examples use a bounded 90-second timeout. Model errors never silently turn into mock answers.

The website remains bound to 127.0.0.1 with its title, independent-project notice, official external municipality link, service cards, glass panels, Mjosa background and exact creator footer. No municipality logo is used. No main push, merge, force push or branch deletion is part of publication.


An additional real local portal smoke query, `vann`, completed in 5.48 seconds using ollama:llama3.2:3b, with two claims, two citations and no final verification findings after one correction. Socket connections in this smoke were restricted to 127.0.0.1:11434. This is a separate real-model run, not part of the 185 offline tests, and does not demonstrate semantic truth or general model reliability.
