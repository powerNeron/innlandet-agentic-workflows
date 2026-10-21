# Full-system integration and local web interface

## Run locally (Python 3.12, standard library only)

Use this feature worktree until the branch is reviewed and merged:

```powershell
cd C:\Users\LINDA\PycharmProjects\innlandet-agentic-workflows-full-system-web
python -X utf8 -m hamar_agent.web --port 8000
```

Open http://127.0.0.1:8000 in a browser. Stop with Ctrl+C. The server binds only 127.0.0.1; it does not open a browser or bind a public interface. No packages, credentials, paid APIs or model downloads are required. Set PyCharm's interpreter to Python 3.12 and working directory to this repository; run module hamar_agent.web with --port 8000.

CLI, preserving the original fixture command and JSON stdout:

```powershell
python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
python -X utf8 -m hamar_agent --source synthetic-verification-demo
```

For file saving, select an existing output directory and a new filename:

```powershell
python -X utf8 -m hamar_agent --source synthetic-verification-demo --output output/demo.json
```

output/ must already exist. Exclusive saving never overwrites a file. An interrupted write may leave a partial new file; no deletion is attempted. Downloading from the browser does not write a server-side file: the browser asks the user where to save it.

## Actual execution

CLI/web -> WorkflowService -> approved fixture (or explicitly enabled approved HTTP source) -> existing summarizer interface -> existing verify_claims -> optional one correction callback -> re-verification -> WorkflowResult -> existing JSON serializer/storage or browser download.

The default provider is Jesper/JeppeGs's MockSummarizer, not a real LLM. It echoes synthetic paragraphs. The existing verifier really runs and finds invalid references, absent excerpts, numeric mismatches and narrow numeric conflicts. All original findings and correction outcomes are retained in the report; review warnings are never replaced by a claim of factual truth. The verifier's semantic limitations remain unchanged.

Malformed initial provider responses produce errors and no result. No correction is attempted without an injected callback. When one is configured, it is called at most once if there are findings; its returned claims are rechecked, and failed or unresolved correction remains visible.

See full-system-contract.md for the additive JSON extension and adapter seams. Shared schemas and JeppeGs's modules are unchanged. Existing Result callers still work. The old fixture-only, unverified CLI output is intentionally superseded by additive workflow JSON and checked evidence statuses.

## Web routes and controls

- GET /: simple Norwegian interface with demo label, approved source selection, run state and inline errors.
- GET /api/sources: approved IDs and provider/mode, no arbitrary file/URL input.
- POST /api/run: application/json with exactly source_id; returns run_id and result.
- GET /api/results/<run_id>: exact serialized result download, requiring the local session token.
- GET /app.js and /style.css: fixed local assets only; no general file serving.

The UI displays claims, excerpts, paragraph IDs/text, evidence statuses, structured findings, warnings, provider, correction status and full JSON. Dynamic source/model text uses textContent, not HTML insertion. No external scripts, fonts or services are used.

Host checking, local Origin checking on run requests, a random session token, no CORS, no-store responses and a restrictive content security policy limit browser cross-site access. The HTTP adapter rejects oversized/ambiguous request framing, uses an 8 KiB body cap and 10-second connection timeout. Responses remain in memory, capped at the most recent 16 runs; old IDs expire. The server suppresses access logs. This is a local single-user coursework tool, not an authenticated multi-user deployment.

## Verification and tests

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
```

New integration suites individually block socket creation/connections. The final full-suite check also blocks both for every test. HTTP wire tests invoke the actual BaseHTTPRequestHandler parser using an in-memory socket double, so external network/paid APIs cannot be reached. A separate real loopback-only smoke check exercised page/assets, source list, workflow execution and download with external DNS/connections forbidden. Node's syntax checker validated app.js; no npm packages are needed. No browser automation/visual rendering test is claimed.

## Remaining dependencies and limits

- JeppeGs supplies the actual Ollama summarizer adapter, correction provider, evaluation and any semantic verification improvements. None is assumed or advertised as installed.
- Agree on the orchestration callback adapter before connecting a real provider. A real model call needs provider-owned timeouts and error mapping; no indefinite retry is implemented here.
- No municipal URL is approved. HTTP_APPROVALS remains empty, external retrieval disabled by default, and the UI cannot enable it.
- A reviewable non-personal delivery boundary is required before receiving real documents; content hashes are not personal-data prevention.
- General truth, paraphrase support, date/unit interpretation, source freshness and municipal correctness are not established by excerpt matching.
- Rich retrieval metadata/version history and deployed authentication are outside this local integration. The synthetic demo is not a municipal advice service.


## Search portal extension

The homepage is now the Norwegian searchable portal. Existing source-run controls remain under the developer details section. All prior workflow routes still work. See search-portal.md and source-review-process.md for the new offline corpus, query/answer routes, HTML adapter, approval process, SSRF/robots controls and exact startup commands. The default remains mock/synthetic with no live approvals.


## Integrated runtime update

The earlier missing-adapter limitation is superseded by [the current integration report](meetings/ollama-integration.md). CLI and web now accept --provider ollama --model llama3.2:3b --ollama-timeout 90. Default remains mock; optional --fallback-to-mock is labeled and never implicit. The actual provider remains synthetic-only. All source approval boundaries and empty live registries remain in force.
