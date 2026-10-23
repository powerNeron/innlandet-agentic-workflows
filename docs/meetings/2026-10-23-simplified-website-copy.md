# Simplified website text and layout

Sanitized request: simplify the welcome/subtitle/search guidance and AI description, remove the three-step explanation and prominent source-count/status strip, and retain privacy, limited coverage and verification disclosures in concise accessible help. Preserve search, AI answers and official citations. No source changes or Git publication.

## Changes and acceptance

- Updated `hamar_agent/web_assets/index.html` with the requested exact Norwegian text, visible search label and placeholder. Removed the step list, long inline input warnings, reviewed-source explanation and source badge/count. Kept the AI heading and replaced its description as requested.
- Replaced the lengthy bottom trust panel with a closed-by-default native `details` element labelled “Om tjenesten”. It includes a short privacy reminder, limited/non-live source coverage, the limits of citation matching and the independent student-project status. Both inputs reference the concise privacy reminder through `aria-describedby`.
- Removed obsolete mode/count DOM updates from `app.js` so initialization cannot fail on removed elements. Synthetic/demo identification is still provided by existing answer/provider messaging.
- Removed styles exclusive to the removed sections and added small styles for subtitle, search label and help. No backend Python, privacy filter, model workflow, verifier, citation policy or source approval data was changed.
- Updated the existing `eval/test_portal.py` privacy-guidance assertion to check its new help location. Extended the existing Chrome driver to verify exact copy, absence of removed blocks, accessible help and an actual mobile building-question AI answer.

## Verification

- `python -X utf8 -m harness.offline_tests --output output/simple-copy-offline-final-20261023.txt`: 282 tests, zero failures/errors, sockets and DNS blocked. The initial run found the old privacy-copy assertion; updated it to the required new location and reran successfully.
- `node --check` passed for frontend app.js and harness/browser_smoke.cjs; `git diff --check` passed.
- Chrome/Node regression against the existing actual `http://127.0.0.1:8000` server: exit 0. Exact requested copy and collapsed/openable help passed; eight category searches, desktop/tablet/mobile layout, real llama3.2:3b answers, official links, backend export, follow-up/reset isolation, privacy rejection and insufficient-evidence refusal passed. No JavaScript exceptions, console errors or HTTP failures.
- Mobile building question explicitly returned `evidence_checked` from llama3.2:3b with the official building-service link and no horizontal overflow.
- Artifacts: `output/simple-copy-browser-20261023/` and the offline log above. Desktop and mobile AI screenshots were visually inspected.

Existing local server was reused. Source content, hashes and expiry dates remain unchanged. No commit, push, merge, external access or new service was enabled.
