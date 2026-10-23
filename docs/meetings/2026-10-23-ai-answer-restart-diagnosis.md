# AI answer failure after Windows restart

Sanitized task: investigate only the reported building-service AI answer failure, preserve privacy/source validation and approval expiry, and verify the actual localhost website. No commits, remote writes, dependencies or model downloads authorized or performed.

## Evidence and decision

- Existing port 8000 listener used a separate local virtual environment with Python 3.13.7. The account-specific executable path is omitted from this publication copy. Command: `-X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000`. This differs from the documented Python 3.12 baseline, but both the existing HTTP server and direct workflow with that interpreter succeeded. No unrelated interpreter migration was made. Process working directory was not inspected directly; the running server served the expected eight-document real catalog and current UI.
- Ollama was already listening on loopback port 11434. Tags and running-model APIs confirmed llama3.2:3b, loaded on GPU.
- Local Ollama operational log records cold loading beginning at 11:07:42 on 2026-10-23, runner startup completing after 64.92 seconds at 11:08:47, and the first `/api/chat` ending with HTTP 500 after 1m30s at 11:09:10, followed by task cancellation. The web process has a matching 90-second provider timeout. This supports a cold-start request exhausting the caller timeout. The log does not establish why that initial inference needed the remaining time; no permanent model/configuration defect was demonstrated.
- The existing backend intentionally masks provider/verifier errors with the reported generic workflow error. Access logging is disabled for privacy; no historical Hamar traceback was available. The original failure was not reproduced once the model was warm.
- Before any runtime or code modification, the exact building question returned HTTP 200, `evidence_checked`, provider `ollama:llama3.2:3b`, one exact-match claim, zero verification findings, and the official building-service citation. The same workflow succeeded directly using the running server's interpreter.
- Decision: retain the already working environment. No application code/configuration change, service restart, model reinstall, model download or timeout increase. A cold start may again need model warm-up before an answer; automatic cold-start recovery was not added or tested.

## Verification

- `python -X utf8 -m harness.offline_tests --output output/restart-ai-offline-20261023.txt`: 282 tests, zero failures/errors; harness blocks sockets and DNS.
- `python -X utf8 -m harness.real_source_smoke --enable-local-llm --output output/restart-ai-real-20261023`: 23/23 passing.
- Existing Chrome/Node browser driver `harness/browser_smoke.cjs` ran against the actual `http://127.0.0.1:8000` server, not a separate test server: exit 0, desktop/tablet/mobile, privacy rejection, source citations, answer/downloads and failure handling passed; no JavaScript exceptions, console errors or HTTP failures. Artifacts: `output/restart-ai-browser-20261023/`.
- Visually inspected `natural-building-answer.png`: exact requested question, source-checked answer about a garage/shed/other freestanding building, official building-service URL and downloadable JSON. Displayed workflow time: 1522 ms.
- Final port check: exactly one listener on 127.0.0.1:8000, PID 4768, unchanged.
- No municipal pages were retrieved. Source manifests, hashes, catalog and approval expiry 2026-10-28 were unchanged. Only this new diagnostic note and ignored test artifacts were created.
