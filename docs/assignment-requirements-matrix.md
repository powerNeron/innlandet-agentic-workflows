# Current authoritative assignment matrix

Only [the official assignment supplied by the user](official-assignment-user-supplied.md) is used. The user explicitly resolved the earlier uncertainty. The superseded historical assessment is archived locally and is not published or used as an authority. No personal directories or unrelated documents were accessed in this audit.

PASS means demonstrated in the allowed project worktree. FAIL means a supplied mandatory requirement is not satisfied by the current observed implementation/artifacts. UNKNOWN means the required deliverable or approval cannot be verified from this project. Neither tests nor this matrix award a course grade.

| Mandatory requirement from supplied text | Status | Concrete evidence / unresolved item |
| --- | --- | --- |
| Identify a recurring information-work need in Innlandet | PASS | README.md, SPEC.md: Norwegian Hamar municipal service search and evidence-backed excerpts |
| Work as a pair | PASS | Both authors' existing commits and component ownership documented; exact creator footer retained |
| No collecting, storing or processing identifying personal information | UNKNOWN | Live HTML retrieval now fails before DNS in both source-management entry points. The offline snapshot importer can still parse a supplied HTML file, and this audit did not inspect the ignored local catalog or establish that every possible snapshot is non-personal. Do not claim overall personal-data compliance. |
| Respect sources; use official APIs/RSS/open documents where possible | PASS | Eight explicitly reviewed official HTTPS public pages, robots/rate/redirect/SSRF checks and no unrestricted crawl |
| No prohibited scraping or unnecessary republication | PASS | robots_policy.py, exact URL/paragraph manifests, only 39 necessary reviewed paragraphs retained; no raw municipal HTML persistence |
| Verify local language/institutions/context | PASS | Eight Hamar service categories/cards, Norwegian UI and real excerpts with official provenance; independent-project notice |
| Submission contains both report and walking skeleton | UNKNOWN | Walking skeleton exists. A complete Compulsory 2 submission report is not present/verified in the allowed worktree |
| Report describes problem, intended users and output | UNKNOWN | Supporting README/SPEC content exists; inclusion in the actual submission report is unverified |
| Report defines success and how output correctness is checked | UNKNOWN | SPEC and strict_verify provide criteria; actual report unverified |
| Report architecture covers context, stages/subagents and automatic parts | UNKNOWN | docs/full-system-contract.md and docs/real-source-workflow.md document architecture; actual report unverified |
| Report schedule works backwards from demonstration date | FAIL | No such milestone schedule or confirmed demonstration date found in this worktree; no dates were invented |
| Report risk assessment and mitigations | UNKNOWN | Implementation notes record risks/failures/limits, but actual report section is unverified |
| Report contains repository link | UNKNOWN | Repository is configured correctly; actual report artifact/link placement is unverified |
| Walking skeleton executes one real-input-to-checkable-output path | PASS | Live reviewed import, actual local Ollama and source-verified JSON/CLI/web smoke harnesses |
| README permits reproduction | PASS | README and real-source-workflow.md provide import/run/evaluation commands; approvals are explicitly expiring and renewals require review |
| Repository includes context files used by harness | PASS | AGENTS.md, SPEC.md, approval/selection manifests and synthetic offline fixtures. Generated real catalog is local ignored output reproducible through the reviewed import command |
| Technical minimum 1: input and checkable output | PASS | Actual paragraphs, exact references/quotes, numeric/condition-preserving strict gate and JSON contracts |
| Technical minimum 2: more than one stage | PASS | Approval, retrieval, extraction, indexing/search, model selection, verification, optional bounded correction, re-verification, export |
| Technical minimum 3: tools/files/external data | PASS | Actual official HTTPS import, local catalog and Ollama HTTP API |
| Technical minimum 4: automatic part | PASS | Single CLI/server request orchestrates model, verification, optional correction and export without manually driving each step |
| Systematic testing, stress testing and validation before demonstration | UNKNOWN | Current offline suite: 226 tests passed, with DNS and real sockets blocked; a synthetic 1,000-claim adversarial batch also passed. The local Ollama smoke failed because the installed runtime's CUDA kernel image is invalid; no current browser run or student demonstration evidence was supplied. Earlier real-model/browser results in `docs/real-source-workflow.md` are historical. |
| Report uses supplied LaTeX template | UNKNOWN | No .tex/.pdf report or supplied report template found inside the allowed worktree |
| NeurIPS preprint package option and checklist removal | UNKNOWN | No rendered/source report to inspect |
| Report main text is 3-4 pages | UNKNOWN | No report PDF in worktree; no personal folders searched |
| Report is in English | UNKNOWN | English implementation notes exist, but not a verified submission report |
| Appendix included | UNKNOWN | No assembled report appendix to inspect |
| Representative coding-agent prompt excerpts, maximum two pages | UNKNOWN | docs/prompt-log.md contains sanitized summaries; assembled representative excerpts and page limit unverified |
| Meeting reports show iterative reasoning, design decisions and revisions | UNKNOWN | Five setup/decision records exist, but the repository does not establish that they are reports of actual team meetings or who attended. Student confirmation or genuine meeting reports are needed; no meetings are invented. |

**Publication/merge gate: BLOCKED.** Any mandatory FAIL or UNKNOWN blocks publication and merge under the user's current conditional authorization. No two-agent dialogue engine, eight-meeting minimum, exam tag, final-white-paper format, or final-exam deadline is used as a requirement: none was included in the authoritative text supplied here.

## Follow-up privacy review

Portal queries in both real and synthetic UI modes are constrained to a fixed allowlist of general service-topic words. The browser rejects other text locally, clears the input, and sends no search request; the server independently rejects free-form terms and never echoes rejected text. This closes the UI/API query path for names, addresses, and arbitrary free text that are not approved service terms.

The live-fetch privacy bypass has been removed from `ReviewedFetcher`, its private `_get` seam, `fetch-reviewed --enable-live`, and the administrative import CLI. Regression tests assert no DNS, socket connection, or output creation for these attempts. Snapshot import remains offline and requires an expiring approval and matching content hashes, but a local file can still be parsed; the audit did not inspect a real catalog or certify its contents. Overall personal-data compliance is therefore **UNKNOWN**, not PASS.

The report, schedule, template, page count and assembled appendix statuses below remain unchanged until those artifacts and student inputs are available. No dates, meetings, contributions, or experiments were added in this follow-up.

The current real-query guard is independently covered by offline tests. The optional local Ollama synthetic smoke was attempted after this code change but failed with the installed runtime error `CUDA error: device kernel image is invalid`; no municipal retrieval was attempted. The documented local municipal catalog was not read or verified during this privacy audit, so the real-source smoke could not be rerun. These limitations are not represented as successful current real-model tests.

The remaining privacy uncertainty cannot be fixed by silently relabeling HTML or asserting that filtering means no collection. Any future source format must establish non-personal content before acquisition and before parsing. Missing report artifacts/schedule must be supplied or completed and reviewed; this audit does not invent a submission or human sign-off.

Historical, superseded analysis is preserved in the local ignored audit backup and excluded from publication because it refers to unrelated personal-file metadata. Only the current user-supplied assignment above applies.
