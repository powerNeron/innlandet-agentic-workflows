# AI provider configuration

The local web process uses the existing verified workflow and accepts provider/model choices only from server-side configuration. It binds to `127.0.0.1`. Ollama is the real-source default; the website lists only exact model tags both allowlisted in the environment and present in the local Ollama `/api/tags` response. Availability checks use loopback, a short timeout, a response-size limit, and no redirects or proxies. The application never downloads a model. Synthetic mock mode requires the explicit `--demo --provider mock` flags.

Configure the default local model and optional additional exact Ollama tags in the server environment:

```powershell
$env:HAMAR_OLLAMA_MODEL = "llama3.2:3b"
$env:HAMAR_OLLAMA_ALLOWED_MODELS = "qwen2.5:3b"
python -X utf8 -m hamar_agent.web --real-sources --port 8000
```

Only models installed locally and present in that allowlist appear as enabled choices. A missing or unavailable model disables its choice and does not trigger a fallback.

## Optional OpenAI provider

OpenAI is disabled by default. The optional adapter uses the official Python SDK Responses API, sends only the reviewed source paragraphs provided by the existing workflow, sets `store=False`, does not send the user's question or conversation history, disables SDK retries, bounds the timeout, input characters and output tokens, and returns sanitized errors. It uses the same claim contract and mandatory strict paragraph verifier as local inference. The server never returns the API key to the browser or result JSON.

Install the optional dependency only when the project has separately authorized external processing:

```powershell
python -m pip install -r requirements-openai.txt
```

Set these variables in the server environment, not in browser code or a tracked file:

```powershell
$env:HAMAR_OPENAI_ENABLED = "true"
$env:HAMAR_OPENAI_PRIVACY_AUTHORIZED = "true"
$env:HAMAR_OPENAI_MODEL = "<approved-model>"
$env:OPENAI_API_KEY = "<secret supplied through a secure environment>"
```

Both flags, model, key and SDK must be available before OpenAI appears enabled. The app does not choose OpenAI automatically and never switches to it after an Ollama failure. No live OpenAI request was made for this implementation. The SDK was not installed in the audited environment; tests use a fake SDK-compatible client. The token limit bounds one response, not account-level cost; configure provider-side spending limits before any authorized use. External-processing authorization still requires a genuine institutional/project privacy decision, and the current no-personal-data policy is not by itself evidence that cloud processing is permitted.

## Answer and verification limits

The current source adapter asks providers to return a complete reviewed paragraph with its exact paragraph ID. The verifier enforces paragraph identity and verbatim evidence, then permits at most one correction followed by re-verification. This gives traceability and conservative rejection; it does not prove that the official page is correct, current or semantically supports a paraphrase. No unsupported paraphrase is enabled. Natural explanatory generation remains limited until an independently validated semantic verification method is approved.

## Conversation and source updates

The AI page keeps only allowlisted municipal topic terms in volatile, per-page memory, for at most eight turns and two hours. It does not retain prior answers as evidence. Reset and provider changes clear the context; a reset racing an inference invalidates the stale response. Ordinary municipal search has separate state. Results and JSON downloads are token-owned and bounded in memory.

