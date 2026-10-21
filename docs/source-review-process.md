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

## Optional explicitly enabled reviewed fetch (not used during development)

Only after the boundary and individual manifest entry have been separately approved:

```powershell
python -m hamar_agent.portal_sources fetch-reviewed --enable-live --approvals LOCAL_APPROVALS.json --source-id APPROVED_ID --output output/NEW_catalog.json
```

Without --enable-live or without that exact current approval, this fails before DNS. It never discovers URLs or follows redirects. This command is not an approval request and must not be run with real sources until authorized.

The new HTML-capable fetcher is separate from the existing text/plain-only retriever. It fetches reviewed robots.txt first (64 KiB cap), checks its pinned hash and rules, then fetches only the approved page. Requests use a dedicated agent, at least two seconds between requests, and obey stricter robots crawl-delay/request-rate. Excessive robot delays require a separate scheduling decision. No retries, cookies, authentication, proxies or linked subresources.

Only approved canonical host URLs are allowed. All DNS answers must be public/global; private, loopback, link-local and mixed answers are refused. The HTTPS connection pins a validated numeric address while retaining original-host TLS certificate validation, preventing a second hostname lookup during connection. Each socket has a ten-second timeout; bodies have an independent 512 KiB cap. Only HTTP 200 and expected text/html or text/plain with strict UTF-8 decoding are accepted. Redirects, login status, compression, ambiguous headers, noindex, size and hash changes fail closed; resources close on error.

Limits: socket timeout is not a total deadline; rate limiting is per process, not distributed. DNS/trust configuration is environmental. Exact-byte pinning deliberately rejects dynamic page changes. No response-hash check can prevent already receiving unexpected personal bytes. The registry stays empty until these limitations are resolved for each proposed source.
