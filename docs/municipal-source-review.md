# Municipal source review: pending activation

## Authority and review scope

The user authorized www.hamar.kommune.no as the authoritative domain and /meny/ for bounded discovery, and required a source-review report before enabling application retrieval. This is not a blanket approval of all pages. Existing design, code and student ownership boundaries are preserved. No production source approval, catalog import, Ollama processing of municipal text, live application mode or Git publication was enabled during this review.

The menu was inspected through the research browser. Five exact candidate pages were separately checked in a bounded administrative review: normal TLS, public-address pinned connections, no redirect, 10-second socket timeout, 512 KiB HTML limit, UTF-8 and five-second rate gate. Raw municipal bodies were held only in review memory, not stored in Git, a catalog or application results. This administrative review is distinct from approval-enforced application ingestion. It cannot establish that dynamic future responses contain no personal information.

## Robots and access

https://www.hamar.kommune.no/robots.txt returned HTTP 200, text/plain UTF-8. Observed SHA-256 b05e0051ef9bb54c62b82ed2dd8880438ff2a3032d0ffb40009eac5e965df6fd. Generic rules allow the proposed paths, set Crawl-delay: 5, and disallow /sok/ plus individual assets. Other named crawlers have separate exclusions. We did not use /sok/, a sitemap crawl, linked subresources or external application/login hosts.

The prior urllib.robotparser interpreted the broad Allow: / before the specific /sok/ prohibition and returned true for /sok/. robots_policy.py now selects the most specific agent groups, combines equally specific groups, applies longest matching path rules, supports wildcard/end anchors, ignores empty rules, gives Allow priority only on equal specificity, and enforces delays/rates. Invalid or excessive rates fail closed. portal_sources.validate_robots retains pinned-hash validation and delegates permission to the new policy. Eight new offline regression tests cover this issue.

HEAD requests for /vann-og-avlop/, /parkering/ and /klima/ each returned HTTP 200, text/html; charset=utf-8, with no Location, WWW-Authenticate, Content-Encoding or X-Robots-Tag observed. Subsequent limited review GETs for all five candidates passed existing strict transport checks. Public status and robots permission do not establish a license, general reuse entitlement or absence of personal data. Reuse/AI-specific conditions have not been fully established and must not be asserted as approved.

## Candidate list, not an executable allowlist

| Exact URL | Review finding | Activation status |
| --- | --- | --- |
| https://www.hamar.kommune.no/klima/luftkvalitet-i-hamar/ | Substantive candidate, but subsequent visual/text review found a named photo credit. 134200 raw bytes; main extraction succeeds with 39 paragraphs / 2566 characters and does not flag the name. This demonstrates why pattern checks are insufficient. | Blocked under the current full-document privacy boundary |
| https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/ | Useful service article, 157087 bytes. Main extraction rejects a possible contact/number pattern; four article elements make a generic article selector ambiguous. Do not relax or bypass that rejection blindly. | Blocked pending exact extraction review |
| https://www.hamar.kommune.no/vann-og-avlop/ | Category hub, 122718 bytes. Main extraction has no eligible text; multiple article boundaries. Mostly navigation, not a useful answer corpus. | Discovery/reference only |
| https://www.hamar.kommune.no/parkering/ | Category hub, 120275 bytes. Main extraction empty; article extraction returns only 27 characters. Not substantive evidence. | Discovery/reference only |
| https://www.hamar.kommune.no/klima/ | Category hub, 123445 bytes. Main extraction empty; multiple article boundaries. | Discovery/reference only |
| https://www.hamar.kommune.no/drikkevann/ | Research-browser review exposed named employee/contact information. No application retrieval or indexing performed for this page. Personal details are intentionally omitted from this report. | Excluded under current full-document privacy boundary |

No email-pattern match is not proof of a non-personal document. Institutional contact information is also rejected conservatively by the current extraction pattern. The air-quality review hashes were raw 6b95ab53e7a3d341c8bacd9c9e9590cc4eb7b699c52d2f7cee88f10d24599c01 and extracted main 2db634468ca8bdaa9a628fd39421c72c80750a5d80404d7ec0c35aa8a8ba9150. They are observations only, not approval assertions or permission to retrieve changed content.

## Next integration boundary

Before activation, identify a page or municipality-provided non-personal export that meets the whole-response privacy boundary, and finish access/reuse-condition review, with an expiring manifest entry and exact extraction/hash policy. The current full-response privacy rule cannot be replaced silently with extraction-only redaction. Keep both default registries empty until that boundary is satisfied. Import a reviewed snapshot into a new local ignored catalog with its actual original retrieval timestamp, then start with that catalog and an explicitly selected real provider, never a demo fallback.

JeppeGs's existing Ollama summarizer and correction adapter both reject non-synthetic inputs. Real support must be an explicit agreed extension, with synthetic=False retained, verified source provenance supplied by the catalog loader, the existing verifier, one correction at most and no mock fallback in real-source mode. Do not relabel municipal sources synthetic or silently duplicate/replace his implementation. Current search may use a validated real catalog, but real AI answers are not yet enabled. Web defaults also still use synthetic demo data unless a reviewed catalog or --empty-index is explicitly selected. That default is not a real-source mode.

## Validation and publication

193 complete offline tests passed with socket creation and DNS blocked: existing 185 plus eight robots regressions. No municipal content was used as an offline fixture. The site photo-credit name and personal contact details are intentionally omitted from this report. No provider/shared-schema/design files were modified in this review. No commits, pushes or merges were performed. Implementation remains on feat/full-system-web; only the robots implementation, its test, portal_sources integration and this report changed.


## Current real-source update

The user subsequently approved transient official HTML acquisition with retention limited to individually reviewed non-personal service excerpts. Earlier missing-adapter/full-document-only statements above describe the historical baseline. Eight sources and 39 paragraphs now run through the real-source adapter, mandatory strict verification and bounded correction. See [current implementation and commands](real-source-workflow.md) and [actual assignment matrix](assignment-requirements-matrix.md). Normal web startup is now real mode; use --demo explicitly for offline synthetic testing. No existing provider files/shared schemas were changed. This user policy does not override stricter course-assignment requirements.