The existing source-change command remains proposal-only and offline. Raw HTML acquisition and snapshot import fail closed under the current privacy policy; the application does not automatically check live municipal pages or renew expiry dates. A person can inspect a proposal and record explicit approve/reject decisions in a separate local audit file with `python -m hamar_agent.source_admin`; details are in [the source administration guide](https://github.com/powerNeron/innlandet-agentic-workflows/blob/dad5024fda555113ab65233b1d2abdd9c34f09cf/docs/source-proposal-administration.md). A recorded approval is not activation. Legacy content activation remains blocked because sanitized proposals do not establish the required source-byte and robots provenance. A separate, explicitly gated unchanged-content expiry renewal is available after owner authorization and completed source/privacy/provenance review; see the [owner-controlled renewal procedure](../README.md#owner-controlled-renewal-review-check-activate). It does not enable fetching, HTML import or provider fallback.

## Tests

Provider selection, disabled/unavailable choices, mock SDK calls, error sanitization, session isolation, bounded follow-up context, reset races, and JSON ownership are covered by offline tests. The full offline suite blocks sockets and DNS. This does not substitute for a live OpenAI account test, human privacy approval, screen-reader testing, or semantic answer-quality evaluation.

## Bounded genuine-provider validation

The existing smoke command also supports the strict Aisha search/answer routes.
It uses only the hash-approved fictional water fixture, simulated source-admission
metadata and a fictional URL that is never fetched. It loads no municipal catalog.
The outer evidence explicitly labels those simulated inputs even though the strict
adapter's internal source flag exercises the real-source admission interface.
Successful local tests establish actual inference and traceability for this fixture;
they do not validate current municipal facts, source rights or human usefulness.

With an already installed, server-allowlisted model and explicit local permission:

```powershell
python -B -X utf8 -m eval.ollama_smoke --workflow --enable-local-llm --model llama3.2:3b --repeats 3 --output output/ollama-smoke-NEW
```

Each positive local request permits at most two calls sharing 1,400 reserved output
tokens and a 90-second deadline. Three negative requests check unsupported topics,
missing price evidence and synthetic contact-input rejection without generation.
`summary.json`, `raw.jsonl` and `T4_live_provider_smoke.csv` retain outcomes, latency,
budgets and numeric Ollama telemetry. Token counts reported by Ollama are separate
from reserved maxima; missing usage and monetary cost remain unknown. The method is
in-process public-route dispatch plus actual provider HTTP, not browser automation.
The original generic `--source-id` synthetic summarizer command remains unchanged.

Before any OpenAI setup, this check inspects only dependency and environment-entry
presence, never credential values or network connectivity:

```powershell
python -B -X utf8 -m eval.ollama_smoke --workflow --provider openai --check-only
```

Exit 3 means prerequisites are missing; exit 0 means entries/SDK are present, not
that their values, authorization, billing or connectivity are valid. Install the
optional SDK only after installation approval. The user creates/manages any account,
API key and spending limit directly with OpenAI, then configures the backend securely;
never paste a key into chat or commit it. A ChatGPT subscription does not establish
API credit. Real paid testing additionally requires approval for the chosen model
and spending exposure. Only after that approval and both existing server flags:

```powershell
python -B -X utf8 -m eval.ollama_smoke --workflow --provider openai --enable-paid-api --repeats 1 --output output/openai-smoke-NEW
```

This explicit command permits one positive request with at most one model call and
512 output tokens, then three no-model negative cases. Correction cannot spend a
second call. No automatic retries, paid fallback or automatic credential setup is
introduced. This is not an account-level monetary cap or an approved command to run
without the separate human decision. Genuine OpenAI testing remains unperformed.

## Application capabilities and publication gates

The application reads hash-approved synthetic fixtures or explicitly admitted local
source excerpts and provenance. The search index performs no query-time retrieval.
Model context contains reviewed paragraphs and verifier feedback; user conversation
and arbitrary file paths are not model tools. Neither adapter supplies shell, file,
browser or arbitrary-URL tools to the model. Ollama transport permits local HTTP on
port 11434 with proxies/redirects disabled. OpenAI uses the official SDK and trusted
server configuration; SDK environment/transport settings still require operator
review. These checks do not constitute an operating-system egress sandbox.

Exact-one whole-paragraph verification, at most one correction and the shared run
controls gate answer publication. Session identity/revision and deadline are checked
under the publication lock before memory changes. Local response envelopes, including
safe clarifications, can be exported only by the owning page token; export of a
clarification is not a model-generated answer. Reset clears context and invalidates
pending publication, without asserting cancellation of inference. Already completed,
token-owned exports remain until session expiry or bounded-memory eviction. Application results
are bounded volatile memory; explicit CLI/evaluation commands write their requested
local outputs. The application has no publishing, emailing or source-activation tool.

Human approval governs source selection/renewal, external processing and paid use,
and any public release/submission. Local display and owner-requested JSON download
are automatic after their checks. The operator remains responsible for lawful inputs
and any subsequent sharing. Host Codex/MXC project-only isolation is still unverified;
application controls must not be represented as host filesystem confinement.

## Chat med Aisha AI — separate general conversation

The mode selector keeps **Kommunal informasjon** and **Chat med Aisha AI** separate.
The original municipal search, exact-paragraph verification, citations and refusals
are retained. General chat answers are explicitly AI-generated and fallible; they
are never labeled municipally verified. Chat does not load or attach municipal
catalogs, documents, search results or the municipal conversation. Changing chat
provider/model/search setting requires chat reset; local history is not silently
transferred to a cloud provider.

The user must choose a configured provider/model. Ollama remains local. OpenAI
requires the existing `HAMAR_OPENAI_ENABLED` and
`HAMAR_OPENAI_PRIVACY_AUTHORIZED` flags, SDK, model and backend credential entry,
plus **`HAMAR_CHAT_PAID_AUTHORIZED=true`**. This additional gate defaults OFF.
Neither opening the mode, fetching options nor selecting a model performs inference.
The frontend does not automatically select OpenAI, retry a paid request or fall back
from Ollama. Only the user's explicit Send/Retry action requests a model call.

Use only non-personal content. Local guards reject recognizable contact/address,
identity and credential patterns before inference; output guards also reject common
contact/credential signals. These filters do **not** reliably detect every person's
name or all private information and are not privacy clearance. Never enter personal
data or secrets. Choosing OpenAI sends the accepted chat messages and bounded recent
chat history to external processing. Chat text remains in volatile token-owned page
sessions; the application writes no conversation log and uses no browser persistence
or OpenAI conversation/previous-response IDs. `store=False` is requested; that flag is
not a claim about every aspect of the provider's retention policy.

Controls per request: one generation attempt, at most 512 configured output tokens,
the existing per-run output/prompt-byte/deadline reservations, 1000 current-message
characters and 12000 UTF-8 bytes for serialized instructions/history/current input.
Old context is trimmed in complete user/assistant pairs; the current message and
instructions are never silently truncated. Eight completed turns require reset.
Six admitted attempts/minute/page and 20/minute/process are checked atomically; all
WebApplication instances share the process window. Failed/unknown attempts count;
reset/provider changes do not refund rate capacity. SDK retries remain0.

History is server-owned. Client-supplied history, roles, tools or budget overrides
are rejected. A revision guards duplicate retries and final publication rechecks
session identity, expiry, revision and busy ownership before finishing the run and
changing history. UI load/reset/retry operations have separate ownership checks and
reset requests are serialized. Reset clears chat history and blocks late publication;
it does not terminate a remote inference. Existing bounded worker/deferred-close
limits still apply. Explicit unsuccessful, incomplete or nonterminal provider output
is not published as a completed answer.

### Optional web search remains OFF

`HAMAR_CHAT_WEB_AUTHORIZED` defaults false. A forged checked box cannot enable a
tool: both this separate server approval and the user's per-request selection are
required, only for OpenAI. Ollama has no search tool. Actual search is not authorized
by these instructions or by SDK installation. Source/privacy/reuse conditions must
be resolved before activation; a boolean flag is an approval gate, not clearance.

The prepared Responses request uses `tools=[{"type":"web_search"}]` and
`max_tool_calls=1`. This bounds requested tool invocations, not internal search
fan-out, returned pages or monetary cost. Any future live-search approval must
consider the selected model, additional search pricing and provider account limits.
The UI says search occurred only when a returned `web_search_call` actually completed.
Source links come only from its returned URL annotations; unsafe schemes, credential
URLs and local/IP destinations are refused. These third-party citations are not
approved municipal evidence or independent factual verification. No links are fetched
by the application merely to display them. Tests use fictional search annotations.

### Project environment and first approved real OpenAI call

The detected project interpreter is `.venv\Scripts\python.exe`, Python 3.13.7.
The SDK was absent at preflight. Installation still requires the confirmation
requested by the user; no package or system setting has been changed. After approval:

```powershell
.\.venv\Scripts\python.exe -m pip --isolated --require-virtualenv --cache-dir .cache/pip --disable-pip-version-check install -r requirements-openai.txt
```

This installs only into the project's environment and uses its cache; it makes no
OpenAI request. Keep the temporary `OPENAI_API_KEY` only in the user's terminal.
Start the backend/checks from that same terminal: another Codex/PyCharm process may
not inherit it. Never paste the value into chat, source, a command log or a tracked
file. Choose a genuine API model available to the account and set only its
non-secret name in `HAMAR_OPENAI_MODEL`; no model availability is invented here.

Before approving any spending, run the no-call presence/configuration check:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.chat --check-only
```

It never loads the credential value or constructs a client. Exit 0 means chat
prerequisites/flags are present, not proven connectivity; exit 3 means incomplete
setup/approval. Missing paid approval is expected until the separate decision.
The two existing external-processing flags must also be configured by the owner.

Request explicit human approval for **one** Responses call using the chosen model,
one fixed synthetic message, at most 512 output tokens, bounded prompt bytes and
**no web search**. Output tokens are not an account spending cap; confirm the
model's price/credits and acceptable exposure first. Only after that approval:

```powershell
$env:HAMAR_CHAT_PAID_AUTHORIZED = "true"
try {
    .\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.chat --enable-paid-api --output output/chat-openai-smoke-NEW
} finally {
    $env:HAMAR_CHAT_PAID_AUTHORIZED = "false"
}
```

The smoke command permits one fixed positive request, no correction/retry, and
records sanitized synthetic evidence. It never enables search. A one-call approval
does not authorize ongoing interactive paid chat; that requires its own decision.
ChatGPT subscription status is not evidence of API credits. No real paid test has
been executed for this batch.

To inspect the existing UI without municipal data or paid calls:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.web --demo --provider mock --port 8000
```

Municipal mode is then explicitly synthetic; chat can use an installed allowlisted
local Ollama model. OpenAI stays disabled while paid authorization is false.

### Reproduction and remaining UI verification

`python -m unittest eval.test_chat -v` covers backend and Node-based UI behavior when
Node is installed. `node harness/browser_smoke.cjs --unit` executes the actual chat
JS with a deterministic synthetic DOM/API; it is **not browser rendering**. The full
offline harness blocks sockets/DNS; optional Node absence is reported as a skip.

The existing real-browser harness has synthetic SDK/transport injection and checks
chat plus municipal behavior at 1440, 768, 390 and 320 pixels, source rendering, loading,
reset/retry races and accessibility names:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m harness.browser_smoke --demo --output output/chat-browser-NEW
```

It uses a new project-local profile and makes no inference/search calls. In the
current agent environment Chrome failed during GPU-process startup before the page
opened, including the separately permitted run. Logs are retained; no sandbox was
disabled and no Windows security setting was changed. Run this check from the user's
normal project terminal to complete actual rendering/accessibility evidence. A
passing DOM test must not be reported as a passing browser test.

### SDK installed; first model prepared (2026-11-11)

This update supersedes the earlier pending-installation status. The owner approved
installation only into this project's `.venv`; the preflight found no SDK there.
Official `openai` version **2.54.0** is now installed with its dependencies under
the project interpreter, Python **3.13.7**. `pip check` reports no broken requirements.
The existing requirements file and application code were preserved.

The owner selected **`gpt-4.1-mini`**. `.env.example` records that non-secret model
name and keeps both chat paid authorization and web search false. The application
does not load this template. In the user's existing PyCharm terminal, where the
temporary key already resides, set only the non-secret values:

```powershell
$env:HAMAR_OPENAI_MODEL = "gpt-4.1-mini"
$env:HAMAR_CHAT_PAID_AUTHORIZED = "false"
$env:HAMAR_CHAT_WEB_AUTHORIZED = "false"
.\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.chat --check-only
```

This prints no credential value and makes no provider request. Exit 3 is expected
while spending authorization is false; it does not mean the SDK installation failed.
Existing running processes must be restarted from this terminal to inherit changed
non-secret settings. The agent did not inspect or import the user's terminal key.

The installed SDK passed six offline cases using real Responses serialization and
typed parsing over an in-memory HTTP transport with sockets/DNS blocked: success,
authentication failure, timeout, incomplete response, synthetic search annotations
and the retained strict claim-schema adapter.
These are **mocked SDK requests**, not genuine OpenAI or live-search experiments.
Both search-authorization defaults remain OFF. All 459 offline regressions and
34 focused chat methods pass with the installed SDK; the four Verifier findings
remain covered. Real account/model access and key validity remain untested.

The prepared single-call test uses `gpt-4.1-mini`, one fixed synthetic message,
at most **512 output tokens**, **2048 prompt-text bytes**, a **20-second deadline**,
zero SDK retries and no tools/search. The fixed serialized prompt currently measures
599 UTF-8 bytes. These are enforceable call/output/text/wait limits, not an exact
monetary billing cap; actual input tokens, prices, credits and currency must be
considered before approving spending. No monetary result or current price is assumed.

Only after separate approval for that paid test, use the existing `--enable-paid-api`
smoke command described above. Apply its narrower run limits only to the smoke and
restore the previous process settings afterward; do not replace the application's
normal Ollama budget with a 512-token run budget. This future block touches only
named non-secret variables, never the key:

```powershell
# NOT AUTHORIZED YET: execute only after explicit paid-test approval.
$aishaTestSettings = @{
    HAMAR_OPENAI_MODEL = "gpt-4.1-mini"
    HAMAR_OPENAI_ENABLED = "true"
    HAMAR_OPENAI_PRIVACY_AUTHORIZED = "true"
    HAMAR_CHAT_PAID_AUTHORIZED = "true"
    HAMAR_CHAT_WEB_AUTHORIZED = "false"
    HAMAR_OPENAI_MAX_OUTPUT_TOKENS = "512"
    HAMAR_OPENAI_TIMEOUT = "20"
    HAMAR_RUN_OUTPUT_TOKENS = "512"
    HAMAR_RUN_INPUT_BYTES = "2048"
    HAMAR_RUN_SECONDS = "20"
}
$aishaPreviousSettings = @{}
foreach ($name in $aishaTestSettings.Keys) {
    $aishaPreviousSettings[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    foreach ($name in $aishaTestSettings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $aishaTestSettings[$name], "Process")
    }
    .\.venv\Scripts\python.exe -B -X utf8 -m hamar_agent.chat --enable-paid-api --output output/chat-gpt41mini-smoke-NEW
} finally {
    foreach ($name in $aishaTestSettings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $aishaPreviousSettings[$name], "Process")
    }
}
```

This block is prepared for human review and has **not** been executed. A one-call
approval does not authorize ongoing interactive paid chat. Evidence for installation,
SDK checks and regressions is under
`output/aisha-openai-sdk-e59ae52089f142b5a41508d4860ffa8d/`. Prior chat snapshots and
browser-startup limitations remain unchanged; no new browser-rendering claim is made.

### Manual advanced chat model (default OFF)

The public interface uses friendly names, while exact allowlisted IDs stay in
backend configuration. Keep `HAMAR_OPENAI_MODEL=gpt-4.1-mini`. General chat defaults
only to an installed, allowed local Ollama option. OpenAI is manually selected;
neither loading, refreshing, resetting nor choosing a mode sends a generation request.
Changing provider/model with history requires a completed chat reset first.

The existing cloud gates remain necessary: `HAMAR_OPENAI_ENABLED`,
`HAMAR_OPENAI_PRIVACY_AUTHORIZED`, `HAMAR_CHAT_PAID_AUTHORIZED`, an SDK, a configured
model and server credential presence. Presence is checked without reading the key
value for discovery. These checks do not certify credentials, connectivity or account
model access. Leave paid authorization false until further interactive spending is
approved; the owner's one completed test does not authorize ongoing paid use.

An additional choice **OpenAI – utvidet modell** is prepared using two new settings:

```dotenv
HAMAR_CHAT_OPENAI_ADVANCED_MODEL=
HAMAR_CHAT_ADVANCED_OPENAI_AUTHORIZED=false
```

Do not enable these yet. After separate approval, the operator must choose an exact
account-supported model, review its price and compatibility, and set its own flag.
No speculative stronger-model ID is supplied. An empty, invalid or duplicate primary
ID fails closed. The advanced option also requires every existing cloud gate and
never becomes the automatic default. Revoked approval is checked before SDK creation.
Its output, call, context, timeout, history and rate limits remain the existing chat
limits; these are not an exact monetary billing cap. There is no paid fallback.

Optional web search remains separately authorized and OFF. Its control is hidden
when unavailable. Only annotations from an actual completed search can produce source
links, and they are distinct from municipal verification. Public error messages are
Norwegian and actionable; detailed result records remain in the existing owned API/CLI.
