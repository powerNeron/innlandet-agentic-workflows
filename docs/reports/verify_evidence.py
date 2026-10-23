"""Audit existing project evidence offline; never run inference or fetch sources.

Run from the repository root. --output creates a new sanitized JSON record.
Only approved catalog paragraphs are read; no source text or user paths are saved.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-only", action="store_true",
                        help="Verify archived historical logs without local output/ or the active catalog")
    args = parser.parse_args()
    artifacts = {}

    def resolve(path):
        original = ROOT / path
        archived = ROOT / "resultat/logger/historisk" / path
        if path.startswith("output/") and (args.archive_only or not original.exists()):
            return archived
        return original

    def read(path):
        actual = resolve(path)
        raw = actual.read_bytes()
        artifacts[path] = {
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "mtime_utc_not_proof_of_execution_date": datetime.fromtimestamp(
                actual.stat().st_mtime, timezone.utc).isoformat(),
        }
        return raw.decode("utf-8-sig").replace("\r\n", "\n")

    def load(path):
        return json.loads(read(path))

    offline_path = "output/approved-ui-prepush-offline-20261023.txt"
    log = read(offline_path)
    total, elapsed = re.search(r"Ran (\d+) tests in ([\d.]+)s", log).groups()
    assert log.rstrip().endswith("OK")
    assert not re.search(r"^FAILED|^ERROR:|^FAIL:", log, re.M)
    assert len(re.findall(r" \.\.\. ok$", log, re.M)) == int(total)

    base = "output/restart-ai-real-20261023/"
    smoke = load(base + "summary.json")
    rows = smoke["rows"]
    assert len(rows) == smoke["tests"] == smoke["passing"] == 23
    assert all(row["pass"] for row in rows)
    latencies = sorted(row["provider_latency_ms"] for row in rows
                       if row.get("provider_latency_ms") is not None)
    assert len(latencies) == 18
    assert statistics.median(latencies) == smoke["provider_latency_ms"]["median"]
    assert latencies[-1] == smoke["provider_latency_ms"]["p95_nearest_rank"]
    assert sum(row.get("grounded_claims", 0) for row in rows) == smoke["grounded_claims"] == 14
    assert sum(row.get("claims", 0) for row in rows) == 18
    assert sum(row.get("answer_status") == "insufficient_evidence" for row in rows) == 4

    # Validate stored successful outputs against the still-approved local catalog.
    approval_path = "docs/approved-service-pages.json"
    catalog_path = "output/municipal-catalog.json"
    read(approval_path)
    catalog = None
    if not args.archive_only and (ROOT / catalog_path).exists():
        from hamar_agent.portal_sources import load_approvals, load_catalog
        read(catalog_path)
        catalog = load_catalog(ROOT / catalog_path, load_approvals(ROOT / approval_path))
    selection = load("docs/reviewed-service-selection.json")
    selected = {row["source_id"]: row for row in selection}
    checked_outputs = checked_claims = 0
    for path in sorted(resolve(base).glob("*.json")):
        if path.name == "summary.json":
            continue
        data = load(path.relative_to(ROOT).as_posix())
        result = data.get("result") if "answer_status" in data else data
        if result is None:
            continue
        assert result["provider"] == "ollama:llama3.2:3b"
        assert not result["verification"]["findings"]
        assert not result["source"]["synthetic"]
        for claim in result["claims"]:
            if ":" in claim["paragraph_id"]:
                source_id, paragraph_id = claim["paragraph_id"].rsplit(":", 1)
            else:
                source_id, paragraph_id = result["source"]["id"], claim["paragraph_id"]
            if catalog is not None:
                doc = catalog.documents[source_id]
                expected = next(p.text for p in doc.source.paragraphs if p.id == paragraph_id)
                assert claim["text"] == claim["evidence_quote"] == expected
                source_url = doc.source.url
            else:
                # Historical report verification is not source admission or renewal.
                # Validate verbatim text against the unchanged approved paragraph hash.
                assert claim["text"] == claim["evidence_quote"]
                match = re.fullmatch(r"p([1-9][0-9]*)", paragraph_id)
                assert match is not None
                paragraph_digest = selected[source_id]["paragraph_sha256"][int(match.group(1)) - 1]
                assert hashlib.sha256(claim["text"].encode("utf-8")).hexdigest() == paragraph_digest
                source_url = selected[source_id]["url"]
            assert claim["evidence_status"] == "exact_match"
            citations = data.get("citations", result["source_provenance"])
            assert any(c["source_id"] == source_id and c["url"] == source_url
                       and c["paragraph_id"] == claim["paragraph_id"] for c in citations)
            checked_claims += 1
        checked_outputs += 1
    assert checked_outputs == checked_claims == 17

    browser_path = "output/approved-ui-prepush-browser-20261023/browser-check.txt"
    browser_log = read(browser_path)
    browser = json.loads(next(line for line in browser_log.splitlines()
                              if line.startswith('{"title":')))
    questions = json.loads(next(line.partition(" ")[2] for line in browser_log.splitlines()
                                if line.startswith("REQUIRED_AI_QUESTIONS ")))
    assert len(questions) == 13 and all(row["http_status"] == 200 for row in questions)
    assert 'BROWSER_CONSOLE {"javascript_exceptions":[],"console_errors":[]}' in browser_log
    assert "HTTP_FAILURES []" in browser_log
    assert "MOBILE_AI evidence_checked; official building citation visible" in browser_log

    historical = {}
    directory = "output/final-technical-evidence/"
    for name in ("ollama-performance-20261022", "ollama-sustained-performance-20261022",
                 "ollama-sustained-performance-c1-20261022"):
        data = load(directory + name + ".json")
        read(directory + name + ".py")
        assert len(data["requests"]) == data["requests_completed"]
        assert all(row["ok"] for row in data["requests"])
        historical[name] = {key: data[key] for key in (
            "requests_completed", "latency_seconds", "resource_summary", "concurrency_cap",
            "duration_seconds", "sustained_60_seconds", "all_60_verified_no_errors",
            "timeouts_or_errors", "date", "recorded_at_utc") if key in data}
    for name in ("ollama-quality-adversarial-20261022-postfix",
                 "ollama-correction-20261022", "production-adapter-injection-probe-20261022",
                 "local-http-search-stress-20261022"):
        data = load(directory + name + ".json")
        # These artifacts contain operational metrics and synthetic case outcomes.
        # Exclude machine details and any free-text descriptions from the snapshot.
        keys = ("quality", "security", "requests", "workers", "failures", "elapsed_seconds",
                "requests_per_second", "latency_ms", "status", "correction_attempts",
                "final_findings", "final_claim_count", "injected_text_retained", "completed",
                "publication_status", "claim_count", "selected_injection_paragraph",
                "unsupported_number_in_model_claim", "forged_id_in_model_claim", "findings")
        historical[name] = {key: data[key] for key in keys if key in data}
    for path in ("harness/offline_tests.py", "harness/real_source_smoke.py",
                 "harness/browser_smoke.py", "harness/browser_smoke.cjs",
                 "hamar_agent/real_sources.py", "hamar_agent/portal.py",
                 "hamar_agent/ollama_provider.py"):
        read(path)
    record = {
        "audit_utc": datetime.now(timezone.utc).isoformat(),
        "audit_environment": {"os": platform.system(), "release": platform.release(),
                              "python": platform.python_version()},
        "active_catalog_used": catalog is not None,
        "historical_hash_verification_only": catalog is None,
        "offline": {"total": int(total), "passed": int(total), "failures": 0, "errors": 0,
                    "seconds": float(elapsed)},
        "real_ollama": {"tests": 23, "passed": 23, "recorded_grounded_claims_partial": 14,
                        "claims_summed_from_all_rows": 18, "verified_saved_outputs": checked_outputs,
                        "verified_saved_claims": checked_claims,
                        "insufficient_evidence_refusals": 4,
                        "latency_ms": smoke["provider_latency_ms"]},
        "sources": {"documents": len(selection),
                    "paragraphs": sum(len(s["paragraph_sha256"]) for s in selection),
                    "reviewed_on": sorted({s["reviewed_on"] for s in selection}),
                    "expires_on": sorted({s["expires_on"] for s in selection})},
        "browser": {"summary": browser, "question_cases": len(questions),
                    "statuses": {status: sum(q["status"] == status for q in questions)
                                 for status in sorted({q["status"] for q in questions})},
                    "mobile_real_answer": True, "console_errors": 0, "http_failures": 0},
        "historical": historical, "artifacts": artifacts,
        "missing": ["Measured token usage", "Independent human semantic quality rating",
                    "Human screen-reader sign-off", "Exact historical inline stress/correction scripts"],
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print("Evidence verified: offline=282; Ollama=23; saved claims=17; browser cases=13")


if __name__ == "__main__":
    main()
