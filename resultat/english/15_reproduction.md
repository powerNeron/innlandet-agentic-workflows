# Reproduction and execution record

Run from the repository root using the same commit and Python environment. Exact recorded commands, UTC times, outcomes and sanitized raw output are in ../logger/kommandoer.jsonl. Real tests require the existing approved local catalog and installed model. Approval must not be extended merely to make a test run. No raw HTML is retrieved.

```powershell
python -X utf8 resultat/run_experiments.py offline
python -X utf8 resultat/run_experiments.py faults
python -X utf8 resultat/run_experiments.py gates
python -X utf8 resultat/run_experiments.py stress
python -X utf8 resultat/run_experiments.py real
python -X utf8 resultat/run_experiments.py browser
python -X utf8 resultat/build_package.py
python -X utf8 resultat/publish_bilingual.py
```

These are the actual entry points, but output creation is exclusive. A new run requires a separate experimental checkout with an empty results directory; do not delete or overwrite evidence. Test tools create private loopback servers on available ports and leave port 8000 untouched. The Chrome profile is temporary and is not retained. Plots use the already available matplotlib installation. A Git clone alone does not provide the ignored catalog; lawful transfer and validity must be resolved.

Historical results and methodological caveats are reused from docs/reports/verified-results-2026-10-23.md, evidence-2026-10-23.json and verify_evidence.py. The 43 older files were hash-checked without repeating historical experiments.


Report generators explicitly validate the collected sample. For a new experimental series with a different completed-call count, review sample assumptions and labels in the experimental copy; do not force old totals into new logs. Full bilingual matrix: 01_full_requirements.md. Historical tables: 20_historical_evidence.md. Run the final audit with `python -X utf8 resultat/audit_package.py`.