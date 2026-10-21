# Agentic Workflows for Innlandet

Building and Verifying Coding Agent Harnesses for Local Needs
Full-Semester Project, Autumn 2026
KIUA-2003 Applikasjon av kunstig intelligens/maskinlaering II
University of Inland Norway, Hamar

Provenance: the official assignment text explicitly pasted and confirmed by the user in this project conversation. This project copy normalizes line wrapping and list formatting. Administrative contact details are omitted; the supplied requirement wording is preserved. Only the supplied sections below are authoritative for this integration gate. No unrelated PDF, two-agent brief, final-exam criteria, meeting count, or tag requirement is added.

## Abstract

Coding agents have dramatically reduced the cost of writing software. What now demands the most time and effort is everything around the code, including identifying a worthwhile problem, specifying it precisely in natural language, providing the right context for the agent, and verifying that the resulting software actually works. This project develops exactly those abilities. Students work in pairs to identify a recurring workflow challenge in the Innlandet region and build an agentic harness to address it. Identifying the right problem is itself part of the assignment. Rather than receiving a predefined task, each group studies how local organizations and communities manage information, identifies an opportunity where an agentic workflow could create genuine value, specifies the task for the agent, and then designs, implements, and evaluates the solution. The harness is subjected to systematic testing, stress testing, and validation before being demonstrated. In doing so, students apply every major concept from the course, including task specification, context engineering, orchestration, automation, evaluation, and safe operation.

## 1 Identifying the problem

Innlandet region runs on recurring information work. Announcements are published and missed, schedules are compiled by hand, documents are summarized for people who cannot read them in the original language, and volunteers coordinate the same activities every week. Somewhere in these routines is a workflow that an agentic system can improve. Identifying that opportunity is part of Compulsory 2, the first deliverable of the project.

Domains. You are expected to identify the problem your project will solve. As a guide, recurring workflow challenges commonly arise in areas such as:

- Municipal and county services: The public sector continuously publishes announcements, public hearings, council minutes, budget documents, and roadwork notices. Municipalities and the county administration provide reliable sources of recurring, public, text-intensive work.
- Culture and events: Information about concerts, exhibitions, library programs, and festivals is scattered across websites, social media, and PDF posters. Aggregating information, removing duplicates, and maintaining calendars are recurring tasks with no single owner.
- Sport and voluntary organisations: Volunteer organisations depend on repetitive coordination. Match schedules become newsletters, meeting notes become action lists, and season plans become weekly reminders. Much of this work remains manual.
- Information accessibility: Public information in Norwegian is not accessible to everyone. Translating it into plain language or other languages, while verifying correctness, is itself a recurring workflow.
- Local business and tourism: Seasonal guides, opening-hour directories, and review monitoring follow predictable cycles. The information already exists but is often compiled manually, if at all.
- Campus life: The university is itself a community with recurring information needs. Student announcements, course information, and practical guidance for international students are fragmented across systems that rarely communicate with one another.

Constraints. Regardless of the problem you identify, the following constraints apply:

- No personal data. Your workflow must not collect, store, or process information that identifies individuals, such as member lists, contact details, or user accounts. Choose problems whose inputs are public or synthetic.
- Respect the sources. Use official APIs, RSS feeds, or openly published documents whenever possible. Do not scrape websites that prohibit it, and do not republish source material beyond what the workflow requires.
- Fit the local context. The workflow should serve the Innlandet region. Verify that its outputs are appropriate for the local context, including the language of the source material, the institutions it refers to, and the people it is intended to serve.

## 2 Compulsory 2: Plan and walking skeleton

Compulsory 2 is graded pass or fail, and a pass is required to sit the exam. The submission has two main parts, a report and the walking skeleton.

The report. The report presents the problem and the plan to solve it. It must contain the following:

- A description of the problem: What recurring need it addresses, who has this need, and what the workflow produces.
- A definition of success: What output the workflow delivers and how its correctness can be checked.
- An architecture: How the workflow is structured as an agentic harness, covering the context the agent receives, how the work is divided into stages or subagents, and which parts run without a person at the keyboard.
- A schedule: Milestones from submission to the demonstration, working backwards from the demonstration date.
- A risk assessment: What is most likely to fail and what your group will do when it does.
- Repository: The report must contain a link to the repository.

The walking skeleton. The skeleton is a repository in which one path of the workflow runs end to end, e.g., real input goes in, the harness processes it, and checkable output comes out. The skeleton does not need to be complete, robust, or polished. It needs to exist and to run. The repository must contain a README with instructions that allow anyone to reproduce the run, and the context files the harness uses.

Technical minimum. Every project must satisfy four requirements. A problem that can be solved with a single prompt does not meet the minimum, however useful it may be:

1. The workflow takes input and produces output whose correctness can be checked.
2. It runs in more than one stage, so that the work is decomposed rather than handled in a single prompt.
3. It uses tools, including files, shell commands, or external data.
4. At least one part of it runs automatically, without a person driving each step.

Report format.

- Style: Reports must use the provided LaTeX template and follow the NeurIPS preprint format by including `\usepackage[preprint]{neurips_2025}`. Remove the NeurIPS checklist section.
- Length: The main text must be between three and four pages. References and appendices do not count toward this limit. Reports must be written in English.
- Appendices: An appendix is required and has no page limit. It must include:
  - Prompt logs: Representative excerpts from interactions with coding agents (maximum two pages).
  - Meeting reports: Evidence of iterative reasoning, design decisions, and revisions throughout the project. Weekly team meetings are strongly encouraged.
