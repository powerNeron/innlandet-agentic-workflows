# Offline Python scaffold for Hamar KommuneAgent

The repository previously contained project documentation only. This change adds a Python 3.12 standard-library package that reads an explicitly synthetic local fixture, creates deterministic mock claims, and prints a versioned JSON result.

Immutable source, paragraph, claim and result schemas establish the shared interface for later workflow stages. A Summarizer protocol provides a boundary for a future OpenAI adapter. All mock claims remain not_checked; excerpt matching is explicitly distinguished from semantic fact-checking and factual truth.

Includes a fictional Norwegian fixture, offline contract tests, PyCharm/run instructions, and KIUA-2003 implementation decisions. Existing tracked documentation is preserved.

Validation: all 9 unittest tests passed on Python 3.12.10; CLI smoke checks passed, including UTF-8 mode. No dependencies were installed, and no live retrieval or paid APIs were used.

Review requested from JeppeGs: schema clarity, synthetic labeling, evidence-status limitations, reproducibility, and PR 1 scope. Fetching, evidence matching, revision and result-file saving remain later work. Do not merge automatically.