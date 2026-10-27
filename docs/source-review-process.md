# Individual source review and catalog management

## Default state

The code's implicit `APPROVED_PAGES` registry is empty. The checked-in `docs/approved-service-pages.json` separately records eight expiring URL-and-paragraph approvals for the existing local catalog; it does not enable fetching. `docs/approved-pages.example.json` is an empty example. No page, redirect target or URL found by search is automatically admitted. The menu and homepage links are references only.

Inspect defaults without network:

```powershell
python -m hamar_agent.portal_sources list
python -m hamar_agent.portal_sources validate --approvals docs/approved-pages.example.json
```

Both report an empty source list and live_enabled=false.

## Review checklist (before any application acquisition)

1. Select one exact public HTTPS page on www.hamar.kommune.no. No queries, fragments, credentials, ports, encoded/relative paths or other hosts are accepted. Exclude login-protected pages, personal cases, staff lists, meeting records and user submissions. Do not crawl the menu.
2. Establish a non-personal full-response delivery boundary. Review the entire original document, not only the extracted main text, plus robots.txt and response headers. If personal-data absence cannot be established, stop: redaction after receiving is insufficient under this project's rule. No live municipal source currently satisfies an approved boundary here.
3. Obtain a reviewed static snapshot outside the application, under separately authorized review, and record its actual original retrieval time. Do not fabricate a current timestamp for old files. Keep raw snapshots outside Git. Review robots allow/disallow, crawl-delay, request-rate and HTML/header noindex instructions.
4. Select a single main or article extraction boundary. Confirm only public informational text remains: scripts, navigation, forms, footers, hidden nodes and active content are excluded. Password inputs and noindex documents are refused. Contact patterns trigger rejection, but no automated extractor guarantees privacy.
5. Record a source ID, exact URL, manually reviewed title/category, reviewed_on, expires_on (recommend short review periods), rationale, no_personal_data=true only when justified, content_type, content_tag, and exact SHA-256 hashes for original bytes, normalized extracted text and reviewed robots bytes. Changes to any body/hash require another review. No_personal_data is a review assertion, not an automatic detector.
6. Have the user explicitly approve that individual entry. Edit a local trusted manifest only after approval. Do not add it to production automatically. Keep review records free of personal data and credentials.

PageApproval in portal_sources.py defines the exact manifest fields. The default file is [] so no plausible example entry can accidentally enable live fetching. validate rejects invalid, duplicate, expired and future approvals. Administrative commands are terminal-only; the web UI has no approval controls.

## Raw HTML acquisition and import are disabled

The application refuses both `fetch-reviewed --enable-live` and `import-snapshot`, before DNS, network requests, or reading a snapshot file. A local HTML file can also contain personal information, so parsing it before excerpt filtering is not an acceptable privacy boundary. The real workflow reads only the existing approved local catalog; synthetic fixtures remain available for offline tests and demos. There is no supported production command for turning raw HTML into a catalog.

## Live HTML retrieval is disabled

Live HTML retrieval and HTML-based import fail closed, including
`portal_sources fetch-reviewed --enable-live`, `portal_sources import-snapshot`,
and the administrative importer. Filtering after acquisition cannot prove that
personal information was never received or processed. Do not attempt live
municipal requests or raw-snapshot imports. The existing reviewed local catalog
and normal portal/search workflow remain available while their approvals are
current. The in-memory extraction/import helper is exercised only with synthetic
test data; it is not a supported production ingestion path.

The historical transport protections below described the earlier implementation
and did not establish the assignment's no-personal-data boundary. They must not
be interpreted as authorization to retrieve pages. Re-enable live ingestion only
if an approved input format guarantees personal data is not received.


## Current real-source update

The previous application decision to allow transient HTML acquisition was superseded by the strict assignment privacy requirement. Eight reviewed source records and 39 retained paragraph hashes are still in the repository, but their approvals expire on 2026-10-28 and are not renewed. Use the existing local catalog only while current. See [current implementation and limitations](real-source-workflow.md) and [assignment matrix](assignment-requirements-matrix.md). Use `--demo` for synthetic offline testing.

## Controlled expiry-only renewal

The owner may personally document the current source, service-fact, privacy and permitted provenance checks using the recorded project-owner authorization. This does not claim independent municipal/instructor approval. The new `prepare-renewal`, `check-renewal` and explicitly confirmed `activate` path is limited to unchanged approved content; all original hashes and review/retrieval timestamps are preserved, and new review dates/decisions are recorded in the transaction audit. An unchecked owner authorization alone cannot activate anything. Legacy changed-content activation and all HTML acquisition/import remain blocked.

Follow the [current owner-review and transaction procedure](../README.md#owner-controlled-renewal-review-check-activate). It requires current UTC-day reviews, hash-bound sanitized provenance, consistent approval/selection/catalog inputs, stopped application processes, a new audit directory and explicit confirmation. Partial failures roll back or retain a recovery lock/journal; do not restart after an interrupted transaction until verified recovery. No actual November renewal has been performed; all eight recorded expiries remain 2026-10-28.

The `complete-renewal-technical` command fills only verifiable local metadata, provenance-file paths and file digests, preserving an original draft and a local owner worksheet. Human review flags, reviewer/decision fields and actual source-observation timestamps remain separate; the tool never turns a successful hash comparison into source freshness or privacy approval. See the root README for its command and the exact owner-assessment procedure.
