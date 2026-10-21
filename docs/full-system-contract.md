# Proposed additive workflow contract

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
