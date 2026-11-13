"""Validate and summarize anonymous human reviews of local chat-quality runs."""
import argparse
import hashlib
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import re
import sys

from harness.chat_quality_eval import ADDITIONAL_CASES, CASES

CRITERIA = ("accuracy", "relevance", "context", "calibration", "clarity")
TAGS = frozenset({
    "unsupported_claim", "wrong_sense", "context_dropped", "ambiguity_unresolved",
    "uncertainty_missing", "language_issue", "overly_verbose", "safe_referral",
    "useful_clarification", "provider_error",
})
REVIEWER_CODE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
SCHEMA_VERSION = "1.0"


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON: {path}") from exc


def load_run(run_dir):
    """Load a completed quality run without copying answer text into review data."""
    folder = Path(run_dir)
    summary = _read_json(folder / "summary.json")
    if not isinstance(summary, dict):
        raise ValueError("run summary must be an object")
    for field in ("suite", "dataset_sha256", "runtime", "case_count", "executed"):
        if field not in summary:
            raise ValueError(f"run summary missing {field}")
    runtime = summary["runtime"]
    if not isinstance(runtime, dict) or not all(isinstance(runtime.get(k), str) and runtime[k]
                                                 for k in ("provider", "model", "version")):
        raise ValueError("run runtime must identify provider, model, and version")
    suite = summary["suite"]
    catalog = {"primary": CASES, "additional": ADDITIONAL_CASES}.get(suite)
    if catalog is None:
        raise ValueError("run suite is not one of the fixed synthetic chat suites")
    expected_digest = hashlib.sha256(json.dumps(catalog, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    digest = summary["dataset_sha256"]
    if digest != expected_digest or summary["case_count"] != len(catalog):
        raise ValueError("run dataset identity does not match the fixed synthetic suite")
    expected_cases = {case["id"]: case for case in catalog}
    for key in ("system_sha256", "context_system_sha256"):
        if not isinstance(summary.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", summary[key]):
            raise ValueError(f"{key} must be a lowercase SHA-256 digest")
    source_digests = summary.get("source_sha256")
    if not isinstance(source_digests, dict) or not source_digests or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in source_digests.values()):
        raise ValueError("source_sha256 must contain lowercase SHA-256 digests")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("dataset_sha256 must be a lowercase SHA-256 digest")
    if type(summary["case_count"]) is not int or type(summary["executed"]) is not int:
        raise ValueError("case_count and executed must be integers")
    if summary["case_count"] <= 0 or summary["executed"] != summary["case_count"]:
        raise ValueError("only complete evaluation runs can be reviewed")

    rows = []
    for path in sorted(folder.glob("*.json")):
        if path.name in {"summary.json", "runtime.json"}:
            continue
        raw = _read_json(path)
        case = raw.get("case") if isinstance(raw, dict) else None
        case_id = case.get("id") if isinstance(case, dict) else None
        if not isinstance(case_id, str) or case_id not in expected_cases or path.stem != case_id:
            raise ValueError(f"invalid or undeclared synthetic case record: {path.name}")
        if case != expected_cases[case_id]:
            raise ValueError(f"case {case_id} does not match its fixed synthetic definition")
        if not isinstance(raw.get("text"), str) or type(raw.get("http_status")) is not int:
            raise ValueError(f"case {case_id} is missing response text or HTTP status")
        rows.append({"case_id": case_id, "http_status": raw["http_status"]})
    case_ids = [row["case_id"] for row in rows]
    if len(case_ids) != summary["executed"] or len(case_ids) != len(set(case_ids)):
        raise ValueError("case files do not match the completed run count")
    return {
        "suite": suite,
        "dataset_sha256": digest,
        "system_sha256": summary["system_sha256"],
        "context_system_sha256": summary["context_system_sha256"],
        "source_sha256": source_digests,
        "provider": runtime["provider"],
        "model": runtime["model"],
        "model_digest": runtime.get("digest"),
        "runtime_version": runtime["version"],
        "temperature": runtime.get("temperature"),
        "seed": runtime.get("seed"),
        "num_predict": runtime.get("num_predict"),
        "case_ids": sorted(case_ids),
        "case_status": {row["case_id"]: row["http_status"] for row in rows},
    }


def make_template(run):
    """Create a blank review form; no generated answer text or personal data is copied."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {key: run[key] for key in ("suite", "dataset_sha256", "system_sha256", "context_system_sha256", "source_sha256", "provider", "model", "model_digest", "runtime_version", "temperature", "seed", "num_predict")},
        "reviewer_code": "",
        "reviewed_at": "",
        "reviews": [{"case_id": case_id, "scores": {criterion: None for criterion in CRITERIA}, "tags": []}
                    for case_id in run["case_ids"]],
    }


def _validate_scores(data, run):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("review schema_version must be '1.0'")
    if set(data) != {"schema_version", "run", "reviewer_code", "reviewed_at", "reviews"}:
        raise ValueError("review contains unknown fields")
    expected_run = make_template(run)["run"]
    if data.get("run") != expected_run:
        raise ValueError("review run identity does not match the selected evaluation run")
    reviewer = data.get("reviewer_code")
    if not isinstance(reviewer, str) or not REVIEWER_CODE.fullmatch(reviewer):
        raise ValueError("reviewer_code must be an anonymous 1-24 character code")
    try:
        reviewed = date.fromisoformat(data.get("reviewed_at", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("reviewed_at must be an ISO date (YYYY-MM-DD)") from exc
    if reviewed.isoformat() != data["reviewed_at"]:
        raise ValueError("reviewed_at must use canonical YYYY-MM-DD format")
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("reviews must be a list")
    expected_ids = set(run["case_ids"])
    seen = set()
    for item in reviews:
        if not isinstance(item, dict):
            raise ValueError("each review must be an object")
        if set(item) != {"case_id", "scores", "tags"}:
            raise ValueError("review item contains unknown fields")
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or case_id not in expected_ids or case_id in seen:
            raise ValueError("reviews must contain each run case exactly once")
        seen.add(case_id)
        scores = item.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(CRITERIA):
            raise ValueError("scores must contain exactly: " + ", ".join(CRITERIA))
        for criterion, value in scores.items():
            if type(value) is not int or value not in (0, 1, 2):
                raise ValueError(f"{case_id}: {criterion} score must be integer 0, 1, or 2")
        tags = item.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags) or len(tags) != len(set(tags)) or not all(tag in TAGS for tag in tags):
            raise ValueError(f"{case_id}: tags must be unique values from the documented tag set")
    if seen != expected_ids:
        raise ValueError("every case in the run must receive a review")
    return reviewer, reviewed.isoformat(), reviews


def summarize_reviews(run, submissions):
    """Keep reviewer scores separate and report disagreement instead of hiding it."""
    if not isinstance(submissions, list) or not submissions:
        raise ValueError("at least one completed review submission is required")
    by_reviewer = {}
    per_case = defaultdict(list)
    for submission in submissions:
        reviewer, reviewed_at, reviews = _validate_scores(submission, run)
        if reviewer in by_reviewer:
            raise ValueError("reviewer codes must be unique in one report")
        by_reviewer[reviewer] = {"reviewed_at": reviewed_at, "reviews": reviews}
        for item in reviews:
            per_case[item["case_id"]].append({"reviewer_code": reviewer, "scores": item["scores"], "tags": item["tags"]})

    reviewer_summaries = []
    for reviewer, record in sorted(by_reviewer.items()):
        items = record["reviews"]
        means = {criterion: round(sum(item["scores"][criterion] for item in items) / len(items), 2)
                 for criterion in CRITERIA}
        reviewer_summaries.append({"reviewer_code": reviewer, "reviewed_at": record["reviewed_at"],
                                   "cases": len(items), "mean_by_criterion": means,
                                   "mean_total": round(sum(sum(item["scores"].values()) for item in items) / len(items), 2),
                                   "zero_scores": {criterion: sum(item["scores"][criterion] == 0 for item in items)
                                                   for criterion in CRITERIA}})

    case_summaries = []
    for case_id in run["case_ids"]:
        records = per_case[case_id]
        means = {criterion: round(sum(row["scores"][criterion] for row in records) / len(records), 2)
                 for criterion in CRITERIA}
        ranges = {criterion: max(row["scores"][criterion] for row in records) -
                               min(row["scores"][criterion] for row in records)
                  for criterion in CRITERIA}
        case_summaries.append({"case_id": case_id, "reviewer_count": len(records),
                               "mean_by_criterion": means, "score_range_by_criterion": ranges,
                               "reviewers": records})
    return {
        "schema_version": SCHEMA_VERSION,
        "run": make_template(run)["run"],
        "reviewer_count": len(by_reviewer),
        "review_count": sum(len(value["reviews"]) for value in by_reviewer.values()),
        "reviewer_summaries": reviewer_summaries,
        "case_summaries": case_summaries,
        "interpretation": "Human judgments of this fixed run only. Reviewer means are reported separately; score ranges expose disagreement. This is not population accuracy or a truth guarantee.",
    }


def _inside_output(path, root):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to((Path(root) / "output").resolve()):
        raise ValueError("review inputs and outputs must stay under project/output")
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Completed local chat-quality run directory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", type=Path, help="Create a blank anonymous review JSON file")
    mode.add_argument("--scores", type=Path, help="Validate and summarize one or more review submissions")
    parser.add_argument("--report", type=Path, help="New JSON report path; only valid with --scores")
    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    try:
        run_path = _inside_output(args.run, root)
        run = load_run(run_path)
        if args.template:
            if args.report:
                parser.error("--report is only valid with --scores")
            template_path = _inside_output(args.template, root)
            with template_path.open("x", encoding="utf-8") as stream:
                json.dump(make_template(run), stream, ensure_ascii=False, indent=2)
            print(f"Review template created: {template_path}")
            return 0
        scores_path = _inside_output(args.scores, root)
        scores = _read_json(scores_path)
        submissions = scores if isinstance(scores, list) else [scores]
        report = summarize_reviews(run, submissions)
        if args.report:
            report_path = _inside_output(args.report, root)
            with report_path.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"review input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
