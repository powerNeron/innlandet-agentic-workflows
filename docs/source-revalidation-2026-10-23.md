# Source revalidation status — 2026-10-23

## Decision

No municipal page was requested, fetched, or re-imported for this check. The current source-review policy in `docs/source-review-process.md` explicitly disables live HTML acquisition and raw snapshot import because the application cannot establish that personal information is never received or processed. This check therefore cannot attest to current page availability or content, and it does not renew or extend any approval.

The eight records below retain their existing `reviewed_on` value (`2026-10-21`) and `expires_on` value (`2026-10-28`). The manifests and approved local excerpts were not changed. Each source is **NOT REVALIDATED — HUMAN REVIEW REQUIRED**; a human review alone does not authorize live ingestion or bypass the privacy boundary.

## Per-source status and human review worksheet

For each source, a reviewer must open the exact official URL in a normal browser, check that the page remains public and relevant, compare the approved excerpt paragraphs listed by hash in the two manifests, and review the complete page and access conditions for personal information, robots instructions, redirects, login requirements, and material changes. Do not save or import raw HTML, copy unrelated page content into the project, or treat a page being reachable as approval. Record a decision only after resolving the privacy boundary with the course/project policy.

| # | Source ID | Official URL | Approved paragraphs | Existing review / expiry | Current status |
|---:|---|---|---:|---|---|
| 1 | `hamar-sfo` | https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 2 | `hamar-byggesak` | https://www.hamar.kommune.no/byggesak/bygge-uten-a-soke/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 3 | `hamar-folkehelse` | https://www.hamar.kommune.no/folkehelse-kunnskapsgrunnlag/ | 4 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 4 | `hamar-bibliotek` | https://www.hamar.kommune.no/kultur-og-aktivitet/hamar-bibliotek/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 5 | `hamar-kommuneplan` | https://www.hamar.kommune.no/kommuneplan/kommuneplanens-samfunnsdel/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 6 | `hamar-drikkevann` | https://www.hamar.kommune.no/drikkevann/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 7 | `hamar-parkering` | https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |
| 8 | `hamar-luftkvalitet` | https://www.hamar.kommune.no/klima/luftkvalitet-i-hamar/ | 5 | 2026-10-21 / 2026-10-28 | NOT REVALIDATED — HUMAN REVIEW REQUIRED |

### Reviewer record (complete separately for each source)

- Decision: `PENDING — DO NOT ACTIVATE OR RENEW`
- Reviewer name or authorized role: ____________________
- Review date: ____________________
- Current page accessible at exact URL (yes/no; redirects): ____________________
- Privacy and robots/access review completed (yes/no; evidence): ____________________
- Approved paragraph hashes still match (yes/no; discrepancies): ____________________
- Numbers, dates, fees, eligibility and conditions checked (yes/no; notes): ____________________
- Explicit approval to renew, if permitted by policy: ____________________
- New expiry date, only after actual approval: ____________________

Do not fill in reviewer fields or alter either manifest until a real authorized reviewer has completed the review and confirmed that the project/course privacy policy permits renewal. Expiry enforcement remains enabled; after expiry, the sources must be refused by the production workflow.

## Evidence checked

- `docs/approved-service-pages.json`: eight exact URL records, all currently marked `reviewed_on: 2026-10-21` and `expires_on: 2026-10-28`.
- `docs/reviewed-service-selection.json`: eight URL-specific records and paragraph SHA-256 lists, with the same existing dates.
- `docs/source-review-process.md`: states that live HTML requests and raw snapshot imports fail closed before network/file access and that approvals are not silently renewed.

This report records the policy blocker, not a claim that the eight live pages were visited or that their content remains current.
