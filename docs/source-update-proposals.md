# Controlled source update proposals

## Current safety boundary

The production application does not retrieve municipal HTML. The current privacy policy forbids acquiring or parsing raw HTML because unrelated personal information can be present before any extractor or filter runs. `portal_sources fetch-reviewed --enable-live` and snapshot import therefore fail closed. This UI does not expose an update button, and ordinary/AI searches never fetch pages.

The additive `hamar_agent.source_updates` command compares sanitized, human-prepared plain-text excerpts with the current reviewed catalog. It is proposal-only: it cannot edit the catalog or approval manifest, enable excerpts for retrieval, change approval expiry, or connect to a network. The report marks changed text for human review and records the previous expiry unchanged. It applies size, exact-source, timestamp, and conservative privacy-pattern checks. Those checks are defense in depth and do not replace a human review for names or contextual personal information.

## Manual update review process

1. Open only one of the exact URLs in `docs/approved-service-pages.json` in a browser and compare the page to its approved excerpts. Do not use a crawler, page mirror, browser extension that uploads content, or raw HTML export.
2. Review the page for people, personal/contact details, login-only material, hidden/active content and changed service conditions. If personal-data absence is uncertain, stop and do not prepare a candidate.
3. Copy only the relevant non-personal service paragraphs into a UTF-8 JSON candidate. Include its exact approved `source_id` and `url`, a timezone-aware observation timestamp, and `paragraphs`. Do not include page source, scripts, names, contact details or unrelated content.
4. Compare it to the existing local catalog with a new output path. Review both the old and proposed excerpts in the JSON report. A changed/expired record remains unavailable for update until a person completes and documents a fresh approval through the established source-review process.

Example candidate shape (synthetic placeholder text only):

```json
{
  "source_id": "hamar-sfo",
  "url": "https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/",
  "observed_at": "2026-10-21T12:00:00+02:00",
  "paragraphs": ["Syntetisk eksempeltekst; erstatt kun etter menneskelig gjennomgang."]
}
```

Command (the output path must not already exist):

```powershell
python -X utf8 -m hamar_agent.source_updates compare `
  --approvals docs/approved-service-pages.json `
  --catalog output/municipal-catalog.json `
  --candidate output/reviewed-candidate.json `
  --output output/update-proposals/hamar-sfo-20261022.json
```

Create `output/update-proposals` first if needed. The command prints `network_used: false`, and exclusive file creation prevents overwriting a prior proposal. It will refuse a candidate with HTML markup, contact-pattern hits, unknown source IDs, a non-exact URL, malformed timestamps or oversized content. Existing approval expiry is never renewed by this command.

## Unimplemented live update capability

Fetching and parsing an HTML response, even transiently, would cross the current no-personal-data acquisition boundary. A network allowlist, TLS, redirect denial, robots rules, timeouts and size limits cannot prove that the response contains no personal information. Therefore automatic HTTP update checks, HTTP fixture transport tests and unattended scheduling remain disabled. Re-enabling them requires a separately approved source delivery format or a documented privacy decision that permits transient receipt and processing of the full response. No real pages were fetched for this implementation.
