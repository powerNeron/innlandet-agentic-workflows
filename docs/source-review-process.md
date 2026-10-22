# Individual source review and catalog management

## Default state

No real URL is approved. docs/approved-pages.example.json is an empty manifest, not permission to fetch Hamar pages. No page, redirect target or URL found by search is automatically admitted. The menu and homepage links are external references only.

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

## Import an already reviewed snapshot (no network)

Use a manifest and files containing only eligible non-personal material, with a real recorded original retrieval time:

```powershell
python -m hamar_agent.portal_sources import-snapshot --approvals LOCAL_APPROVALS.json --source-id APPROVED_ID --snapshot REVIEWED_PAGE.html --robots-snapshot REVIEWED_ROBOTS.txt --retrieved-at ORIGINAL_ISO_TIMESTAMP --output output/NEW_catalog.json
```

The output parent must already exist; the destination must be new. The importer validates current approval, robots permission/hash, raw/extracted hashes, size, UTF-8, extraction and provenance. It stores only reviewed extracted text plus metadata, not raw HTML or response headers. Load the catalog in the local server with --catalog and --approvals. Existing CLI schemas, legacy fixtures and text/plain retrieval are unchanged.

## Live HTML retrieval is disabled

Live HTML retrieval and HTML-based approval import currently fail closed, including
`portal_sources fetch-reviewed --enable-live` and the administrative importer.
Filtering after the response arrives cannot prove that personal information was
never acquired or processed. These paths must fail before DNS or connection
setup. Do not attempt live municipal requests. The existing reviewed local
catalog and normal portal/search workflow remain available while their approvals
are current. Snapshot import remains an explicitly offline operation.

The historical transport protections below described the earlier implementation
and did not establish the assignment's no-personal-data boundary. They must not
be interpreted as authorization to retrieve pages. Re-enable live ingestion only
if an approved input format guarantees personal data is not received.


## Current real-source update

The previous application decision to allow transient HTML acquisition was superseded by the strict assignment privacy requirement. Eight reviewed source records and 39 retained paragraph hashes are still in the repository, but their approvals expire on 2026-10-28 and are not renewed. Use the existing local catalog only while current. See [current implementation and limitations](real-source-workflow.md) and [assignment matrix](assignment-requirements-matrix.md). Use `--demo` for synthetic offline testing.
