# Remove manual workflow and JSON controls from the website

Sanitized request and acceptance criteria: remove visible JSON export controls, source selection and the controlled-workflow panel; retain independent municipal search, real Ollama answers, visible official citations, backend export, privacy filters and mandatory source verification. No source content, hashes, expiry changes or Git remote operations.

## Implementation

- `hamar_agent/web_assets/index.html`: removed the answer download button and the complete manual source/workflow/result panel.
- `hamar_agent/web_assets/app.js`: removed manual source loading/run/export handlers, export-only result IDs, unused label dictionaries and raw JSON presentation. Kept technical provenance/warnings, official citation cards, conversation reset, input privacy checks and independent search/AI flows. Technical-details summary no longer mentions JSON.
- `hamar_agent/web_assets/style.css`: removed styles exclusive to the removed panel and JSON blocks.
- `eval/test_web.py`: existing page test now also asserts removed controls are absent; existing backend run/download and session tests remain intact.
- `harness/browser_smoke.cjs`: asserts removed controls are absent and inspects API responses using browser-test-only instrumentation instead of reading rendered JSON. Backend export is still checked using its authenticated HTTP endpoint, without adding UI controls. Existing search, privacy, follow-up, reset, official-link, insufficient-evidence and responsive checks retained.
- Python application/server, workflow, verifier, providers and approval manifests are unchanged. Existing server serves frontend assets from disk; no restart or duplicate listener was needed. Remote access remains disabled.

## Verification

- Final offline suite: 282 tests, zero failures/errors (`output/ui-removal-offline-final-20261023.txt`). Sockets and DNS blocked by the harness.
- JavaScript syntax checks passed for app.js and browser_smoke.cjs. Final `git diff --check` passed.
- Chrome/Node driver against actual `http://127.0.0.1:8000`: final exit 0; eight category searches, real llama3.2:3b answers, official citations, one authenticated backend export, privacy rejection without requests, follow-up/reset isolation, safe insufficient-evidence results, network failure feedback and desktop/tablet/mobile checks passed. No JavaScript exceptions, console errors or HTTP failures.
- Exact building question returned `evidence_checked` and the official `https://www.hamar.kommune.no/byggesak/bygge-uten-a-soke/` citation. Artifacts: `output/ui-removal-browser-final-20261023/`.
- First browser run exposed one leftover removed-button reference in conversation reset. Fixed and reran the entire driver successfully. CSS review also removed a dangling selector left during removal of JSON-only styles.
- The final CSS cleanup only removes that dangling prefix from the loading-message selector; the successful full browser run began before this final cleanup. No claim is made that its initial desktop screenshot loaded that last CSS cleanup.

Sources, hashes and approval expiry remain unchanged. No commit, push, merge, pull request, tunnel or access grant was performed.
