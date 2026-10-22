# Local municipal source proposal review

Run from the project root. The process is offline and reads only a human-prepared, privacy-screened plain-text proposal. Raw HTML acquisition and snapshot import remain disabled.

```powershell
New-Item -ItemType Directory -Force output\proposals, output\source-review | Out-Null

python -X utf8 -m hamar_agent.source_updates compare `
  --approvals docs/approved-service-pages.json `
  --catalog output/municipal-catalog.json `
  --candidate output/reviewed-candidate.json `
  --output output/proposals/hamar-sfo-NEW.json

python -X utf8 -m hamar_agent.source_admin review `
  --proposal output/proposals/hamar-sfo-NEW.json `
  --approvals docs/approved-service-pages.json `
  --catalog output/municipal-catalog.json

python -X utf8 -m hamar_agent.source_admin decide `
  --proposal output/proposals/hamar-sfo-NEW.json `
  --approvals docs/approved-service-pages.json `
  --catalog output/municipal-catalog.json `
  --decision approve `
  --reviewer-role source-reviewer `
  --privacy-reviewer-role privacy-reviewer `
  --source-checked --privacy-checked --service-facts-checked `
  --confirm "approve hamar-sfo" `
  --output output/source-review/hamar-sfo-DECISION.json

python -X utf8 -m hamar_agent.source_admin activate `
  --decision-record output/source-review/hamar-sfo-DECISION.json `
  --output output/source-review/hamar-sfo-ACTIVATION.json
```

The reviewer must independently open the official source in a normal browser and compare the URL and each proposed excerpt, including numbers, dates, fees, eligibility, deadlines, negations and conditions. Review privacy and remove unrelated names, individual contacts and personal records before preparing the candidate. Do not paste raw HTML or save it to the project. The CLI binds the proposal's old excerpt and approval metadata to the current local approval manifest and catalog, validates exact official HTTPS scope, hashes and the existing privacy screen; those mechanical checks do not replace human review.

`decide` requires explicit source and privacy reviewer roles, all three review confirmations for approval, and an exact typed decision. It writes a new JSON decision record exclusively and never overwrites one. The record contains source identity and hashes rather than excerpt text. Reviewer roles are local self-attestations; the current app has no independent identity/authentication system. A rejection can be recorded without asserting approval. An approval is only `approved_pending_activation_review`; it does not make candidate text available to search or AI.

`activate` is an explicit control and currently fails closed, writing a separate activation-attempt record with exit code 3. The current policy disables raw HTML/snapshot ingestion, while the production approval contract requires reviewed source-byte and robots provenance hashes. A sanitized text proposal cannot truthfully provide those fields. Do not bypass that blocker, reuse stale hashes, or treat this record as source approval. A future privacy-approved, pre-sanitized provenance contract and genuine reviewer authorization are required before activation can be implemented. Expired approvals (including 2026-10-28) cannot be renewed through this command. Active manifests and catalog remain unchanged.
