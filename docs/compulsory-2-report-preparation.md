# Compulsory 2 report preparation (not a submission report)

This note uses only the official assignment at `docs/official-assignment-user-supplied.md` and evidence in this repository. It is not the required final report and must not be submitted as one. No personal folders or other projects were searched.

## Verified material that can support the report

- **Problem and output:** README.md and SPEC.md describe a Hamar municipal-service information search that returns source-linked, evidence-checked service excerpts. Current coverage is limited to eight reviewed sources; the answer path returns a whole approved paragraph rather than an unrestricted summary. See `docs/real-source-workflow.md`.
- **Success and checking:** the real path checks source approval/expiry, paragraph references, verbatim text and evidence findings, and fails closed after at most one correction. The offline and real-model test commands and their recorded historical outcomes are in `docs/real-source-workflow.md`. On 2026-10-21 this audit reran 229 offline tests successfully; the opt-in synthetic Ollama smoke was attempted but the local model runtime returned HTTP 500. The municipal catalog required by the real-source harness is absent from this worktree, so no new real-source inference result is claimed.
- **Architecture:** `docs/real-source-workflow.md`, `docs/full-system-contract.md`, `hamar_agent/municipal_import.py`, `hamar_agent/portal.py`, `hamar_agent/real_sources.py` and `hamar_agent/web.py` document source selection/import, indexing/search, local Ollama, verification/correction, and CLI/web output.
- **Risk evidence:** source expiry, narrow coverage, exact-excerpt limitations, Ollama failure behavior, privacy boundaries and open assignment conflict are documented in `docs/real-source-workflow.md` and `docs/assignment-requirements-matrix.md`.
- **Repository link:** https://github.com/powerNeron/innlandet-agentic-workflows

These items are source material only. Students must review and take responsibility for the final report's claims and wording.

## Required report format and appendix

The supplied assignment requires an English report using the provided LaTeX template, `\usepackage[preprint]{neurips_2025}`, removal of the NeurIPS checklist, a 3–4 page main text, and an appendix with no page limit. Representative coding-agent prompt excerpts are limited to two pages. Meeting reports must evidence iterative reasoning, design decisions and revisions.

No `.tex`, `.sty`, `.pdf`, or `.bib` report/template artifact exists in this project worktree. The exact provided template therefore cannot be verified or reproduced here. No compiled page count or formatting check is claimed.

`docs/prompt-log.md` contains sanitized summaries, not assembled representative prompt excerpts. The files in `docs/meetings/` are setup/decision records; the repository alone does not establish which were actual team meetings or who attended. Do not relabel them as meeting minutes without student confirmation. The assignment specifies no required meeting count.

## Schedule inputs still needed

The supplied assignment contains no submission date or demonstration date. Git timestamps and source-review expiry are not substitutes for those dates. The milestones below are evidenced project phases, not a dated or approved schedule:

| Milestone candidate evidenced in the repository | Date / offset from demonstration | Student-confirmed owner and completion |
| --- | --- | --- |
| Problem selection and walking skeleton | **Student input required** | **Student input required** |
| Source approval and reviewed-content workflow | **Student input required** | **Student input required** |
| Local Ollama, verification and bounded correction integration | **Student input required** | **Student input required** |
| Final offline/real integration checks and demonstration rehearsal | **Student input required** | **Student input required** |
| Compulsory 2 submission and demonstration | **Provide both dates** | **Student input required** |

Once the demonstration date and actual milestone history are confirmed, schedule milestones should be ordered backwards from that date. No dates, meeting events, individual contributions or completion claims have been filled in by this note.

## References and submission checks

The supplied text says references and appendices are excluded from the page limit, but it does not separately state a mandatory bibliography format. Cite any municipal or technical claims used in the report with the exact source information already recorded in the approved source manifest and project documentation; do not add sources that have not been checked for the report.

Before submission, students still need to provide/confirm the official LaTeX template, submission and demonstration dates, schedule/owners, actual meeting reports or confirmation of existing records, and representative sanitized prompt excerpts. They must compile the report with the required package option, remove the checklist, verify English language and 3–4 page main-text length, and inspect the appendix. The current privacy FAIL in the assignment matrix also needs a source-boundary resolution; this preparation note does not waive it.
