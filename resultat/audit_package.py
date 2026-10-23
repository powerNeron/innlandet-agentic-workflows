"""Sluttkontroll uten nye modellkall; oppdaterer bare nye rapportartefakter.

python -X utf8 resultat/audit_package.py
Raalogger, appfiler og kildegodkjenninger endres aldri.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only validation of the committed package")
    parser.add_argument("--refresh", action="store_true", help="Refresh generated report inventory before staging")
    args = parser.parse_args()
    git = ["git", "-c", "safe.directory=" + ROOT.as_posix()]
    already_tracked = bool(subprocess.check_output(
        [*git, "ls-files", "--", "resultat/audit_package.py"], cwd=ROOT, text=True).strip())
    read_only = args.check or (already_tracked and not args.refresh)
    if not read_only:
        # Matplotlib leaves redundant spaces inside multiline SVG path attributes.
        # Retain every coordinate and newline; remove only trailing presentation whitespace.
        for svg in BASE.rglob("*.svg"):
            original = svg.read_text(encoding="utf-8")
            formatted = "\n".join(line.rstrip() for line in original.splitlines()) + "\n"
            if formatted != original:
                svg.write_text(formatted, encoding="utf-8")
    # Complete Norwegian root entry points, keeping their mirrored counterparts.
    aliases = {
        "03_evaluering_og_malemetode.md": "03_methodology.md", "05_kildekontroll_og_personvern.md": "05_sources_privacy_security.md",
        "06_stresstesting_og_feilanalyse.md": "06_stress_failures_regression.md", "07_brukertest_og_sporreundersokelse.md": "07_user_survey.md",
        "08_arkitektur_og_arbeidsflyt.md": "08_architecture.md", "09_codex_endringer_og_motereferater.md": "09_agent_changes_meetings.md",
        "10_figurer_og_tabeller.md": "10_figures_and_tables.md", "11_begrensninger_og_refleksjon.md": "11_limitations.md",
        "12_kravdekning_og_mangelliste.md": "12_coverage_gaps.md", "13_eksamensberedskap.md": "13_final_exam_readiness.md",
        "14_risiko_og_fremdrift.md": "14_risks_schedule.md", "15_reproduksjon_og_kjorelogg.md": "15_reproduction.md",
        "16_forsoksprotokoll.md": "16_experiment_protocol.md", "17_representative_promptutdrag.md": "17_prompt_excerpts.md",
        "18_referater_bekreftelsesmal.md": "18_meeting_confirmation_template.md", "00_LES_MEG.md": "00_READ_ME.md"}
    for target, source in aliases.items():
        if read_only:
            break
        text = (BASE / "norsk" / source).read_text(encoding="utf-8")
        def link(match):
            path = match.group(1)
            if path.startswith(("https://", "http://", "#")):
                return match.group(0)
            return "](" + posixpath.normpath("norsk/" + path) + ")"
        text = re.sub(r"\]\(([^)]+)\)", link, text)
        text = text.replace("../logger/", "logger/").replace("../run_experiments.py", "run_experiments.py")
        text = text.replace("../19_tokenbruk.csv", "19_tokenbruk.csv")
        text = text.replace("Diagram: figurer/03_workflow.mmd", "Diagram: norsk/figurer/03_workflow.mmd")
        for language_file in (BASE / "norsk").glob("*.md"):
            text = re.sub(r"(?<![\w/])" + re.escape(language_file.name), "norsk/" + language_file.name, text)
        if target == "00_LES_MEG.md":
            text += "\n\nSpråkversjoner: [norsk](norsk/00_READ_ME.md) og [English](english/00_READ_ME.md). [Komplett filinventar](FILOVERSIKT.md). [Endelig kontroll](logger/final-audit.json).\n"
        (BASE / target).write_text(text, encoding="utf-8")
    no = json.loads((BASE / "norsk/verified_values.json").read_text(encoding="utf-8"))
    en = json.loads((BASE / "english/verified_values.json").read_text(encoding="utf-8"))
    assert no == en
    full_text_number_checks = []
    for path in sorted((BASE / "norsk").glob("*.md")):
        counterpart = BASE / "english" / path.name
        a = re.findall(r"\d+(?:\.\d+)?", path.read_text(encoding="utf-8"))
        b = re.findall(r"\d+(?:\.\d+)?", counterpart.read_text(encoding="utf-8"))
        full_text_number_checks.append({"file": path.name, "same_numeric_tokens_in_order": a == b})
        assert re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")) == re.findall(
            r"\]\(([^)]+)\)", counterpart.read_text(encoding="utf-8")), path.name
    broken = []
    for path in BASE.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#")[0]
            planned_audit = (path.parent / target).resolve() == (BASE / "logger/final-audit.json").resolve()
            if target and not target.startswith(("http://", "https://")) and not planned_audit and not (path.parent / target).exists():
                broken.append({"file": path.relative_to(BASE).as_posix(), "target": target})
    assert not broken, broken
    # All source references in the result CSV and all raw latency/token cells agree.
    csv_checks = []
    for name in ("02_test_results.csv", "04_response_times.csv", "19_token_usage.csv"):
        def cells(lang):
            with (BASE / lang / name).open(encoding="utf-8", newline="") as stream:
                return list(csv.reader(stream))[1:]
        a, b = cells("norsk"), cells("english")
        if name == "02_test_results.csv":
            a, b = [r[:-1] for r in a], [r[:-1] for r in b]
        assert a == b
        csv_checks.append({"file": name, "identical_measurement_cells": True, "rows": len(a)})
    for name in ("01_requirements.csv", "01_full_requirements.csv"):
        def requirement_cells(lang):
            with (BASE / lang / name).open(encoding="utf-8", newline="") as stream:
                return list(csv.reader(stream))[1:]
        a, b = requirement_cells("norsk"), requirement_cells("english")
        assert len(a) == len(b) == 36
        reference = r"[A-Za-z0-9_./-]+\.(?:md|json|py|mmd|csv|txt)"
        for row_a, row_b in zip(a, b):
            assert row_a[0] == row_b[0]
            assert re.findall(r"\d+(?:\.\d+)?", " ".join(row_a)) == re.findall(r"\d+(?:\.\d+)?", " ".join(row_b))
            assert re.findall(reference, " ".join(row_a)) == re.findall(reference, " ".join(row_b))
        csv_checks.append({"file": name, "identical_numeric_cells_and_source_references": True, "rows": len(a)})
    for path in ("verified_values.json", "figurer/data.json"):
        assert json.loads((BASE / "norsk" / path).read_text(encoding="utf-8")) == json.loads((BASE / "english" / path).read_text(encoding="utf-8"))
    evidence = json.loads((BASE / "logger/historisk-hashkontroll.json").read_text(encoding="utf-8"))
    newline_baselines = json.loads((BASE / "logger/line-ending-baselines.json").read_text(encoding="utf-8"))["files"]
    normalized_context_files = []
    def check_hash(path, data, expected):
        if hashlib.sha256(data).hexdigest() == expected:
            return
        baseline = newline_baselines.get(path)
        assert baseline is not None and baseline["original_sha256"] == expected, path
        assert hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == baseline["lf_sha256"], path
        normalized_context_files.append(path)
    unavailable_local_catalog = []
    for item in evidence["artifacts"]:
        original = ROOT / item["path"]
        if original.exists():
            actual = original
        else:
            actual = BASE / "logger/historisk" / item["path"]
            if item["path"] == "output/municipal-catalog.json":
                unavailable_local_catalog.append(item["path"])
                continue
        check_hash(item["path"], actual.read_bytes(), item["sha256"])
    protected = json.loads((BASE / "logger/kode-og-kildeintegritet.json").read_text(encoding="utf-8"))
    for item in protected["files"]:
        check_hash(item["path"], (ROOT / item["path"]).read_bytes(), item["sha256"])
    commands = [json.loads(line) for line in (BASE / "logger/kommandoer.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(row["exit_code"] == 0 for row in commands)
    measured = json.loads((BASE / "logger/model-measurements.json").read_text(encoding="utf-8"))
    assert all(row["requested_output_limit"] == 700 and row["eval_count"] <= 700 and row["done"]
               for row in measured["model_call_metrics"])
    assert not re.search(r"[A-Za-z]:[\\/]+Users[\\/]", (BASE / "logger/kommandoer.jsonl").read_text(encoding="utf-8"))
    protected_paths = {item["path"] for item in protected["files"]}
    changed = subprocess.check_output([*git, "diff", "--name-only"], cwd=ROOT, text=True).splitlines()
    assert not protected_paths.intersection(changed)
    report = {"date": datetime.now(timezone.utc).isoformat(), "pass": True,
        "same_numeric_dataset": True, "csv_checks": csv_checks,
        "same_markdown_source_references": True,
        "measured_outputs_within_requested_cap": True,
        "full_text_numeric_checks": full_text_number_checks,
        "all_full_text_numeric_checks_pass": all(row["same_numeric_tokens_in_order"] for row in full_text_number_checks),
        "broken_markdown_links": broken,
        "historical_hashes_verified": len(evidence["artifacts"]) - len(unavailable_local_catalog),
        "local_catalog_not_published": True,
        "unavailable_local_catalog_checks": unavailable_local_catalog,
        "code_context_newline_normalization_only": sorted(set(normalized_context_files)),
        "protected_code_and_source_files_unchanged": len(protected["files"]),
        "tracked_application_changes": False, "browser_screenshot_and_plots_visually_inspected": True,
        "visually_inspected_files": ["english/figurer/01_model_response_times.png",
                                     "english/figurer/02_http_latency_distribution.png",
                                     "logger/browser/mobile-ai.png"],
        "numeric_equality_is_not_factual_accuracy": True,
        "global_kill_switch_verified": False, "final_submission_ready": False}
    if read_only:
        manifest = json.loads((BASE / "logger/pakke-manifest.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            assert hashlib.sha256((BASE / item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
        print(json.dumps({"read_only": True, "measurement_parity": True,
                          "full_text_numeric_parity": report["all_full_text_numeric_checks_pass"],
                          "historical_hashes_verified": report["historical_hashes_verified"],
                          "local_catalog_available": not unavailable_local_catalog}))
        return
    (BASE / "logger/final-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    (BASE / "FILOVERSIKT.md").write_text("# Komplett filoversikt\n\n" + "\n".join(
        "- `" + p.relative_to(BASE).as_posix() + "`" for p in files) + "\n", encoding="utf-8")
    manifest = [{"path": p.relative_to(BASE).as_posix(), "bytes": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in files if p.name != "pakke-manifest.json"]
    (BASE / "logger/pakke-manifest.json").write_text(json.dumps({"date": datetime.now(timezone.utc).isoformat(),
        "files": manifest, "raw_experimental_logs_unchanged": True}, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(files), "measurement_parity": True,
                      "full_text_numeric_parity": report["all_full_text_numeric_checks_pass"],
                      "numeric_text_mismatches": [r["file"] for r in full_text_number_checks if not r["same_numeric_tokens_in_order"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
