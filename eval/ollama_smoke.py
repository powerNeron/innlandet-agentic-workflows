"""Opt-in real inference against an explicitly approved synthetic fixture."""
import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hamar_agent.ollama_provider import OllamaClient, OllamaConfig, OllamaError, OllamaSummarizer
from hamar_agent.sources import APPROVED_SOURCES, load_source


def openai_prerequisites():
    """Presence only: never load credentials, instantiate an SDK or probe a URL."""
    names = ("OPENAI_API_KEY", "HAMAR_OPENAI_MODEL", "HAMAR_OPENAI_ENABLED",
             "HAMAR_OPENAI_PRIVACY_AUTHORIZED")
    return {"sdk_installed": importlib.util.find_spec("openai") is not None,
            "environment_entries_present": {name: name in os.environ for name in names},
            "connectivity_verified": False, "generation_verified": False,
            "limitation": "Entry presence does not validate values, authorization, credits or connectivity."}


def _live_client(args, telemetry):
    if args.provider == "openai":
        from hamar_agent.openai_provider import OpenAIClient, OpenAIConfig
        config = OpenAIConfig.from_env()
        if args.model and args.model != config.model:
            raise ValueError("Use the server-configured OpenAI model")
        return OpenAIClient(config)
    from hamar_agent.ollama_provider import _local_post
    from hamar_agent.provider_registry import require_installed_ollama_model
    from hamar_agent.real_sources import reviewed_transport
    config = OllamaConfig(model=args.model or OllamaConfig.from_env().model, timeout_seconds=90)
    require_installed_ollama_model(config.model)

    def measured_post(url, headers, body, timeout, limit):
        request = json.loads(body)
        call = {"request_sha256": hashlib.sha256(body).hexdigest(),
                "output_token_cap": request["options"]["num_predict"],
                "timeout_seconds": timeout, "completed": False}
        telemetry.append(call)
        started = perf_counter()
        try:
            raw = _local_post(url, headers, body, timeout, limit)
            response = json.loads(raw)
            # Preserve numeric provider telemetry only, never unchecked model text.
            for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration",
                        "prompt_eval_duration", "eval_duration"):
                value = response.get(key)
                call[key] = value if type(value) is int and value >= 0 else None
            call["completed"] = True
            return raw
        finally:
            call["elapsed_ms"] = (perf_counter() - started) * 1000
    return OllamaClient(config, transport=reviewed_transport(measured_post))


