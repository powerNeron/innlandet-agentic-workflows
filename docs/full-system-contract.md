# Additive workflow contract

Historical proposal below; the integrated contract and actual adapters are specified in the current integration section at the end. Statements about an unavailable Ollama adapter describe the earlier baseline only.

## Boundaries

The existing schemas.py, summarize.py, verify.py and revision.py are unchanged. This is powerNeron's orchestration contract, published for agreement with JeppeGs before a real adapter is connected. It does not assume an Ollama module or implement his provider logic.

Existing interfaces used unchanged:

- Summarizer.summarize(source: Source) -> tuple[Claim, ...]
- verify_claims(source, claims) -> VerificationReport
- VerificationFinding(code, message, claim_ids)
- VerificationReport(claims, findings)
- OneRevisionGate.request(source, prior_claims, findings) -> RevisionRequest

## Workflow output

WorkflowResult in workflow.py subclasses Result, retaining source, claims, provider, schema_version and warnings. It inherits Result.to_json() and can be passed to existing save_result. It adds workflow_version, verification and correction. The shared Result constructor and its direct JSON output are unchanged. Existing consumers that read the original fields continue to work; consumers that reject additional JSON keys must opt into the workflow extension. There is no claim of byte-identical CLI output: the requested integration changes statuses from not_checked to the actual evidence check result.

verification is the existing report serialized as claims and findings. A finding has code, message and claim_ids. exact_match describes only an excerpt occurring in a paragraph. Unsupported numbers and conflicting claims may still have exact_match evidence status; findings and review warnings must always be displayed alongside it. No output field declares facts true.

correction contains status (not_needed, not_configured, completed or failed), attempts (0 or 1), initial_claims, initial_findings and warnings. completed means a correction callback returned and was checked, not that all findings were resolved. Final findings are in verification; original findings remain in correction. The local gate is new for each run. No automatic repeated requests occur.

The orchestration-owned CorrectionCallback is Callable[[Source, RevisionRequest], tuple[Claim, ...]]. A future provider can be adapted with a small lambda or wrapper once JeppeGs agrees on his actual API. Do not add a presumed .correct or .revise method to his modules. No correction callback is installed by the default CLI/web application. Tests inject synthetic callbacks only.

Initial malformed/empty/duplicate/non-Claim responses raise a controlled error rather than fabricate claims to satisfy Result's nonempty contract. Such runs produce no saved result. Expected correction errors retain the original report and a sanitized failure warning. Error messages from real adapters must be mapped to the documented ValueError/TypeError/RuntimeError/OSError boundary without secrets.

## Provider wiring

WorkflowService accepts summarizer, provider label and optional corrector through trusted Python startup configuration. Both CLI and web use this service and run_workflow. Programmatic CLI main(argv, service=...) and create_server(service=...) accept the same injected service; default command-line startup always uses offline mocks. The provider label must accurately identify the injected implementation. There is no guessed dynamic import, Ollama SDK or assumed endpoint/model. The exact blocker for real integration is that no Ollama adapter or correction-provider implementation exists in the fetched main. JeppeGs must supply these plus agreed timeout and error behavior.

## Real-source seam

WorkflowService defaults to local approved fixtures. HTTP requires enable_http=True AND an explicit HttpApproval registry, with current review dates, exact URLs and existing transport limits. The web request schema accepts only source_id and cannot supply URLs, approvals or startup flags. No live-source enabling flag is exposed by the shipped CLI/server. Approved plain text becomes stable p1, p2... paragraphs; actual network transport remains the existing fetch_document implementation. Real sources are not labeled synthetic. A non-synthetic-capable provider is required. No real source is registered, and personal-data eligibility must be resolved before any live configuration.


## Current integrated contract (2026-10-21)

The actual interfaces from main a21d1cc are now connected without editing JeppeGs's files. runtime.create_service composes OllamaSummarizer(client) and OllamaCorrectionProvider(client). CorrectionProvider.revise(source, claims, findings) returns CorrectionResult(claims, findings, provider). The orchestration callback accepts this result as well as the original tuple[Claim, ...], preserving existing injected callbacks. No shared schema constructor changes.

Correction JSON additionally includes provider and provider_findings. Provider findings are retained alongside independent final verification; initial claims/findings remain in correction. At most one revision is attempted. Completed means an adapter returned, not that all issues were fixed. Errors preserve the original findings and review warnings. A missing or invalid evidence reference never becomes a verified fact.

CLI and web select mock (default) or ollama explicitly through the same service factory. Portal prepared synthetic sources use that service too. Explicit --fallback-to-mock permits labeled mock output only for synthetic inputs; without it an Ollama error fails the run. Correction errors preserve original real output instead of changing providers. JSON and the UI display the actual result provider.

The application requests the existing four-string claim JSON contract through Ollama's structured format option using the provider's transport injection seam. Network bounds, loopback checks, response validation and errors remain delegated to the original transport. This composition currently imports the internal _local_post helper: its availability is a compatibility dependency covered by integration tests; a future public transport export should be agreed with JeppeGs. No evidence IDs or text are silently normalized.

Both existing Ollama adapters deliberately accept synthetic sources only. Real reviewed-page search/indexing is separate, and actual real-source LLM answers remain blocked until JeppeGs explicitly supports that input contract. Both production live registries remain empty. No web route enables fetching or approves a URL.


## Current real-source update

The user subsequently approved transient official HTML acquisition with retention limited to individually reviewed non-personal service excerpts. Earlier missing-adapter/full-document-only statements above describe the historical baseline. Eight sources and 39 paragraphs now run through the real-source adapter, mandatory strict verification and bounded correction. See [current implementation and commands](real-source-workflow.md) and [actual assignment matrix](assignment-requirements-matrix.md). Normal web startup is now real mode; use --demo explicitly for offline synthetic testing. No existing provider files/shared schemas were changed. This user policy does not override stricter course-assignment requirements.
