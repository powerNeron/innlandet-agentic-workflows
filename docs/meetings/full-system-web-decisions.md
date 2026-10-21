# KIUA-2003: powerNeron full-system implementation

## Authorization

User authorized a local feat/full-system-web branch from latest origin/main, integrating own modules, preserving JeppeGs's modules/shared schemas, running offline tests and building a local UI. Base: 9102ae2. No push, main modification, commit, merge or municipal approval was requested. The unrelated evidence commit e833983 is excluded.

## Decisions

Use existing verification/revision interfaces with an additive Result subclass owned by orchestration. Report the contract before any incompatible shared change; no shared schema was changed. One callback maximum, preserve original findings, recompute evidence statuses through JeppeGs's verifier, and never interpret exact_match as truth. Initial malformed output fails rather than generating placeholder claims.

Reuse one service for CLI/web. Keep live HTTP behind two explicit startup gates and the existing protected transport. Serve a minimal loopback-only web app with standard-library HTTP and static assets; no external deployment or package dependencies.

Preserve original component tests. Update only four assertions in powerNeron's tests that depended on unverified CLI output; direct shared Result and mock behavior remain tested. JeppeGs's files/tests are unchanged.

## 50/50 remaining-work coordination

powerNeron work packages: (1) workflow verification integration, (2) bounded correction orchestration, (3) source approval/retrieval integration, (4) CLI/JSON plus local HTTP/UI, (5) integration tests and own documentation.

JeppeGs work packages: (1) real Ollama summarizer adapter, (2) summary prompts/parsing and grounding, (3) verification logic and limitations, (4) correction provider compatible via an agreed wrapper, (5) LLM evaluations and own documentation.

These are ownership boundaries for balanced contribution, not a claim that component counts guarantee equal hours. Shared interfaces must be coordinated; no guessed Ollama/correction API is implemented.

## Sanitized prompt log

Request: complete powerNeron's independently owned integration/UI work on a new branch, leave main/remote untouched, retain safe defaults, block external calls during tests and report remaining provider dependencies. No credentials, personal data or real municipal documents were used.


## Final validation

Python 3.12.10: all 114 tests passed with socket.socket and socket.create_connection blocked across the complete suite (77 prior tests with updated integration expectations, 18 full-workflow tests and 19 web tests). Real loopback-only HTTP smoke passed for page, JS, approved-source listing, verified run and exact JSON download with external DNS/connections forbidden. node --check validated the browser script. No browser-rendering automation is claimed. Norwegian UI strings are written as UTF-8; no external assets are loaded.

Protected-file checks confirmed schemas.py, summarize.py, verify.py, revision.py, JeppeGs's test_summary_verification.py and all fixtures are unchanged from origin/main. No live municipal source, paid API, real Ollama provider or correction provider was invoked. Production HTTP approvals remain empty. The branch is local and uncommitted; no remote writes, main changes or e833983 inclusion occurred.


## Search portal extension decisions

User authorized local expansion into a searchable Norwegian municipal-information portal. Official menu https://www.hamar.kommune.no/meny/ was read as a design reference for seven category titles only. No municipal page was admitted to the application corpus.

Implemented a genuine full-text inverted index with weighted relevance, explicit synthetic demo collection, source/paragraph provenance, query-to-workflow evidence selection, verified answer reports, insufficient-evidence outcomes and JSON downloads. The existing CLI and run routes remain available. Added a separate reviewed HTML/text import path rather than broadening the old text/plain retriever silently.

Live HTML acquisition requires an empty-by-default registry plus explicit enablement, exact reviewed document/robots/extracted hashes, privacy review, canonical host allowlist, public-IP pinning, TLS, robots rules, per-process throttling and response limits. The browser cannot approve sources or enable live fetching. Local catalog loading never fetches pages.

Real municipal data remains blocked pending a suitable non-personal delivery boundary. The current mock refuses non-synthetic input, so real reviewed catalogs can be searched but need JeppeGs's actual provider for answers. No guessed Ollama/correction API was added. All shared schemas and JeppeGs's modules remain unchanged.


## Final portal validation

All 159 offline tests passed on Python 3.12.10 with both socket.socket and socket.create_connection blocked for the complete suite: 114 prior full-system/component tests plus 45 new portal/source tests. Source-management defaults and the empty example manifest report no approved sources and live_enabled=false. node --check passed for app.js; git diff --check passed.

A real loopback-only HTTP smoke exercised search, verified answer and exact JSON download. Headless Chrome, with external name resolution disabled, then loaded all seven categories, submitted the topic vann, displayed one relevant indexed synthetic result and two verified mock excerpts. Desktop homepage/results screenshots were inspected. No municipal data, model provider or paid API was used in application tests. Norwegian UI labels now distinguish traceability from factual correctness.

Protected-file comparison confirmed no changes to schemas.py, summarize.py, verify.py, revision.py, JeppeGs's tests or original fixtures. The new portal fixture is explicitly synthetic and hash-pinned. All work remains local and uncommitted on feat/full-system-web; no push, merge or main change occurred.