def workflow_smoke(args):
    """Actual provider, fictional source and simulated source-admission metadata.

    This exercises the strict production adapter without reading a municipal
    catalog or granting new source approval. No live municipal URL is fetched.
    """
    from hamar_agent.portal import PortalService
    from hamar_agent.real_sources import MunicipalWorkflowService
    from hamar_agent.run_control import RunPolicy, active_workers, run_scope
    from hamar_agent.search import SearchIndex, index_document
    from hamar_agent.web import WebApplication

    root = Path(__file__).resolve().parents[1]
    destination = args.output.resolve()
    if not destination.is_relative_to((root / "output").resolve()) or destination == (root / "output").resolve():
        raise ValueError("Evidence must use a new directory below project/output")
    destination.mkdir(parents=True, exist_ok=False)
    fixture = load_source("synthetic-water-demo")
    # The false synthetic flag is solely simulated admission data for this test.
    # All outer evidence explicitly identifies the content and approval as fictional.
    source = replace(fixture, id="provider-smoke-fixture", synthetic=False,
                     url="https://www.hamar.kommune.no/fictional-provider-test-only/")
    index = SearchIndex((index_document(source, "teknisk", retrieved_at="2020-01-01T00:00:00Z",
                                       approval_expires="2100-01-01"),))
    telemetry, records = [], []
    summary = {"method": "genuine model inference; synthetic context; in-process public HTTP-route dispatch",
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "provider": args.provider, "content_synthetic": True, "source_approval_simulated": True,
               "fixture_id": fixture.id, "fixture_sha256": APPROVED_SOURCES[fixture.id].sha256,
               "source_url_is_fictional_and_never_fetched": True,
               "limitation": "Small smoke sample; not municipal factual validity, human quality or a provider comparison.",
               "actual_billed_cost": None, "actual_usage_source": "Ollama response telemetry only; null if unavailable"}
    client = None
    try:
        client = _live_client(args, telemetry)
        summary["model"] = client.config.model
        summary["generation_settings"] = ({"endpoint": client.config.base_url, "temperature": 0, "seed": 0,
                                           "num_predict": client.config.num_predict,
                                           "decoding": "whole-reviewed-paragraph JSON schema",
                                           "transport_timeout_seconds": client.config.timeout_seconds}
                                          if args.provider == "ollama" else
                                          {"max_output_tokens": client.config.max_output_tokens,
                                           "transport_timeout_seconds": client.config.timeout_seconds,
                                           "sdk_retries": 0, "store": False})
        policy = RunPolicy(output_tokens=1400 if args.provider == "ollama" else 512,
                           max_calls=2 if args.provider == "ollama" else 1)
        summary["policy"] = {"output_tokens": policy.output_tokens, "max_calls": policy.max_calls,
                             "seconds": policy.seconds, "input_bytes": policy.input_bytes}
        service = MunicipalWorkflowService(index, client, provider=args.provider, historical_baseline=True)
        service.run_policy = policy
        app = WebApplication(service, portal=PortalService(service, index=index))
        headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000",
                   "Content-Type": "application/json", "X-Hamar-Token": app.token}
        cases = [(f"grounded-{i+1}", "vann", 200, "evidence_checked") for i in range(args.repeats)]
        cases += [("unsupported", "teleportering", 200, "clarification_required"),
                  ("missing-price", "Hva koster vann?", 200, "insufficient_evidence"),
                  ("synthetic-contact-rejected", "person@example.invalid", 400, None)]
        for case_id, query, expected_http, expected_answer in cases:
            before, call_start, started = set(app.results), len(telemetry), perf_counter()
            with run_scope(policy) as state:
                response = app.dispatch("POST", "/api/answer", headers,
                                        json.dumps({"query": query}).encode("utf-8"))
            payload = json.loads(response.body)
            answer = payload.get("answer", {})
            published = set(app.results) - before
            audit = state.snapshot()
            positive = expected_answer == "evidence_checked"
            result = answer.get("result") or {}
            claims, citations = result.get("claims", []), answer.get("citations", [])
            grounded = (len(claims) == 1 and not result.get("verification", {}).get("findings", ["missing"])
                        and claims[0].get("text") == {source.id + ":" + p.id: p.text for p in fixture.paragraphs}.get(claims[0].get("paragraph_id"))
                        and claims[0].get("evidence_quote") == claims[0].get("text")
                        and claims[0].get("evidence_status") == "exact_match")
            valid_citations = (bool(citations) and all(c.get("url") == source.url and c.get("source_id") == source.id
                               for c in citations) and all(any(c.get("paragraph_id") == claim.get("paragraph_id")
                               for c in citations) for claim in claims))
            exported = all(app.dispatch("GET", "/api/results/" + key, headers, b"").status == 200 for key in published)
            budget_ok = (audit["output_tokens_reserved"] <= policy.output_tokens
                         and audit["prompt_bytes_reserved"] <= policy.input_bytes
                         and audit["provider_tasks_started"] <= policy.max_calls and not audit["stopped_code"])
            calls = telemetry[call_start:]
            usage_complete = bool(calls) and all(type(c.get("eval_count")) is int and type(c.get("prompt_eval_count")) is int for c in calls)
            measured_usage = ({"input_tokens": sum(c["prompt_eval_count"] for c in calls),
                               "output_tokens": sum(c["eval_count"] for c in calls)} if usage_complete else None)
            if measured_usage is not None:
                budget_ok = (budget_ok and measured_usage["output_tokens"] <= audit["output_tokens_reserved"]
                             and all(c["eval_count"] <= c["output_token_cap"] for c in calls))
            passed = (response.status == expected_http and answer.get("answer_status") == expected_answer
                      and budget_ok and ((grounded and valid_citations and len(published) == 1 and exported
                                          and audit["provider_tasks_started"] >= 1) if positive else
                                         (not result and audit["provider_tasks_started"] == 0
                                          and len(published) == (1 if expected_http == 200 else 0))))
            record = {"case_id": case_id, "query": query, "expected_http": expected_http,
                      "expected_answer": expected_answer, "http_status": response.status,
                      "response": payload, "passed": passed, "grounded": grounded if positive else None,
                      "citation_valid": valid_citations if positive else None,
                      "published_model_answers": int(bool(result)), "stored_response_envelopes": len(published),
                      "latency_ms": (perf_counter() - started) * 1000, "audit": audit,
                      "budget_compliant": budget_ok, "measured_token_usage": measured_usage,
                      "provider_calls": calls}
            records.append(record)
            with (destination / "raw.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        durations = sorted(r["latency_ms"] for r in records if r["expected_answer"] == "evidence_checked")
        summary.update({"executed": len(records), "passed": sum(r["passed"] for r in records),
                        "positive_executed": len(durations),
                        "positive_passed": sum(r["passed"] for r in records if r["expected_answer"] == "evidence_checked"),
                        "generation_tasks_started": sum(r["audit"]["provider_tasks_started"] for r in records),
                        "actual_transport_calls": len(telemetry) if args.provider == "ollama" else None,
                        "latency_ms_positive": {"n": len(durations), "mean": statistics.mean(durations),
                            "median": statistics.median(durations), "p95_nearest_rank": durations[math.ceil(.95*len(durations))-1],
                            "maximum": max(durations)},
                        "formulas": {"pass_rate": "passed / executed * 100",
                                     "p95": "sorted positive latency[ceil(0.95*n)-1]; includes cold/warm requests"}})
    except Exception as error:
        # Exception strings may contain SDK bodies or credentials; retain safe type/code only.
        summary["failure"] = {"type": type(error).__name__, "code": getattr(error, "code", "smoke_setup_or_execution_failed")}
    finally:
        if client is not None and callable(getattr(client, "close", None)):
            try:
                client.close()
            except Exception as error:
                summary["cleanup_failure"] = {"type": type(error).__name__, "code": "provider_cleanup_failed"}
        summary["active_workers_at_return"] = active_workers()
        summary["success"] = (not summary.get("failure") and not summary.get("cleanup_failure") and bool(records)
                              and all(r["passed"] for r in records) and active_workers() == 0)
        summary["recorded_provider_telemetry"] = telemetry
        with (destination / "summary.json").open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
        with (destination / "T4_live_provider_smoke.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("dataset", "provider", "model", "case_id", "method", "n",
                                                       "passed", "latency_ms", "generation_tasks_started", "evidence"))
            writer.writeheader()
            for record in records:
                writer.writerow({"dataset": fixture.id, "provider": args.provider, "model": summary.get("model"),
                                 "case_id": record["case_id"], "method": summary["method"], "n": 1,
                                 "passed": record["passed"], "latency_ms": record["latency_ms"],
                                 "generation_tasks_started": record["audit"]["provider_tasks_started"], "evidence": "raw.jsonl"})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", choices=sorted(APPROVED_SOURCES))
    parser.add_argument("--model", default=None, help="Ollama model; defaults to HAMAR_OLLAMA_MODEL or llama3.2:3b")
    parser.add_argument("--workflow", action="store_true", help="Exercise strict Aisha routes using a fictional water fixture")
    parser.add_argument("--provider", choices=("ollama", "openai"), default="ollama")
    parser.add_argument("--enable-local-llm", action="store_true", help="Explicitly authorize local generation for this command")
    parser.add_argument("--enable-paid-api", action="store_true", help="Operator confirmation of separately approved paid test")
    parser.add_argument("--check-only", action="store_true", help="OpenAI presence check without credentials or network access")
    parser.add_argument("--repeats", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--output", type=Path, help="New exclusive evidence directory below project/output")
    args = parser.parse_args(argv)
    if args.check_only:
        if not args.workflow or args.provider != "openai":
            parser.error("--check-only requires --workflow --provider openai")
        status = openai_prerequisites()
        print(json.dumps(status, indent=2))
        return 0 if status["sdk_installed"] and all(status["environment_entries_present"].values()) else 3
    if args.workflow:
        if not args.output or args.source_id:
            parser.error("--workflow requires --output and uses only its fixed fictional fixture")
        if args.provider == "ollama" and not args.enable_local_llm:
            parser.error("Local workflow inference requires --enable-local-llm")
        if args.provider == "openai" and (not args.enable_paid_api or args.repeats != 1):
            parser.error("Paid workflow requires separately approved --enable-paid-api --repeats 1")
        try:
            return workflow_smoke(args)
        except (ValueError, OSError):
            parser.exit(2, "Evidence path is invalid, unavailable or already exists.\n")
    if not args.source_id or args.provider != "ollama" or args.output or args.enable_paid_api:
        parser.error("Legacy synthetic smoke requires --source-id and local Ollama only")
    config = OllamaConfig.from_env()
    if args.model:
        config = OllamaConfig(model=args.model)
    source = load_source(args.source_id)
    started = perf_counter()
    try:
        report = OllamaSummarizer(OllamaClient(config)).summarize_with_report(source)
    except OllamaError as exc:
        parser.exit(2, f"Local Ollama smoke test failed: {exc}\n")
    latency_seconds = perf_counter() - started
    paragraph_ids = {p.id for p in source.paragraphs}
    metrics = {
        "source_id": source.id,
        "model": config.model,
        "latency_seconds": round(latency_seconds, 3),
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
