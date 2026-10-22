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

The existing source-change command remains proposal-only and offline. Raw HTML acquisition and snapshot import fail closed under the current privacy policy; the application does not automatically check live municipal pages or renew expiry dates. A person can inspect a proposal and record explicit approve/reject decisions in a separate local audit file with `python -m hamar_agent.source_admin`; details are in [the source administration guide](source-proposal-administration.md). A recorded approval is not activation. Activation is currently blocked because sanitized proposals do not establish the reviewed source-byte and robots provenance required by the active approval manifest. The command does not change source manifests or expiry dates.

## Tests

Provider selection, disabled/unavailable choices, mock SDK calls, error sanitization, session isolation, bounded follow-up context, reset races, and JSON ownership are covered by offline tests. The full offline suite blocks sockets and DNS. This does not substitute for a live OpenAI account test, human privacy approval, screen-reader testing, or semantic answer-quality evaluation.
