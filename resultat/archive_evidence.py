"""Arkiver kontrollerte rapportlogger byteidentisk; aldri den aktive kildekatalogen.

Originalene i output/ endres ikke. Kjoer foer publisering eller bruk --check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
ARCHIVE = BASE / "logger/historisk"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    evidence = json.loads((ROOT / "docs/reports/evidence-2026-10-23.json").read_text(encoding="utf-8"))
    names = [name for name in evidence["artifacts"]
             if name.startswith("output/") and name != "output/municipal-catalog.json"]
    names += ["output/final-technical-evidence/ollama-quality-adversarial-20261022.py",
              "output/final-technical-evidence/production-adapter-injection-probe-20261022.py"]
    records = []
    for name in names:
        original, target = ROOT / name, ARCHIVE / name
        data = original.read_bytes() if original.exists() else target.read_bytes()
        text = data.decode("utf-8-sig")
        assert not re.search(r"[A-Z]:[\\/]+Users[\\/]", text, re.I), name
        assert not re.search(r"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY)", text), name
        assert not re.search(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text), name
        digest = hashlib.sha256(data).hexdigest()
        if name in evidence["artifacts"]:
            assert digest == evidence["artifacts"][name]["sha256"], name
        if not target.exists() and not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        assert target.read_bytes() == data, name
        records.append({"original_path": name, "archive_path": target.relative_to(ROOT).as_posix(),
                        "sha256": digest, "byte_identical": True})
    # Only non-identifying fields of the old command register are needed.
    register = ROOT / "output/final-technical-evidence/test-results.json"
    redacted_path = ARCHIVE / "test-results-sanitized.json"
    if not redacted_path.exists() and not args.check:
        original = json.loads(register.read_text(encoding="utf-8-sig"))
        selected = {k: original[k] for k in ("date", "tests", "stress_metrics", "real_model_latency", "evidence_policy") if k in original}
        selected["publication_note"] = "Derived allowlisted extract; account, author, runtime-path and GitHub metadata omitted. Original log unchanged."
        selected["original_sha256"] = hashlib.sha256(register.read_bytes()).hexdigest()
        with redacted_path.open("x", encoding="utf-8") as stream:
            json.dump(selected, stream, ensure_ascii=False, indent=2)
    assert redacted_path.exists()
    index_path = ARCHIVE / "archive-index.json"
    record = {"copies": records, "active_municipal_catalog_included": False,
              "sanitized_derived_register": redacted_path.relative_to(ROOT).as_posix(),
              "historical_measurements_not_modified": True}
    if index_path.exists():
        assert json.loads(index_path.read_text(encoding="utf-8")) == record
    else:
        with index_path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
    print("Archived/verified", len(records), "byte-identical files; active catalog excluded.")


if __name__ == "__main__":
    main()
