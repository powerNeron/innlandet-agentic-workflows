# Searchable Hamar information portal

## Start (Python 3.12, standard library only)

```powershell
cd C:\Users\LINDA\PycharmProjects\innlandet-agentic-workflows-full-system-web
python -X utf8 -m hamar_agent.web --port 8000
```

Open http://127.0.0.1:8000. Stop with Ctrl+C. No packages, credentials, live fetching, model downloads or paid APIs are required. In PyCharm run module hamar_agent.web with --port 8000 and the repository root as working directory.

The Norwegian homepage provides a prominent topic search, category filters, ranked results, evidence/answer panel, citations, provenance, warnings and JSON download. It clearly links to https://www.hamar.kommune.no/ and identifies itself as an independent student project. The former source-run UI is retained under the developer details panel.

## What is real, what is synthetic

The keyword/full-text search engine is real: search.py builds an inverted index over every paragraph, uses Unicode case-folded tokenization, conjunctive keyword matching and BM25-style ranking with title weights. It is not a hardcoded search-result list. Queries ignore a small Norwegian stopword list. Search is word-based, not stemming, semantic/vector search, or whole-website search. At most 200 reviewed documents, 512 KiB text per document and 20 results per query are allowed. The current UI uses up to ten search results and three answer sources.

Default documents are eight explicitly fictional service examples from a hash-pinned, labeled portal-synthetic.json fixture. They are not Hamar facts or copies of municipal pages. Their URLs and retrieval timestamps are null; the UI says no network retrieval occurred. Indexed-at timestamps record when the local corpus was loaded. --empty-index starts with no demo corpus and honestly returns no evidence.

The seven main category titles were referenced from the user-specified official menu https://www.hamar.kommune.no/meny/ on 2026-10-21. This was design-reference browsing only, not an approved application ingestion. Category titles/links are navigation metadata, never page approvals. No links from that menu are followed automatically.

## Query -> evidence -> answer

POST /api/search searches the in-memory reviewed index; it never crawls or downloads. POST /api/answer selects matching paragraphs, gives them globally unique document:paragraph IDs, and passes that Source through the existing run_workflow, configured summarizer, verifier and optional bounded correction. The existing CLI/source workflow remains available unchanged alongside portal routes.

Every answer includes query, answer_status, coverage notice, message, result (existing additive WorkflowResult, or null), and citations. Each citation records paragraph ID, source ID/title, exact source URL, original retrieval timestamp, index timestamp, raw/extracted hashes, category, synthetic flag and approval expiry when applicable. A title match without matching paragraph evidence is insufficient. Empty/no-hit searches never call a provider. Invalid references/unsupported numbers remain findings, never a claim of truth.

The default provider is JeppeGs's MockSummarizer. It produces source extracts, not real AI answers; the UI says so. The current mock intentionally refuses non-synthetic sources. A real reviewed catalog therefore remains searchable but returns provider_unavailable for answers until a compatible real adapter is injected. No source is falsely relabeled synthetic to bypass that contract.

WorkflowService/PortalService accept the existing summarize(Source) protocol and correction callback via trusted Python configuration. The query is data in the prepared source title, not a new assumed Ollama method. The real Ollama adapter and its query/correction behavior still belong to JeppeGs and require interface agreement. No shared schema or JeppeGs module is modified.

## Approved real catalogs (offline loading only)

The default APPROVED_PAGES and HTTP_APPROVALS mappings are empty. No web endpoint can approve a URL, upload a page, change provider configuration or enable fetching. A search request accepts only query and optional category. Existing Host/Origin/token checks, body limits, CSP, safe textContent rendering and loopback bind remain in effect.

After a separate individual source approval and offline import (see source-review-process.md), load its generated catalog without any network access:

```powershell
python -X utf8 -m hamar_agent.web --port 8000 --empty-index --approvals LOCAL_APPROVALS.json --catalog LOCAL_CATALOG.json
```

Repeat --catalog for multiple individually reviewed catalogs. The loader rechecks source identity, approved URL, category, exact reviewed text/raw hashes, expiry and paragraph structure. Tampering or expired/unapproved records fail startup. The live-fetch flag is never implied. Dates automatically exclude expired documents from search while running; revoke approvals by restarting with a revised manifest/catalog. No persistent background crawler is installed.

## Privacy, security and coverage limits

Do not enter names, addresses, personal identifiers, contact or health information. Queries are POST bodies, not URL query strings; the server does not log them. Obvious email/long-number/URL inputs are refused, but this is not a personal-name detector or a general privacy guarantee. Answer records are held only in the bounded in-memory result store (16 results), and disappear at restart.

Entire received responses, including robots.txt, require non-personal-data eligibility review before live retrieval. Receiving a changed response already processes its bytes; a hash/privacy pattern filter cannot undo that. If that boundary cannot be assured, do not enable live fetching. Use reviewed non-personal static exports instead. The default synthetic application remains safe without that unresolved live-data guarantee.

The portal never promises complete municipal coverage or up-to-date rules, deadlines or medical/legal advice. Excerpt matching is traceability, not semantic fact-checking. No-result means missing indexed evidence, not absence of a municipal service. Use official sources for decisions. General relevance, paraphrase understanding and source freshness beyond explicit expiry still need evaluation.

## Module ownership

powerNeron: portal/search, approvals and ingestion, extraction adapter, web/CLI orchestration, JSON envelopes, UI and integration/security tests. JeppeGs: real Ollama adapter, summarization, verification logic, correction provider and LLM evaluation. Existing shared contracts remain unchanged; adapters must be coordinated before real integration.


## Validation record

All 159 offline tests pass with socket creation and connections blocked globally. The 45 portal-specific tests cover full-body relevance and title weighting, Norwegian tokenization, categories, insufficient evidence, provenance, HTML boundaries/active content/login/noindex/privacy guards, explicit approvals and expiry, immutable defaults, public-IP pinning/TLS/redirect handling, robots policy/rate limits, size/type/hash checks, snapshot/catalog integrity, web requests and sanitized errors. Existing workflow/CLI/storage tests still pass.

A separate actual loopback HTTP check and headless Chrome test demonstrated category loading, keyword search, verified mock excerpts and JSON download. External DNS was disabled for Chrome and the Python smoke permitted only 127.0.0.1. Homepage and results screenshots were visually inspected. No claim of real municipal coverage or real-model answer quality follows from these tests.


## Integrated runtime update

The earlier missing-adapter limitation is superseded by [the current integration report](meetings/ollama-integration.md). CLI and web now accept --provider ollama --model llama3.2:3b --ollama-timeout 90. Default remains mock; optional --fallback-to-mock is labeled and never implicit. The actual provider remains synthetic-only. All source approval boundaries and empty live registries remain in force.
