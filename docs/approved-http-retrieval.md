# Isolated approved HTTP transport - KIUA-2003

## Scope and branch

feat/approved-http-retrieval starts from feat/source-workflow (daa5e0d), not feat/json-result-saving. Only retrieval.py, its tests and this document are added. PRs 2 and 3 are unchanged. The separate evidence fix e833983 remains excluded. No existing interface, schema, CLI, fixture loader, storage or summarizer is changed, and retrieval is not connected to the workflow.

## Approvals and disabled production access

HTTP_APPROVALS is an immutable empty mapping. HttpApproval records are frozen and bind a source ID to an exact HTTPS URL, rationale, review/expiry dates and optional SHA-256. No real municipality URL is approved. The default fetch_document call rejects all source IDs before constructing an opener. Only tests inject synthetic approvals with example.invalid URLs and mocked openers. Programmatic registry injection is trusted configuration, not a security boundary against arbitrary Python code; do not use it to bypass approval.

## Transport controls

- Source-ID lookup only; requests always use the exact registry URL.
- Narrow lowercase DNS HTTPS URLs with explicit paths; no credentials, ports, IP literals, whitespace, controls, backslashes, fragments, queries or relative path segments.
- Normal default TLS certificate and hostname validation.
- Explicit urllib opener rejects redirects (including same-domain redirects), disables environment proxies and adds no cookie or authentication handlers. No retries, crawling or subresource retrieval.
- GET with text/plain acceptance and identity encoding; socket timeout 10 seconds.
- HTTP 200 and an unchanged response URL required before body reading.
- One text/plain Content-Type header with an explicit UTF-8 charset; duplicate charset parameters, compression and invalid UTF-8 are rejected.
- 512 KiB maximum, checked against Content-Length where supplied and independently during bounded streaming. Invalid, duplicate and inconsistent lengths fail closed.
- Optional SHA-256 matches exact received bytes, without newline normalization. Always return the computed hash with decoded text in an isolated RetrievedDocument record.
- Responses use context managers; HTTPError bodies are closed without reading. Network, TLS, decoding and HTTP transport failures become sanitized RetrievalError messages without response text. Registry validation failures occur before requests.

## Limits and privacy

This module cannot guarantee a public response is free of personal data. Downloading, decoding or hash-checking a body already receives/processes it. SHA-256 is integrity, not privacy or semantic fact-checking. A live source needs a separately approved non-personal delivery boundary before enabling any real registry entry. Do not approve general municipal pages merely because they are public.

The socket timeout is not a strict overall deadline. Byte limits constrain body memory, not a complete HTTP header or network-resource budget. DNS and trust configuration are environmental; the URL allowlist is not network-level egress isolation or a guarantee against DNS changes. No disk caching, raw response logging, HTML/PDF parsing, personal-data detector, semantic verification or downstream source conversion is included.

## Validation

Python 3.12.10: all 51 tests passed (25 existing scaffold/source-workflow tests and 26 new retrieval tests). The final full-suite run patched both socket.socket and socket.create_connection to forbid real connections. New tests also independently install these guards and mock the urllib opener. Cases cover approvals, exact URLs, TLS configuration, timeout argument, redirects, status, content type/charset/compression, length and size boundaries, integrity, Unicode, errors and resource closure.

Run normally with:

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
```

PR 3's 14 storage tests and implementation remain on its sibling branch; they are not part of this branch's 51 tests. Existing tests were not edited. No real source was fetched, package installed or paid API called.

## Decisions and next actions

User authorized isolated local implementation and tests, with no commit or remote changes. powerNeron owns this transport; JeppeGs's summarization, LLM, evidence verification and evaluation components remain separate. A future PR should target feat/source-workflow while its dependency is open. Approval is required before committing/publishing this work or enabling any real URL. Integration with real non-synthetic workflows remains future work.
