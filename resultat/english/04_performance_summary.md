# Performance and token measurements

| Group | n | Median ms | p95 ms | Min ms | Max ms | Log |
|---|---|---|---|---|---|---|
| Sequential | 12 | 1511.1545 | 2103.674 | 1155.707 | 2103.674 | ../logger/model-measurements.json |
| Concurrency 2 | 2 | 2299.8905 | 3066.538 | 1533.243 | 3066.538 | ../logger/model-measurements.json |

Ollama reported 4120 prompt tokens and 1716 generated tokens across 14 completed model calls. Token measurements cover only the instrumented series, not the entire project. The 700 limit is a requested per-call output cap, not a global token or cost budget. Local API calls were measured; energy cost and invoiced monetary cost were not measured.

| Phase | n | Median ms | p95 ms | Requests/s | Expected rejections | Unexpected outcomes |
|---|---|---|---|---|---|---|
| Baseline | 64 | 102.975 | 145.027 | 55.015 | 0 | 0 |
| Perturbation | 256 | 112.574 | 151.673 | 59.338 | 16 | 0 |
| Recovery | 64 | 120.452 | 170.404 | 58.233 | 0 | 0 |
