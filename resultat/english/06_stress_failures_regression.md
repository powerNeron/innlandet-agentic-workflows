# Stress testing and causal failure analysis

| Phase | n | Median ms | p95 ms | Requests/s | Expected rejections | Unexpected outcomes |
|---|---|---|---|---|---|---|
| Baseline | 64 | 102.975 | 145.027 | 55.015 | 0 | 0 |
| Perturbation | 256 | 112.574 | 151.673 | 59.338 | 16 | 0 |
| Recovery | 64 | 120.452 | 170.404 | 58.233 | 0 | 0 |

| ID | Injected mechanism | Baseline HTTP | Fault HTTP | Calls under fault | Recovery HTTP | Expected control passed |
|---|---|---|---|---|---|---|
| F01 | Timeout | 200 | 422 | 1 | 200 | True |
| F02 | Connection refused | 200 | 422 | 1 | 200 | True |
| F03 | Truncated JSON | 200 | 422 | 1 | 200 | True |
| F04 | Missing response field | 200 | 422 | 1 | 200 | True |
| F05 | Oversized response | 200 | 422 | 1 | 200 | True |
| F06 | Wrong fee persists | 200 | 422 | 2 | 200 | True |
| F07 | Forged paragraph ID | 200 | 422 | 2 | 200 | True |
| F08 | Condition removed | 200 | 422 | 2 | 200 | True |
| F09 | Verifier unavailable | 200 | 422 | 1 | 200 | True |
| F10 | Expired test approval | 200 | 400 | 0 | 200 | True |
| F11 | Wrong fee corrected | — | 200 | 2 | — | True |

Hypothesis for F01–F10: an injected fault must prevent new published answers; removing the fault must restore normal processing. Baseline requests return HTTP200. The experiment measures provider calls and result storage before/after, then repeats a normal request after restoration. HTTP400 for an expired source results from source-selection rejection before model invocation.

Dependency class: F01/F02 make model transport unavailable in an isolated instance. The cause is the injected exception; the existing application error boundary returns HTTP422 without a new result. Restoring transport makes the same instance return HTTP200. This is fault recovery, not a new code repair.

Evidence class: F06 returns an incorrect fee both before and after correction. Two calls still lack support and return HTTP422. F11 changes only the second model response to the correct approved paragraph: existing correction and re-verification return HTTP200 after two calls. This is a controlled counterfactual demonstration of an existing repair mechanism, not a newly repaired application defect.

Global emergency stop: a barrier keeps transport running while the conversation is reset. After release, transport completes, but stale publication is rejected with HTTP409. Publication protection works; computation cancellation does not. Proposed separate repair: global cancellation state, prevention of new calls, cancellable transport and verifiable termination. No application repair was performed.

The F series contains six researcher-defined mechanism classes. Names of the four official classes are unavailable. We therefore cannot claim that at least two of them are covered. The historical cold-start failure is an operational observation, not deliberate fault injection. Older load experiments and security failures remain documented in docs/reports/verified-results-2026-10-23.md.
