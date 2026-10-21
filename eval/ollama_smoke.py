"""Opt-in real inference against an explicitly approved synthetic fixture."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hamar_agent.ollama_provider import OllamaClient, OllamaConfig, OllamaError, OllamaSummarizer
from hamar_agent.sources import APPROVED_SOURCES, load_source


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True, choices=sorted(APPROVED_SOURCES))
    parser.add_argument("--model", default=None, help="Ollama model; defaults to HAMAR_OLLAMA_MODEL or llama3.2:3b")
    args = parser.parse_args(argv)
    config = OllamaConfig.from_env()
    if args.model:
        config = OllamaConfig(model=args.model)
    source = load_source(args.source_id)
    try:
        report = OllamaSummarizer(OllamaClient(config)).summarize_with_report(source)
    except OllamaError as exc:
        parser.exit(2, f"Local Ollama smoke test failed: {exc}\n")
    paragraph_ids = {p.id for p in source.paragraphs}
    metrics = {
        "source_id": source.id,
        "model": config.model,
        "claim_count": len(report.claims),
        "citation_rate": round(sum(bool(c.paragraph_id and c.evidence_quote) for c in report.claims) / max(1, len(report.claims)), 3),
        "valid_paragraph_rate": round(sum(c.paragraph_id in paragraph_ids for c in report.claims) / max(1, len(report.claims)), 3),
        "exact_quote_rate": round(sum(c.evidence_status.value == "exact_match" for c in report.claims) / max(1, len(report.claims)), 3),
        "findings_by_code": {},
        "claims": [{"text": c.text, "paragraph_id": c.paragraph_id,
                    "evidence_quote": c.evidence_quote, "evidence_status": c.evidence_status.value}
                   for c in report.claims],
        "limitation": "Metrics measure citation traceability and heuristic flags, not semantic truth.",
    }
    for finding in report.findings:
        code = finding.code.value
        metrics["findings_by_code"][code] = metrics["findings_by_code"].get(code, 0) + 1
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
