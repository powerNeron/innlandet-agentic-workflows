# Evaluation and measurement methodology

Offline tests block sockets and DNS. Real-model tests use only the approved local catalog and loopback Ollama. Faults are injected into new process-local test instances using invented text; no approved source is modified. The experiment log explicitly identifies fixtures as synthetic even when a non-synthetic real-adapter code path is simulated. Browser tests are automated Chrome experiments, not a human usability study.

The unit is respectively a unittest, curated question, HTTP request, model call or safety property. These units must not be pooled into one success rate. Model cases repeat service questions rather than representing independent random observations. p95 uses nearest rank: sorted observation ceil(0.95*n). No population confidence interval is inferred from this dependent sample.

M2 measures wall time around portal.answer; M1 provider_latency_ms measures the workflow including verification. HTTP search latency includes client/server work but no model. Ollama duration fields use ns. Concurrent token records follow completion order and are not arbitrarily joined to request indices. Instrumentation and the GPU safety stop exist only in the evaluation script.

Experiments were not externally preregistered. Criteria were encoded before the respective run. The separately stored holdout file is already known within the project and is therefore not a new blind test. No run was repeated for translation. See ../run_experiments.py and ../logger/kommandoer.jsonl.
