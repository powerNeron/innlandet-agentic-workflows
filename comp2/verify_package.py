"""Verify preserved evidence independently of worktree and optional report checks.

Exit 0: evidence passes and no requested gate fails (warnings may remain).
Exit 1: evidence/security failure or incomplete verifier/output operation.
Exit 2: strict worktree/report gate fails, or invalid CLI arguments.
No result grants academic or publication approval. --output creates a new file only.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "2.0"
REPORT_CHECKS = (
    "neurips_preprint_declaration", "no_neurips_checklist",
    "ten_main_sections", "figures_and_table_inputs_exist",
)
SECURITY_PATTERNS = (
    r"(?i)[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]",
    r"(?i)(?<![\w.-])[\w.+-]+@[\w.-]+\.[a-z]{2,}",
    r"\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{15,}",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_evidence(root=ROOT):
    """Run every evidence group even when another group fails. Never invoke Git."""
    root = Path(root)
    base = root / "comp2"
    checks, errors, summaries = {}, [], []
    metadata = {"checked_original_resultat_files": 0,
                "saved_cli_results": summaries, "sensitive_pattern_candidates": []}

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def run(name, operation):
        try:
            checks[name] = bool(operation())
            if not checks[name]:
                errors.append({"check": name, "error": "Check failed"})
        except (OSError, ValueError, TypeError, KeyError, IndexError, csv.Error) as exc:
            checks[name] = False
            # Do not expose arbitrary source content, secrets or home paths in errors.
            errors.append({"check": name, "error": type(exc).__name__})

    def original_manifest():
        manifest = read(root / "resultat/logger/pakke-manifest.json")
        metadata["checked_original_resultat_files"] = len(manifest["files"])
        return all(sha(root / "resultat" / row["path"]) == row["sha256"]
                   for row in manifest["files"])

    run("original_resultat_manifest", original_manifest)

    def selected_copies():
        rows = read(base / "evidence/selection-manifest.json")
        return all(sha(root / row["source"]) == sha(base / row["copy"]) == row["sha256"]
                   for row in rows)

    run("selected_copies_byte_identical", selected_copies)

    def bilingual_results():
        data = read(base / "evidence/selected-results.json")
        tables = []
        for lang, key in [("english", "en"), ("norwegian", "no")]:
            with (base / "tables" / lang / "results.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))[1:]
            if len(rows) != len(data["rows"]):
                return False
            for row, source in zip(rows, data["rows"]):
                expected = [source["id"], source[key], source["observed"], source["denominator"],
                            source["unit_" + key], data["test_date"], source["source"], source["limit_" + key]]
                if row != expected or not (base / source["source"]).is_file():
                    return False
            tables.append([[row[i] for i in [0, 2, 3, 5, 6]] for row in rows])
        return tables[0] == tables[1]

    run("bilingual_results_values_dates_sources_identical", bilingual_results)

    def bilingual_performance():
        texts = [(base / "tables" / lang / "performance.md").read_text(encoding="utf-8")
                 for lang in ["english", "norwegian"]]
        number = r"(?<![A-Za-z])\d+(?:\.\d+)?"
        return re.findall(number, texts[0]) == re.findall(number, texts[1])

    run("bilingual_performance_numbers_identical", bilingual_performance)

    def archived_outputs():
        archive = read(base / "evidence/archived-evidence-audit.json")
        return (archive["real_ollama"]["verified_saved_outputs"] ==
                archive["real_ollama"]["verified_saved_claims"] == 17
                and archive["offline"]["total"] == 282
                and archive["real_ollama"]["tests"] == archive["real_ollama"]["passed"] == 23)

    run("archived_saved_positive_outputs_17", archived_outputs)

    def ollama_outcomes():
        smoke = read(base / "evidence/ollama-summary.json")
        return (len(smoke["rows"]) == smoke["tests"] == smoke["passing"] == 23
                and all(row["pass"] for row in smoke["rows"]))

    run("ollama_23_expected_outcomes", ollama_outcomes)

    def browser_layouts():
        browser = (base / "evidence/aisha-browser.txt").read_text(encoding="utf-8")
        layouts = [json.loads(line.split(" ", 2)[2]) for line in browser.splitlines()
                   if line.startswith("AISHA_HERO_LAYOUT ")]
        return len(layouts) == 3 and all(row["headings"] == 1 and not row["overflow"]
                                       and row["copy"][0] == "Aisha Agent" for row in layouts)

    run("current_aisha_three_viewports", browser_layouts)

    def browser_errors():
        browser = (base / "evidence/aisha-browser.txt").read_text(encoding="utf-8")
        return ('HTTP_FAILURES []' in browser and
                '\"javascript_exceptions\":[],\"console_errors\":[]' in browser)

    run("browser_no_console_or_http_errors", browser_errors)

    def recorded_cli_runs():
        rows = read(base / "evidence/new-command-register.json")
        return len(rows) == 2 and all(row["exit_code"] == 0 for row in rows)

    run("new_cli_runs_exit_zero", recorded_cli_runs)

    for filename in ["walking-skeleton-synthetic.json", "walking-skeleton-real.json"]:
        def exact_support(filename=filename):
            result = read(base / "evidence" / filename)
            paragraphs = {p["id"]: p["text"] for p in result["source"]["paragraphs"]}
            summaries.append({"file": filename, "claims": len(result["claims"]),
                              "provider": result["provider"], "source_id": result["source"]["id"]})
            return bool(result["claims"]) and all(
                c["text"] == c["evidence_quote"] == paragraphs[c["paragraph_id"]]
                for c in result["claims"])

        run(filename + "_exact_claim_support", exact_support)
        run(filename + "_no_verification_findings",
            lambda filename=filename: not read(base / "evidence" / filename)["verification"]["findings"])

    def approved_provenance():
        selected = {row["source_id"]: row for row in read(root / "docs/reviewed-service-selection.json")}
        for filename in ["walking-skeleton-synthetic.json", "walking-skeleton-real.json"]:
            result = read(base / "evidence" / filename)
            if not result["source"]["synthetic"]:
                approved = selected[result["source"]["id"]]
                if result["source"]["url"] != approved["url"] or not all(
                    hashlib.sha256(c["text"].encode("utf-8")).hexdigest() ==
                    approved["paragraph_sha256"][int(c["paragraph_id"][1:]) - 1]
                    for c in result["claims"]):
                    return False
        return True

    run("new_real_claim_matches_approved_hash_and_url", approved_provenance)

    def security_scan():
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".png", ".pdf", ".py"}:
                continue
            text = path.read_text(encoding="utf-8-sig")
            if any(re.search(pattern, text) for pattern in SECURITY_PATTERNS):
                metadata["sensitive_pattern_candidates"].append(path.relative_to(base).as_posix())
        return not metadata["sensitive_pattern_candidates"]

    run("no_detected_home_paths_emails_or_key_patterns_in_text", security_scan)
    passed = all(value is True for value in checks.values()) and not errors
    return {"status": "PASS" if passed else "FAIL", "checks": checks,
            "errors": errors, **metadata}


def normalize_scope_paths(root, paths):
    """Scope is classification only, never human approval."""
    root = Path(root).resolve()
    scopes = []
    for value in paths:
        value = value.replace("\\", "/")
        posix = PurePosixPath(value)
        if (not value or posix.is_absolute() or PureWindowsPath(value).drive
                or ".." in posix.parts):
            raise ValueError("Scope paths must be repository-relative, without parent traversal")
        resolved = (root / value).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Scope path resolves outside the repository")
        scopes.append({"path": posix.as_posix(),
                       "directory": value.endswith("/") or resolved.is_dir()})
    return scopes


def parse_git_status(payload):
    """Parse porcelain v1 -z: rename/copy destination precedes original path."""
    if not payload:
        return []
    if not payload.endswith(b"\0"):
        raise ValueError("Incomplete Git status")
    records = iter(payload[:-1].split(b"\0"))
    changes = []
    for record in records:
        if len(record) < 4 or record[2:3] != b" ":
            raise ValueError("Invalid Git status")
        status = record[:2].decode("ascii")
        if any(c not in " MADRCUT?!" for c in status):
            raise ValueError("Invalid Git status code")
        path = os.fsdecode(record[3:])
        if not path:
            raise ValueError("Missing Git path")
        original = None
        if "R" in status or "C" in status:
            original = os.fsdecode(next(records, b""))
            if not original:
                raise ValueError("Missing original Git path")
        untracked = status == "??"
        changes.append({"path": path, "original_path": original,
                        "index_status": status[0], "worktree_status": status[1],
                        "untracked": untracked,
                        "staged": not untracked and status[0] not in " !?",
                        "renamed": "R" in status, "copied": "C" in status,
                        "conflicted": status in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"},
                        "approved": False})
    return changes


def inspect_worktree(root=ROOT, scopes=()):
    root = Path(root).resolve()
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=" + root.as_posix(), "status",
             "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=root, capture_output=True, check=True, timeout=10)
        changes = parse_git_status(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"status": "ERROR", "changes": [], "scopes": list(scopes),
                "checks": {"no_staged_changes": None, "changes_within_scope": None},
                "warnings": ["Git inspection unavailable: " + type(exc).__name__],
                "strict_passed": False}

    def matches(path):
        return any(path == s["path"] or (s["directory"] and
                   (s["path"] == "." or path.startswith(s["path"].rstrip("/") + "/")))
                   for s in scopes)

    for change in changes:
        paths = [change["path"]] + ([change["original_path"]] if change["original_path"] else [])
        change["scope_status"] = ("UNREVIEWED" if not scopes else
                                  "IN_SCOPE" if all(matches(p) for p in paths) else "OUT_OF_SCOPE")
    no_staged = not any(c["staged"] for c in changes)
    scoped = all(c["scope_status"] == "IN_SCOPE" for c in changes)
    no_conflicts = not any(c["conflicted"] for c in changes)
    warnings = []
    if changes:
        warnings.append("Worktree changes require human review; in-scope does not mean approved.")
    if not no_staged:
        warnings.append("Staged changes detected.")
    if not scoped:
        warnings.append("Changes are outside the supplied scope or have no declared scope.")
    if not no_conflicts:
        warnings.append("Unmerged Git conflicts detected.")
    return {"status": "WARNING" if changes else "CLEAN", "changes": changes,
            "scopes": list(scopes), "checks": {"no_staged_changes": no_staged,
            "changes_within_scope": scoped, "no_conflicts": no_conflicts},
            "warnings": warnings, "strict_passed": no_staged and scoped and no_conflicts}


def verify_report(source=None):
    if source is None:
        return {"status": "NOT RUN", "checks": dict.fromkeys(REPORT_CHECKS, "NOT RUN"), "errors": []}
    checks = dict.fromkeys(REPORT_CHECKS, False)
    try:
        source = Path(source)
        tex = source.read_text(encoding="utf-8")
        checks["neurips_preprint_declaration"] = r"\usepackage[preprint]{neurips_2025}" in tex
        checks["no_neurips_checklist"] = not re.search(r"\\(?:section|input)\{[^}]*checklist", tex, re.I)
        checks["ten_main_sections"] = len(re.findall(r"\\section\{", tex.split(r"\appendix")[0])) == 10
        checks["figures_and_table_inputs_exist"] = all(
            (source.parent / p).is_file() for p in re.findall(
                r"\\(?:includegraphics(?:\[[^]]*\])?|input)\{([^}]+)\}", tex))
        errors = [] if all(checks.values()) else ["Report-specific check failed."]
    except (OSError, UnicodeError):
        errors = ["Report source is missing or unreadable."]
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Create a new JSON audit file exclusively")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--evidence-only", action="store_true", help="Compatibility option; evidence is the default")
    mode.add_argument("--check-report", action="store_true", help="Also run legacy report-source checks")
    parser.add_argument("--report-source", type=Path, help="Explicit report source; requires --check-report")
    parser.add_argument("--scope-path", action="append", default=[], help="Repository-relative file or directory; repeatable")
    parser.add_argument("--strict-worktree", action="store_true", help="Fail a separate gate on staging, conflicts or unscoped changes")
    args = parser.parse_args(argv)
    if args.report_source is not None and not args.check_report:
        parser.error("--report-source requires --check-report")
    try:
        scopes = normalize_scope_paths(ROOT, args.scope_path)
    except ValueError as exc:
        parser.error(str(exc))
    evidence = verify_evidence(ROOT)
    worktree = inspect_worktree(ROOT, scopes)
    report = verify_report((args.report_source or ROOT / "comp2/report/main.tex") if args.check_report else None)
    exit_code = (1 if evidence["status"] != "PASS" else
                 2 if (args.strict_worktree and not worktree["strict_passed"])
                 or report["status"] == "FAIL" else 0)
    record = {"schema_version": SCHEMA_VERSION,
              "audit_utc": datetime.now(timezone.utc).isoformat(),
              "evidence": evidence, "worktree": worktree, "report": report,
              "strict_worktree": args.strict_worktree, "exit_code": exit_code,
              "submission_ready": False, "commit_and_push_permitted": False}
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2)
        except OSError:
            record["output_error"] = "Unable to create the requested new audit output."
            record["exit_code"] = exit_code = 1
    print(json.dumps(record, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
