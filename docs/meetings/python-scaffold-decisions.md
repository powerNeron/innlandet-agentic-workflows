# KIUA-2003: Python scaffold implementation decisions

## Authorization and scope

User approved PR 1 on feat/python-scaffold: Python 3.12, standard library, shared schemas, synthetic fixture, unit tests and instructions. Existing project files are preserved. Remote push and pull-request creation require a separate approval. No automatic merge is authorized.

## Decisions

- Use a small importable package rather than an agent framework.
- Use immutable dataclasses and a Summarizer protocol for a future OpenAI adapter.
- Demonstrate JSON serialization on stdout without implementing later workflow stages prematurely.
- Label all example content synthetic and never claim that excerpt matching proves factual truth.
- Keep runs deterministic and tests offline with mock responses.
- Do not choose an LLM, fetch live municipal sources, install packages or add credentials.

## Proposed review

JeppeGs should review schemas, fixture labeling, the absence of factual-verification claims, reproducibility, and scope boundaries. Later work can split orchestration/source handling and summarizer/evidence checking between the two students.

## Sanitized prompt record

Request: implement only the approved offline scaffold, run tests, preserve existing files, prepare a local feature commit, and seek approval before remote writes. No personal data, secrets or municipal source content were supplied to the implementation.
## Validation results

- Python 3.12.10: python -m unittest discover -s eval -p 'test_*.py' -v passed all 9 tests.
- CLI smoke check passed with the synthetic fixture; provider mock and evidence_status not_checked.
- Repeated the CLI check with -X utf8 to handle Windows console character encoding.
- No external packages, live source retrieval or paid APIs were used.
- Original tracked files remain unchanged; implementation and report notes are additions only.
