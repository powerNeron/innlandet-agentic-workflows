"""Gjenbruk tidligere kontrollerte data i begge sprak, uten nye forsok."""
import hashlib
import json
from pathlib import Path
from publish_bilingual import mdtable, write

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def main():
    old = json.loads((ROOT / "docs/reports/evidence-2026-10-23.json").read_text(encoding="utf-8"))
    data_path = BASE / "data/shared.json"
    shared = json.loads(data_path.read_text(encoding="utf-8"))
    shared["historical"] = old["historical"]
    data_path.write_text(json.dumps(shared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    h = shared["historical"]
    perf = h["ollama-performance-20261022"]
    stress2 = h["ollama-sustained-performance-20261022"]
    stress1 = h["ollama-sustained-performance-c1-20261022"]
    http = h["local-http-search-stress-20261022"]
    quality = h["ollama-quality-adversarial-20261022-postfix"]
    correction = h["ollama-correction-20261022"]
    probe = h["production-adapter-injection-probe-20261022"]
    for lang, li in (("norsk", 0), ("english", 1)):
        folder = BASE / lang
        values_path = folder / "verified_values.json"
        values = json.loads(values_path.read_text(encoding="utf-8"))
        values["historical"] = h
        values_path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        headers = (["ID", "Dato", "n", "Observasjon", "Begrensning", "Primærfil"],
                   ["ID", "Date", "n", "Observation", "Limitation", "Primary file"])[li]
        prefix = "../logger/historisk/output/final-technical-evidence/"
        def link(name):
            return "[JSON](" + prefix + name + ".json)"
        quality_cases = quality["quality"]["cases"]
        quality_passed = sum(r["source_selection_pass"] and r["supported_answer_pass"] and r["citation_and_exact_evidence_pass"] and r["no_verification_findings"] for r in quality_cases)
        attacks = quality["security"]["real_source_user_attacks"]
        injections = quality["security"]["synthetic_source_injection_runs"]
        rows = [
          ["H1", "2026-10-22", perf["requests_completed"],
           f"p50={perf['latency_seconds']['p50']} s; p95={perf['latency_seconds']['p95']} s; max={perf['latency_seconds']['max']} s",
           ("Blandet sekvensiell og samtidig modellkjøring; historisk kode", "Mixed sequential/concurrent model calls; historical code")[li], link("ollama-performance-20261022")],
          ["H2a", "2026-10-22", stress2["requests_completed"],
           f"duration={stress2['duration_seconds']} s; p95={stress2['latency_seconds']['p95']} s; errors={stress2['timeouts_or_errors']}; all_60={stress2['all_60_verified_no_errors']}",
           ("Samtidighet 2; nådde ikke målet om 60 forespørsler", "Concurrency 2; did not reach the 60-request target")[li], link("ollama-sustained-performance-20261022")],
          ["H2b", "2026-10-22", stress1["requests_completed"],
           f"duration={stress1['duration_seconds']} s; p95={stress1['latency_seconds']['p95']} s; errors={stress1['timeouts_or_errors']}; all_60={stress1['all_60_verified_no_errors']}",
           ("Samtidighet 1; nådde ikke målet om 60 forespørsler", "Concurrency 1; did not reach the 60-request target")[li], link("ollama-sustained-performance-c1-20261022")],
          ["H3", "2026-10-22", http["requests"],
           f"workers={http['workers']}; failures={http['failures']}; rate={http['requests_per_second']} requests/s; p95={http['latency_ms']['p95']} ms",
           ("Kun søk; full historisk inline-kommando mangler", "Search only; complete original inline command unavailable")[li], link("local-http-search-stress-20261022")],
          ["H4a", "2026-10-22", len(quality_cases),
           f"source_selection={sum(r['source_selection_pass'] for r in quality_cases)}/{len(quality_cases)}; answer_criteria={quality_passed}/{len(quality_cases)}",
           ("Byggesak ble trygt avvist, men oppfylte ikke forventet positivt svarkriterium", "Building case was safely refused but failed the expected positive-answer criterion")[li], link("ollama-quality-adversarial-20261022-postfix")],
          ["H4b", "2026-10-22", len(attacks), f"rejected={sum(r['pass'] for r in attacks)}/{len(attacks)}",
           ("Kun testede brukerangrep", "Only the tested user attacks")[li], link("ollama-quality-adversarial-20261022-postfix")],
          ["H4c", "2026-10-22", len(injections), f"security_pass={sum(r['pass'] for r in injections)}/{len(injections)}",
           ("Generisk syntetisk modellbane; instruksjonsavsnitt valgt og verifikasjonsfunn registrert", "Generic synthetic model path; instructional paragraph selected and verification findings recorded")[li], link("ollama-quality-adversarial-20261022-postfix")],
          ["H5", "2026-10-22", 1, f"attempts={correction['correction_attempts']}; final_findings={correction['final_findings']}; elapsed={correction['elapsed_seconds']} s",
           ("Injisert første feil; reell modellkorreksjon; full inline-kommando mangler", "Injected initial error; actual model correction; complete inline command unavailable")[li], link("ollama-correction-20261022")],
          ["H6", "2026-10-22", 1, f"findings={probe['findings']}; selected_injection={probe['selected_injection_paragraph']}",
           ("Én produksjonsadapterprobe er ikke generell immunitet", "One production-adapter probe does not establish general immunity")[li], link("production-adapter-injection-probe-20261022")],
        ]
        intro = (
            "Tallene nedenfor er hentet fra den tidligere verifiserte pakken i docs/reports/. Originale historiske logger er ikke endret eller kjørt om igjen. De er hashkontrollert i logger/historisk-hashkontroll.json. Historiske og nye målinger skal ikke slås sammen som uavhengige observasjoner.\n\n",
            "The values below are reused from the previously verified docs/reports/ package. Original historical logs were neither modified nor rerun. Their hashes are checked in logger/historisk-hashkontroll.json. Historical and new measurements must not be pooled as independent observations.\n\n")[li]
        ending = (
            "De historiske modellbelastningsforsøkene nådde GPU-temperatur 80 °C, som var stoppgrense i de daværende verktøyene. Dette var ufullførte mål, ikke produksjonskapasitetsbevis. Gamle p95-verdier bruker skriptenes gulvindeks og må ikke forveksles med nearest-rank brukt i nye målinger.\n\nKaldstart etter Windows-omstart var en observert driftsfeil, ikke planlagt injeksjon: chat-kallet feilet etter 90 s mens modelloppstart tok omtrent 65 s. Senere varme kall virket uten kodeendring. Hvorfor resten av første inferens tok så lang tid er ikke fastslått. Historisk Hamar-traceback og eksakt reproduksjonskommando mangler.\n\nFull metode og forbehold: docs/reports/verified-results-2026-10-23.md; docs/reports/evidence-2026-10-23.json; docs/reports/verify_evidence.py.",
            "The historical model-load experiments reached a GPU temperature of 80 °C, the stop threshold in those tools. Their targets were incomplete; they do not establish production capacity. Older p95 values use the scripts' floor-index method and must not be confused with nearest rank in the new measurements.\n\nThe cold start after a Windows restart was an observed operational failure, not a planned injection: the chat call failed after 90 s while model startup took approximately 65 s. Subsequent warm calls succeeded without code changes. The reason the remaining initial inference took that long is not established. The historical Hamar traceback and exact reproduction command are unavailable.\n\nComplete methods and caveats: docs/reports/verified-results-2026-10-23.md; docs/reports/evidence-2026-10-23.json; docs/reports/verify_evidence.py.")[li]
        write(folder / "20_historical_evidence.md", "# " + ("Historisk evidens og feiltilfeller", "Historical evidence and failure cases")[li] + "\n\n" + intro + mdtable(headers, rows) + "\n" + ending)
        # Clarify that the current publisher is a frozen, validated reporting view.
        reproduction = folder / "15_reproduction.md"
        text = reproduction.read_text(encoding="utf-8")
        text += "\n\n" + (
            "Rapportgeneratorene validerer det innsamlede utvalget eksplisitt. Ved en ny forsøksserie med annet antall fullførte kall må nye utvalg og etiketter gjennomgås i forsøkskopien; ikke tving gamle summer inn i nye logger. Full tospråklig tabell: 01_full_requirements.md. Historiske tabeller: 20_historical_evidence.md. Sluttkontroll kjøres med `python -X utf8 resultat/audit_package.py`.",
            "Report generators explicitly validate the collected sample. For a new experimental series with a different completed-call count, review sample assumptions and labels in the experimental copy; do not force old totals into new logs. Full bilingual matrix: 01_full_requirements.md. Historical tables: 20_historical_evidence.md. Run the final audit with `python -X utf8 resultat/audit_package.py`.")[li]
        reproduction.write_text(text, encoding="utf-8")
    consistency = BASE / "logger/bilingual-consistency.json"
    record = json.loads(consistency.read_text(encoding="utf-8"))
    record["shared_data_sha256"] = hashlib.sha256(data_path.read_bytes()).hexdigest()
    record["historical_results_reused_from_shared_data"] = True
    consistency.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Historical evidence added in both languages without new experiments.")


if __name__ == "__main__":
    main()
