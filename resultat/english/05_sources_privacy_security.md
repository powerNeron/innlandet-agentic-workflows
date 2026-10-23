# Source verification, privacy and security

| Measure | Value | Source |
|---|---|---|
| Approved documents | 8 | docs/approved-service-pages.json |
| Approved paragraphs | 39 | docs/reviewed-service-selection.json |
| Stored positive answers independently rechecked | 17 | logger/real-smoke/*.json |
| Claims with exact support and source URL | 17 | logger/real-smoke/*.json |
| Approval expiry | 2026-10-28 | docs/approved-service-pages.json |
| New municipal live retrievals | 0 | run_experiments.py |

M1 contains 18 positive model cases. Only 17 separate positive output files exist because one repeated SFO run is not stored separately. The summary grounded_claims=14 is a partial sum; four positive question rows omit this field. citation_checks_passed=23 also includes correct refusals, not 23 positive citations.

The backend requires a verbatim complete source paragraph and valid provenance. This does not certify semantic truth or complete context. Human source approval remains a central trust boundary. An isolated synthetic counterexample showed that a verbatim instructional paragraph can receive no verification findings.

Permissions were tested using invalid Host, Origin, session token, model selection, unknown request fields and an oversized request. The privacy case uses invented contact text only. These rejections made no model calls. G tests verify that both external enablement and privacy flags are required, and that all local checklist fields must be set before an approval record is created. Even such a record cannot activate a source. Reviewer roles are self-attested, not identity-authenticated.

No raw HTML was fetched. Local catalog retrieval is not live website search. Historical HTML processing and complete institutional privacy compliance remain unresolved. A total of 43 older evidence files, including the catalog and approval manifests, were checked unchanged against previous SHA-256 values. See ../logger/historisk-hashkontroll.json. Real session tokens and browser profiles are not published.
