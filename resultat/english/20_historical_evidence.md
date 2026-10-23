# Historical evidence and failure cases

The values below are reused from the previously verified docs/reports/ package. Original historical logs were neither modified nor rerun. Their hashes are checked in logger/historisk-hashkontroll.json. Historical and new measurements must not be pooled as independent observations.

| ID | Date | n | Observation | Limitation | Primary file |
|---|---|---|---|---|---|
| H1 | 2026-10-22 | 12 | p50=2.391 s; p95=2.547 s; max=2.563 s | Mixed sequential/concurrent model calls; historical code | [JSON](../logger/historisk/output/final-technical-evidence/ollama-performance-20261022.json) |
| H2a | 2026-10-22 | 44 | duration=59.625 s; p95=2.719 s; errors=0; all_60=False | Concurrency 2; did not reach the 60-request target | [JSON](../logger/historisk/output/final-technical-evidence/ollama-sustained-performance-20261022.json) |
| H2b | 2026-10-22 | 50 | duration=75.453 s; p95=1.516 s; errors=0; all_60=False | Concurrency 1; did not reach the 60-request target | [JSON](../logger/historisk/output/final-technical-evidence/ollama-sustained-performance-c1-20261022.json) |
| H3 | 2026-10-22 | 800 | workers=8; failures=0; rate=64.27 requests/s; p95=137.554 ms | Search only; complete original inline command unavailable | [JSON](../logger/historisk/output/final-technical-evidence/local-http-search-stress-20261022.json) |
| H4a | 2026-10-22 | 8 | source_selection=8/8; answer_criteria=7/8 | Building case was safely refused but failed the expected positive-answer criterion | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H4b | 2026-10-22 | 3 | rejected=3/3 | Only the tested user attacks | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H4c | 2026-10-22 | 3 | security_pass=0/3 | Generic synthetic model path; instructional paragraph selected and verification findings recorded | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H5 | 2026-10-22 | 1 | attempts=1; final_findings=0; elapsed=1.376 s | Injected initial error; actual model correction; complete inline command unavailable | [JSON](../logger/historisk/output/final-technical-evidence/ollama-correction-20261022.json) |
| H6 | 2026-10-22 | 1 | findings=0; selected_injection=False | One production-adapter probe does not establish general immunity | [JSON](../logger/historisk/output/final-technical-evidence/production-adapter-injection-probe-20261022.json) |

The historical model-load experiments reached a GPU temperature of 80 °C, the stop threshold in those tools. Their targets were incomplete; they do not establish production capacity. Older p95 values use the scripts' floor-index method and must not be confused with nearest rank in the new measurements.

The cold start after a Windows restart was an observed operational failure, not a planned injection: the chat call failed after 90 s while model startup took approximately 65 s. Subsequent warm calls succeeded without code changes. The reason the remaining initial inference took that long is not established. The historical Hamar traceback and exact reproduction command are unavailable.

Complete methods and caveats: docs/reports/verified-results-2026-10-23.md; docs/reports/evidence-2026-10-23.json; docs/reports/verify_evidence.py.
