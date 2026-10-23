# Problem, architecture and context

Problem: residents need to locate and assess municipal service information. The prototype combines search with bounded excerpts and official links; usefulness is a hypothesis, not an established social impact. Success in this evaluation means correct technical states, exact paragraph support and safe refusals, not general factual accuracy.

Context: system rules treating source content as untrusted data, selected approved paragraphs, the JSON contract and optional sanitized verification findings. Free-form user questions are not sent to the real adapter. Search and rule-based gates determine the paragraph selection. The model selects one whole paragraph rather than composing a freely generated semantically verified summary.

Stages: input checks → local catalog retrieval and validity → evidence gate → local model → independent verification → at most one correction → re-verification → source-linked answer. A single question triggers these stages automatically. Tools comprise files, a deterministic search index and local model HTTP, not an unrestricted shell agent. Humans approve source material before admission and decide whether actual source maintenance is lawful. No new source is activated automatically.

Runtime: Windows 11, Python 3.12.10, Ollama 0.40.8, llama3.2:3b, temperature 0, seed 0, num_predict 700, 90 s socket timeout in tests. No new dependency was installed. See ../logger/miljo.json. Diagram: figurer/03_workflow.mmd.
