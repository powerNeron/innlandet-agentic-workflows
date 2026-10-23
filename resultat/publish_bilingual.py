"""Publiser begge språk fra ett målegrunnlag. Ingen nye forsøk eller appendringer.

python -X utf8 resultat/publish_bilingual.py
Opprettelser er eksklusive; ikke overskriv den opprinnelige evidensen.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


def read(name):
    return json.loads((BASE / name).read_text(encoding="utf-8-sig"))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text.rstrip() + "\n")


def csvread(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def csvwrite(path, columns, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(columns); writer.writerows(rows)


def mdtable(headers, rows):
    return "| " + " | ".join(headers) + " |\n|" + "|".join("---" for _ in headers) + "|\n" + "\n".join(
        "| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |" for row in rows) + "\n"


# English descriptions translate the same atomic requirement IDs, not a new rubric.
EN_REQ = {
"A01": ("Recurring information need in Innlandet", "Problem and intended users", "Students review the wording"),
"A02": ("Work in pairs", "Genuine collaboration and responsibilities", "Students confirm contributions and collaboration"),
"A03": ("No processing of identifying personal data", "Data boundary and actual compliance", "Resolve historical HTML processing and institutional privacy approval"),
"A04": ("Respect sources and limit republication", "Exact URLs and acquisition restrictions", "No new acquisition; actual review at expiry"),
"A05": ("Norwegian local context and official institutions", "Relevant answers and official links", "Independent human relevance review recommended"),
"T01": ("Input and checkable output", "Executable observable path", "Retain the limitations in the report"),
"T02": ("More than one stage", "Executable observable path", "Retain the limitations in the report"),
"T03": ("Use of tools, files or external data", "Executable observable path", "Retain the limitations in the report"),
"T04": ("At least one automatic stage", "Executable observable path", "Retain the limitations in the report"),
"C01": ("Both a report and a walking skeleton", "Completed report and executable software", "Write and compile the submission report"),
"C02": ("Problem, need, intended users and output", "Content in the actual submission", "Transfer verified material to the English report"),
"C03": ("Success criteria and correctness checks", "Content in the actual submission", "Transfer verified material to the English report"),
"C04": ("Architecture, context, stages and automation", "Content in the actual submission", "Transfer verified material to the English report"),
"C05": ("Milestones planned backwards from the demonstration", "Confirmed demonstration date and schedule", "Supply the date and approve milestones"),
"C06": ("Risk assessment and mitigations", "Content in the actual submission", "Transfer verified material to the English report"),
"C07": ("Repository link in the report", "Content in the actual submission", "Transfer verified material to the English report"),
"C08": ("An end-to-end workflow path", "Real input to checkable output", "None"),
"C09": ("README permits reproduction", "All necessary inputs available", "Arrange lawful catalog transfer and test a clean checkout"),
"C10": ("Harness context files in the repository", "Instructions and fixtures", "None"),
"C11": ("Supplied LaTeX template", "Original template and report source", "Provide the supplied template"),
"C12": ("NeurIPS preprint format; remove checklist", "Source and compiled PDF", "Use neurips_2025 with preprint and inspect the PDF"),
"C13": ("3–4 pages of main text", "Compiled report and page count", "Compile and count pages excluding references and appendices"),
"C14": ("Report written in English", "Completed English main text", "Write the English submission report"),
"C15": ("Appendix included", "Assembled appendix", "Assemble and compile the appendix"),
"C16": ("Representative agent prompt excerpts, at most two pages", "Genuine excerpts and page count", "Select excerpts and verify at most two PDF pages"),
"C17": ("Meeting reports demonstrate reasoning and revisions", "Genuine events confirmed by participants", "Confirm which documents describe actual meetings"),
"A06": ("Systematic testing, stress testing and validation before the demonstration", "Recorded runs and demonstration confirmation", "Confirm the demonstration and complete a thermally safe plan if necessary"),
"E01": ("Final white-paper grading criteria", "Complete authoritative text", "Provide the complete official final assignment"),
"E02": ("At least two of four specified fault classes, with failures, causes, repairs and regression", "Class names and complete experimental chains", "Map to official classes and clarify repairs; approve application changes separately"),
"E03": ("An enforced global kill switch", "Termination of ongoing computation", "Authorize separate design and implementation of a genuine emergency stop"),
"E04": ("Enforced token and cost budgets", "Per-call and aggregate budgets", "Authorize a global session budget; measure monetary or energy costs if relevant"),
"E05": ("Enforced permissions and human approval gates", "Forbidden operations rejected", "Clarify authentication of actual reviewers; OS controls are not application approval gates"),
"E06": ("At least eight genuine meeting reports", "Eight actual meetings with confirmed decisions", "Students document actual events; do not invent or backdate meetings"),
"E07": ("Representative Codex prompt log", "Genuine representative interactions", "Students select excerpts and confirm representativeness"),
"W40": ("Compare against the actual W40 teaching material", "Original teaching material", "Supply the file path; no missing criteria are guessed"),
"U01": ("User assessment", "Anonymous voluntary responses", "Students conduct a voluntary approved survey"),
}


def verify_existing_publication():
    """Idempotent default for an already published package: never overwrite logs."""
    shared = read("data/shared.json")
    no, en = read("norsk/verified_values.json"), read("english/verified_values.json")
    assert no == en
    assert no["date"] == shared["date"] and no["commit"] == shared["code_commit"]
    assert no["source_metrics"] == shared["source_metrics"]
    assert no["coverage"] == [[r["id"], r["status"]] for r in shared["requirements"]]
    assert no["historical"] == shared["historical"]
    for name in ("02_test_results.csv", "04_response_times.csv", "19_token_usage.csv"):
        values = []
        for language in ("norsk", "english"):
            with (BASE / language / name).open(encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))[1:]
            values.append([row[:-1] for row in rows] if name == "02_test_results.csv" else rows)
        assert values[0] == values[1], name
    assert read("norsk/figurer/data.json") == read("english/figurer/data.json")
    # CSV-derived token fields are strings; compare them numerically.
    expected = sum(int(row["eval_count"]) for row in shared["token_rows"])
    assert expected == shared["summary"]["model"]["output_tokens"]
    print("Existing bilingual publication verified; no data or historical logs overwritten.")


def main():
    if (BASE / "data/shared.json").exists():
        verify_existing_publication()
        return
    summary = read("logger/oppsummering.json")
    model = read("logger/model-measurements.json")
    smoke = read("logger/real-smoke/summary.json")
    faults = read("logger/fault-injection.json")
    gates = read("logger/approval-gates.json")
    stress = read("logger/http-stress.json")
    reqs = read("logger/dekning.json")["requirements"]
    results = csvread(BASE / "02_testresultater.csv")
    latencies = csvread(BASE / "04_ytelse_og_responstider.csv")
    tokens = csvread(BASE / "19_tokenbruk.csv")
    assert summary["offline"]["passed"] == 282 and len(model["rows"]) == 14
    # Independently re-check every persisted positive real-model answer.
    import sys
    sys.path.insert(0, str(ROOT))
    from hamar_agent.portal_sources import load_approvals, load_catalog
    catalog = load_catalog(ROOT / "output/municipal-catalog.json", load_approvals(ROOT / "docs/approved-service-pages.json"))
    checked_outputs = checked_claims = 0
    for path in sorted((BASE / "logger/real-smoke").glob("*.json")):
        if path.name == "summary.json":
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        result = item.get("result") if "answer_status" in item else item
        if result is None:
            continue
        for claim in result["claims"]:
            if ":" in claim["paragraph_id"]:
                source, paragraph = claim["paragraph_id"].rsplit(":", 1)
            else:
                source, paragraph = result["source"]["id"], claim["paragraph_id"]
            doc = catalog.documents[source]
            expected = next(p.text for p in doc.source.paragraphs if p.id == paragraph)
            assert claim["text"] == claim["evidence_quote"] == expected
            citations = item.get("citations", result["source_provenance"])
            assert any(c["source_id"] == source and c["url"] == doc.source.url and c["paragraph_id"] == claim["paragraph_id"] for c in citations)
            checked_claims += 1
        checked_outputs += 1
    assert checked_outputs == checked_claims == 17
    source_metrics = {"documents": 8, "paragraphs": 39, "saved_positive_results": checked_outputs,
                      "independently_matched_claims": checked_claims, "approval_expires": "2026-10-28",
                      "live_pages_fetched_during_task": 0, "catalog_modified": False}
    shared = {"date": "2026-10-23", "code_commit": summary["commit"], "summary": summary,
              "source_metrics": source_metrics, "test_results": results, "latency_rows": latencies,
              "token_rows": tokens, "requirements": reqs, "faults": faults,
              "gates": gates, "stress_phases": stress["phases"], "survey_responses": 0,
              "historical": json.loads((ROOT / "docs/reports/evidence-2026-10-23.json").read_text(encoding="utf-8"))["historical"]}
    write(BASE / "data/shared.json", json.dumps(shared, ensure_ascii=False, indent=2))
    test_descriptions = {
      "O1": ("Offline-regresjon", "Offline regression"),
      "O2": ("Separat lagret syntetisk holdout", "Separately stored synthetic holdout"),
      "O3": ("Syntetisk funnkodedeteksjon", "Synthetic finding-code detection"),
      "M1": ("Reell modell: svar og tilsiktede avslag", "Real model: answers and expected refusals"),
      "M2": ("Reelle målinger: temperaturavbrutt utvalg", "Real measurements: thermally curtailed sample"),
      "F": ("Isolerte feil- og korreksjonsforsøk", "Isolated fault and correction experiments"),
      "P": ("Tillatelses- og promptgrenser", "Permission and prompt boundaries"),
      "G": ("Godkjennings- og endepunktporter", "Approval and endpoint gates"),
      "S": ("Syntetisk HTTP-baseline, feil og gjenoppretting", "Synthetic HTTP baseline, perturbation and recovery"),
      "B": ("Navngitte spørsmål i ekte Chrome", "Named questions in actual Chrome"),
      "KILL": ("Global beregningsstopp: ikke håndhevet", "Global computation stop: not enforced"),
      "SEM": ("Semantisk injeksjonsimmunitet: ikke etablert", "Semantic injection immunity: not established"),
    }
    common_rows = [[r["id"], r["dato"], int(r["antall"]), int(r["bestatt"]), int(r["ikke_bestatt"]), "../" + r["logg"]] for r in results]
    row_ids = [r["id"] for r in results]
    captions = {
        "01": (
          "Figur 1. Portalresponstid for reelle modellkall: 12 sekvensielle og 2 samtidige observasjoner. Punkter er enkeltmålinger, svarte streker er medianer. Planen var 20 forespørsler; serien ble stoppet etter 14 ved GPU-temperatur 80 °C, over den definerte stoppgrensen 78 °C. Datagrunnlag: logger/model-measurements.json.",
          "Figure 1. Portal response times for real model calls: 12 sequential and 2 concurrent observations. Points are individual measurements; black segments show medians. The plan comprised 20 requests; the series stopped after 14 at a GPU temperature of 80 °C, above the specified 78 °C stop threshold. Source: logger/model-measurements.json."),
        "02": (
          "Figur 2. Empirisk kumulativ fordeling av HTTP-søkeresponstid med 8 arbeidere: baseline n=64, perturbasjon n=256 og gjenoppretting n=64. Perturbasjonen inneholder 16 forventede HTTP403-avslag; alle fasene hadde 0 uventede utfall. Ingen modellkall inngår. Datagrunnlag: logger/http-stress.json.",
          "Figure 2. Empirical cumulative distribution of HTTP search latency with 8 workers: baseline n=64, perturbation n=256 and recovery n=64. The perturbation contains 16 expected HTTP403 rejections; all phases had 0 unexpected outcomes. No model calls are included. Source: logger/http-stress.json."),
    }
    token_input = summary["model"]["input_tokens"]
    token_output = summary["model"]["output_tokens"]
    mseq = model["latency_by_batch"]["sequential"]
    mconc = model["latency_by_batch"]["concurrency-2"]
    stage_names = {"baseline": ("Baseline", "Baseline"), "perturbation": ("Perturbasjon", "Perturbation"), "recovery": ("Gjenoppretting", "Recovery")}
    matrix_rows = []
    for r in reqs:
        scope_en = {"felles": "shared", "Compulsory 2": "Compulsory 2", "sluttartikkel": "final white paper", "undervisningskontekst": "teaching context", "tilleggsanbefaling": "additional recommendation"}[r["omfang"]]
        desc, needed, action = EN_REQ[r["id"]]
        if r["id"].startswith("E"):
            loc_en = "User supplement; complete official final criteria unavailable"
            if r["id"] == "E06":
                loc_en += "; absent from local §2"
        elif r["id"] == "W40":
            loc_en = "W40_KIUA_2003 unavailable"
        else:
            loc_en = r["plassering"]  # Official section labels already use English.
        matrix_rows.append((r, scope_en, loc_en, desc, needed, action))
    numeric_payloads = {}
    for lang, li in (("norsk", 0), ("english", 1)):
        folder = BASE / lang; folder.mkdir(exist_ok=True)
        (folder / "figurer").mkdir(exist_ok=True)
        heading = ("Verifiserte resultater", "Verified results")[li]
        header = f"# {heading}\n\nKIUA-2003 — Hamar KommuneAgent. 2026-10-23. Commit `{summary['commit']}`.\n\n"
        intro = (
            "Dette er et rapportgrunnlag, ikke en ferdig eller godkjent innlevering. Offisiell tekst som er tilgjengelig lokalt dekker bare Compulsory 2. Full sluttoppgave, W40-materiale, utdelt LaTeX-mal og demonstrasjonsdato mangler. Alle tall hentes fra [felles datasett](../data/shared.json); ingen forsøk ble kjørt om igjen for oversettelsen.\n\n",
            "This package supports report writing; it is not a completed or approved submission. The locally available authoritative text covers only Compulsory 2. The complete final assignment, W40 material, supplied LaTeX template and demonstration date are unavailable. All numerical results come from the [shared dataset](../data/shared.json); no experiments were repeated for translation.\n\n")[li]
        headers = (["ID", "Dato", "n", "Bestått", "Ikke bestått", "Logg", "Tolkning"],
                   ["ID", "Date", "n", "Passed", "Not passed", "Log", "Interpretation"])[li]
        table_rows = [row + [test_descriptions[identifier][li]] for identifier, row in zip(row_ids, common_rows)]
        csvwrite(folder / "02_test_results.csv", headers, table_rows)
        write(folder / "02_test_results.md", "# " + heading + "\n\n" + mdtable(headers, table_rows) + "\n" + (
            "Radene er forskjellige forsøksenheter og overlapper delvis. De skal ikke summeres til én treffsikkerhet. KILL og SEM er negative sikkerhetsfunn; 0 betyr at den sterkere sikkerhetsegenskapen ikke ble oppfylt. Reelle modelltester inkluderer tilsiktede avslag.",
            "Rows represent different and partly overlapping experimental units. They must not be pooled into one accuracy score. KILL and SEM are negative safety findings: 0 means the stronger safety property was not satisfied. Real-model tests include expected refusals.")[li])
        # CSV labels translate; the underlying numerical fields and references are identical.
        lat_headers = (["Forsøk", "Tilfelle", "Gruppe", "Enhet", "Verdi", "Omfang", "Logg"],
                       ["Experiment", "Case", "Group", "Unit", "Value", "Scope", "Log"])[li]
        translated_latencies = [[r["forsok"], r["case"], r["gruppe"], r["enhet"], r["verdi"], r["omfang"], "../" + r["logg"]] for r in latencies]
        csvwrite(folder / "04_response_times.csv", lat_headers, translated_latencies)
        token_headers = (["Fullføringsrekkefølge", "Prompttoken", "Genererte token", "Prompttid ns", "Genereringstid ns", "Lastetid ns", "Totaltid ns", "Forespurt utgrense", "Stoppårsak"],
                         ["Completion order", "Prompt tokens", "Generated tokens", "Prompt time ns", "Generation time ns", "Load time ns", "Total time ns", "Requested output cap", "Stop reason"])[li]
        csvwrite(folder / "19_token_usage.csv", token_headers, [[r[k] for k in tokens[0]] for r in tokens])
        perf_headers = (["Gruppe", "n", "Median ms", "p95 ms", "Min ms", "Maks ms", "Logg"],
                        ["Group", "n", "Median ms", "p95 ms", "Min ms", "Max ms", "Log"])[li]
        perf = [[("Sekvensielt", "Sequential")[li], *[mseq[k] for k in ("n", "median_ms", "p95_nearest_rank_ms", "min_ms", "max_ms")], "../logger/model-measurements.json"],
                [("Samtidighet 2", "Concurrency 2")[li], *[mconc[k] for k in ("n", "median_ms", "p95_nearest_rank_ms", "min_ms", "max_ms")], "../logger/model-measurements.json"]]
        stress_headers = (["Fase", "n", "Median ms", "p95 ms", "Forespørsler/s", "Forventede avslag", "Uventede utfall"],
                          ["Phase", "n", "Median ms", "p95 ms", "Requests/s", "Expected rejections", "Unexpected outcomes"])[li]
        stress_rows = [[stage_names[p][li], *[v[k] for k in ("n", "median_ms", "p95_nearest_rank_ms", "requests_per_s", "expected_rejections", "unexpected_outcomes")]] for p, v in stress["phases"].items()]
        write(folder / "04_performance_summary.md", "# " + ("Ytelse og tokenmåling", "Performance and token measurements")[li] + "\n\n" + mdtable(perf_headers, perf) + "\n" + (
            f"Totalt rapporterte Ollama {token_input} prompttoken og {token_output} genererte token for 14 fullførte modellkall. Tokendata gjelder bare den instrumenterte måleserien, ikke hele prosjektet. Grensen 700 er en forespurt utgrense per kall, ikke et globalt token- eller kostnadsbudsjett. Lokale API-kall er målt; energikostnad og fakturert pris er ikke målt.\n\n",
            f"Ollama reported {token_input} prompt tokens and {token_output} generated tokens across 14 completed model calls. Token measurements cover only the instrumented series, not the entire project. The 700 limit is a requested per-call output cap, not a global token or cost budget. Local API calls were measured; energy cost and invoiced monetary cost were not measured.\n\n")[li] + mdtable(stress_headers, stress_rows))
        req_headers = (["ID", "Omfang", "Plassering", "Krav", "Evidensbehov", "Status", "Neste handling", "Sporing"],
                       ["ID", "Scope", "Location", "Requirement", "Evidence needed", "Status", "Next action", "Trace"])[li]
        translated_matrix = []
        for r, scope_en, loc_en, desc, needed, action in matrix_rows:
            translated_matrix.append([r["id"], r["omfang"] if li == 0 else scope_en,
                r["plassering"] if li == 0 else loc_en, r["krav"] if li == 0 else desc,
                r["evidensbehov"] if li == 0 else needed, r["status"], r["neste_handling"] if li == 0 else action,
                "../kravmatrise.csv#" + r["id"]])
        csvwrite(folder / "01_requirements.csv", req_headers, translated_matrix)
        write(folder / "01_requirements.md", "# " + ("Kravdekning", "Requirements coverage")[li] + "\n\n" + (
            "Full evidenskjede for hver rad (eksisterende og ny evidens, verifikasjonsmetode og restarbeid) finnes i den felles kravmatrisen. Status er vurdert for det konkrete kravet, ikke som en karakterprosent. E-krav er brukerens tillegg; manglende offisiell tekst erstattes ikke av gjetting.\n\n",
            "The complete evidence chain for every row (existing and new evidence, verification method and remaining work) is retained in the shared requirements matrix. Status refers to the individual requirement, not a grading percentage. E requirements are user supplements; missing authoritative criteria are not guessed.\n\n")[li] + mdtable(req_headers, translated_matrix))
        caption_text = "# " + ("Figurer og tabeller", "Figures and tables")[li] + "\n\n"
        for key, stem in (("01", "01_model_response_times"), ("02", "02_http_latency_distribution")):
            caption_text += captions[key][li] + f"\n\n![{stem}](figurer/{stem}.png)\n\n[SVG](figurer/{stem}.svg)\n\n"
        caption_text += ("Figur 3. Kildebasert flertrinnsarbeidsflyt. Diagrammet er arkitektur, ikke en måling. Kilde: hamar_agent/portal.py og hamar_agent/real_sources.py.",
                         "Figure 3. Multi-stage source-grounded workflow. The diagram describes architecture, not a measurement. Source: hamar_agent/portal.py and hamar_agent/real_sources.py.")[li]
        write(folder / "10_figures_and_tables.md", caption_text)
        # Numeric evidence companion is deliberately identical in both languages.
        payload = {"date": shared["date"], "commit": summary["commit"], "results": common_rows,
                   "latencies": [[r[k] for k in r] for r in latencies], "tokens": [[r[k] for k in r] for r in tokens],
                   "source_metrics": source_metrics, "coverage": [[r["id"], r["status"]] for r in reqs],
                   "survey_responses": 0}
        write(folder / "verified_values.json", json.dumps(payload, ensure_ascii=False, indent=2))
        numeric_payloads[lang] = payload
        write(folder / "00_READ_ME.md", header + intro + (
            "Les resultatoversikten, målemetoden, sikkerhetsanalysen og eksamenssjekklisten samlet. Rålogger ligger i ../logger/. Engelske tabeller og figurer har samme tall som de norske.\n\nRepository: https://github.com/powerNeron/innlandet-agentic-workflows\n\n",
            "Read the results, measurement methodology, safety analysis and final-exam checklist together. Raw logs are stored in ../logger/. English tables and figures use exactly the same numbers as their Norwegian counterparts.\n\nRepository: https://github.com/powerNeron/innlandet-agentic-workflows\n\n")[li] + mdtable(headers, table_rows))
        write(folder / "03_methodology.md", "# " + ("Evaluering og målemetode", "Evaluation and measurement methodology")[li] + "\n\n" + (
            "Offline-tester blokkerer sockets og DNS. Reelle modelltester bruker kun godkjent lokal katalog og Ollama på loopback. Feilinjeksjon skjer i nye prosesslokale testinstanser med oppdiktet tekst; ingen godkjent kilde endres. Testfixture merkes eksplisitt som syntetisk i forsøksloggen selv når realadapterens ikke-syntetiske kodebane simuleres. Nettlesertester er automatiserte Chrome-forsøk, ikke en menneskelig brukerstudie.\n\nEnheten er henholdsvis unittest, kuratert spørsmål, HTTP-forespørsel, modellkall eller sikkerhetsegenskap. Disse skal ikke summeres til én suksessrate. Modelltilfellene er gjenbrukte tjenestespørsmål, ikke uavhengige tilfeldige observasjoner. p95 bruker nearest-rank: sortert observasjon ceil(0.95*n). Vi oppgir ikke populasjonskonfidensintervall fra dette avhengige utvalget.\n\nM2 måler veggklokketid rundt portal.answer; M1s provider_latency_ms måler arbeidsflyt inklusive kontroll. HTTP-søketiden inkluderer klient/server, men ingen modell. Ollamas varighetsfelt har enhet ns. Samtidige tokenposter følger fullføringsrekkefølge og er ikke koblet vilkårlig til en forespørselsindeks. Måleinstrumentering og GPU-stopp finnes bare i evalueringsskriptet.\n\nForsøkene var ikke forhåndsregistrert eksternt. Kriteriene ble kodet før den aktuelle kjøringen. Den separat lagrede holdout-filen er allerede kjent i prosjektet og er derfor ingen ny blindtest. Ingen ny kjøring ble gjort for språkoversettelsen. Se ../run_experiments.py og ../logger/kommandoer.jsonl.",
            "Offline tests block sockets and DNS. Real-model tests use only the approved local catalog and loopback Ollama. Faults are injected into new process-local test instances using invented text; no approved source is modified. The experiment log explicitly identifies fixtures as synthetic even when a non-synthetic real-adapter code path is simulated. Browser tests are automated Chrome experiments, not a human usability study.\n\nThe unit is respectively a unittest, curated question, HTTP request, model call or safety property. These units must not be pooled into one success rate. Model cases repeat service questions rather than representing independent random observations. p95 uses nearest rank: sorted observation ceil(0.95*n). No population confidence interval is inferred from this dependent sample.\n\nM2 measures wall time around portal.answer; M1 provider_latency_ms measures the workflow including verification. HTTP search latency includes client/server work but no model. Ollama duration fields use ns. Concurrent token records follow completion order and are not arbitrarily joined to request indices. Instrumentation and the GPU safety stop exist only in the evaluation script.\n\nExperiments were not externally preregistered. Criteria were encoded before the respective run. The separately stored holdout file is already known within the project and is therefore not a new blind test. No run was repeated for translation. See ../run_experiments.py and ../logger/kommandoer.jsonl.")[li])
        source_headers = (["Mål", "Verdi", "Kilde"], ["Measure", "Value", "Source"])[li]
        source_rows = [[("Godkjente dokumenter", "Approved documents")[li], 8, "docs/approved-service-pages.json"],
                       [("Godkjente avsnitt", "Approved paragraphs")[li], 39, "docs/reviewed-service-selection.json"],
                       [("Lagrede positive svar kontrollert på nytt", "Stored positive answers independently rechecked")[li], 17, "logger/real-smoke/*.json"],
                       [("Påstander med eksakt samsvar og kilde-URL", "Claims with exact support and source URL")[li], 17, "logger/real-smoke/*.json"],
                       [("Godkjenningsutløp", "Approval expiry")[li], "2026-10-28", "docs/approved-service-pages.json"],
                       [("Nye kommunale nettinnhentinger", "New municipal live retrievals")[li], 0, "run_experiments.py"]]
        write(folder / "05_sources_privacy_security.md", "# " + ("Kildekontroll, personvern og sikkerhet", "Source verification, privacy and security")[li] + "\n\n" + mdtable(source_headers, source_rows) + "\n" + (
            "M1 har 18 positive modelltilfeller. Bare 17 egne resultatfiler finnes fordi én SFO-repetisjon ikke lagres separat. Sammendragets grounded_claims=14 er en delsummering; fire positive spørsmålsrader mangler dette feltet. citation_checks_passed=23 omfatter også riktige avslag, ikke 23 positive sitater.\n\nBackend krever ordrett helt kildeavsnitt og gyldig proveniens. Dette sertifiserer ikke semantisk sannhet eller full kontekst. Menneskelig godkjenning av kildetekst er en sentral tillitsgrense. Et isolert syntetisk moteksempel viste at et ordrett instruksjonsavsnitt kan få null verifikasjonsfunn.\n\nTillatelser ble testet med ugyldig Host, Origin, økt-token, modellvalg, ukjent request-felt og oversize request. Personverntilfellet bruker bare oppdiktet kontakttekst. Modellen ble ikke kalt for disse avslagene. G-testene verifiserer at både eksternaktivering og personvernflagg kreves, og at alle lokale sjekklister må være satt før en godkjenningspost opprettes. Selv en slik post kan ikke aktivere kilden. Rollene er selverklærte, ikke identitetsautentiserte.\n\nIngen rå HTML ble hentet. Lokalt katalogoppslag er ikke levende nettsøk. Historisk HTML-behandling og full institusjonell personvernetterlevelse forblir uavklart. 43 gamle evidensfiler, inkludert kildekatalogen og manifestene, er kontrollert uendret mot tidligere SHA-256. Se ../logger/historisk-hashkontroll.json. Reelle økt-token og nettleserprofiler publiseres ikke.",
            "M1 contains 18 positive model cases. Only 17 separate positive output files exist because one repeated SFO run is not stored separately. The summary grounded_claims=14 is a partial sum; four positive question rows omit this field. citation_checks_passed=23 also includes correct refusals, not 23 positive citations.\n\nThe backend requires a verbatim complete source paragraph and valid provenance. This does not certify semantic truth or complete context. Human source approval remains a central trust boundary. An isolated synthetic counterexample showed that a verbatim instructional paragraph can receive no verification findings.\n\nPermissions were tested using invalid Host, Origin, session token, model selection, unknown request fields and an oversized request. The privacy case uses invented contact text only. These rejections made no model calls. G tests verify that both external enablement and privacy flags are required, and that all local checklist fields must be set before an approval record is created. Even such a record cannot activate a source. Reviewer roles are self-attested, not identity-authenticated.\n\nNo raw HTML was fetched. Local catalog retrieval is not live website search. Historical HTML processing and complete institutional privacy compliance remain unresolved. A total of 43 older evidence files, including the catalog and approval manifests, were checked unchanged against previous SHA-256 values. See ../logger/historisk-hashkontroll.json. Real session tokens and browser profiles are not published.")[li])
        fault_headers = (["ID", "Injisert mekanisme", "Baseline HTTP", "Feil HTTP", "Kall under feil", "Gjenoppretting HTTP", "Forventet kontroll bestått"],
                         ["ID", "Injected mechanism", "Baseline HTTP", "Fault HTTP", "Calls under fault", "Recovery HTTP", "Expected control passed"])[li]
        fault_labels = {
          "F01": ("Tidsavbrudd", "Timeout"), "F02": ("Tilkobling avvist", "Connection refused"),
          "F03": ("Avkortet JSON", "Truncated JSON"), "F04": ("Manglende svarfelt", "Missing response field"),
          "F05": ("For stort svar", "Oversized response"), "F06": ("Feil avgift vedvarer", "Wrong fee persists"),
          "F07": ("Falsk avsnitts-ID", "Forged paragraph ID"), "F08": ("Vilkår fjernet", "Condition removed"),
          "F09": ("Verifikator utilgjengelig", "Verifier unavailable"), "F10": ("Utløpt testgodkjenning", "Expired test approval"),
          "F11": ("Feil avgift korrigeres", "Wrong fee corrected")}
        frows = [[r["id"], fault_labels[r["id"]][li], r.get("baseline_http", "—"), r["observed_http"],
                  r.get("model_calls_under_fault", r.get("model_calls")), r.get("recovery_http", "—"), r["pass"]] for r in faults["cases"]]
        write(folder / "06_stress_failures_regression.md", "# " + ("Stresstesting og kausal feilanalyse", "Stress testing and causal failure analysis")[li] + "\n\n" + mdtable(stress_headers, stress_rows) + "\n" + mdtable(fault_headers, frows) + "\n" + (
            "Hypotese for F01–F10: en injisert feil skal hindre nye publiserte svar; fjerning av feilen skal gjenopprette normal behandling. Baseline gir HTTP200. Testen måler provider-kall og resultatlager før/etter, og gjentar normalforespørselen etter restaurering. HTTP400 ved utløpt kilde skyldes avvisning i kildevalget før modellkall.\n\nAvhengighetsklassen: F01/F02 fjerner tilgjengelig modelltransport i en isolert instans. Årsaken er det injiserte unntaket; appens eksisterende feilgrense gir HTTP422 uten nytt resultat. Transporten gjenopprettes, og samme instans gir HTTP200. Dette er gjenoppretting fra feil, ikke en ny kodereparasjon.\n\nEvidensklassen: F06 returnerer feil avgift både før og etter korreksjon. To kall gir fortsatt utilstrekkelig støtte og HTTP422. F11 endrer bare andre modellrespons til riktig godkjent avsnitt: eksisterende korreksjon og ny verifikasjon gir HTTP200 etter to kall. Dette er en kontrollert kontrafaktisk demonstrasjon av eksisterende reparasjonsmekanisme, ikke en nylig reparert programdefekt.\n\nGlobal nødstopp: en barriere holder transporten i arbeid; samtalen nullstilles mens den kjører. Etter frigivelse fullfører transporten, men publisering av det gamle svaret avvises med HTTP409. Publiseringsvern fungerer; beregningsavbrytelse gjør det ikke. Foreslått separat reparasjon: global avbrytelsestilstand, nye kall sperres, avbrytbar transport og etterprøvbar terminering. Ingen appreparasjon er utført.\n\nDet finnes seks egenvalgte mekanismeklasser i F-serien. Navnene på de fire offisielle klassene mangler. Vi kan derfor ikke hevde at minst to av dem er dekket. Kaldstartfeilen i historiske logger er en driftsobservasjon, ikke planlagt feilinjeksjon. Eldre belastningsforsøk og sikkerhetsfeil er fortsatt bevart i docs/reports/verified-results-2026-10-23.md.",
            "Hypothesis for F01–F10: an injected fault must prevent new published answers; removing the fault must restore normal processing. Baseline requests return HTTP200. The experiment measures provider calls and result storage before/after, then repeats a normal request after restoration. HTTP400 for an expired source results from source-selection rejection before model invocation.\n\nDependency class: F01/F02 make model transport unavailable in an isolated instance. The cause is the injected exception; the existing application error boundary returns HTTP422 without a new result. Restoring transport makes the same instance return HTTP200. This is fault recovery, not a new code repair.\n\nEvidence class: F06 returns an incorrect fee both before and after correction. Two calls still lack support and return HTTP422. F11 changes only the second model response to the correct approved paragraph: existing correction and re-verification return HTTP200 after two calls. This is a controlled counterfactual demonstration of an existing repair mechanism, not a newly repaired application defect.\n\nGlobal emergency stop: a barrier keeps transport running while the conversation is reset. After release, transport completes, but stale publication is rejected with HTTP409. Publication protection works; computation cancellation does not. Proposed separate repair: global cancellation state, prevention of new calls, cancellable transport and verifiable termination. No application repair was performed.\n\nThe F series contains six researcher-defined mechanism classes. Names of the four official classes are unavailable. We therefore cannot claim that at least two of them are covered. The historical cold-start failure is an operational observation, not deliberate fault injection. Older load experiments and security failures remain documented in docs/reports/verified-results-2026-10-23.md.")[li])
        survey_items = (
          ["Det var enkelt å finne søkefeltet.", "Det var enkelt å stille et spørsmål til AI-agenten.", "Informasjonen var lett å forstå.", "Kildehenvisningene gjorde det enklere å vurdere svaret.", "Det var tydelig når kildegrunnlaget ikke var tilstrekkelig.", "Utformingen var lett å bruke på skjermen jeg benyttet.", "Jeg opplevde tjenesten som pålitelig innenfor oppgitt avgrensning.", "Tjenesten kan være nyttig for innbyggere som søker kommunal informasjon."],
          ["The search field was easy to find.", "It was easy to ask the AI agent a question.", "The information was easy to understand.", "Source references made the answer easier to assess.", "It was clear when source evidence was insufficient.", "The layout was easy to use on my screen.", "I perceived the service as reliable within its stated scope.", "The service could benefit residents seeking municipal information."])[li]
        write(folder / "07_user_survey.md", "# " + ("Frivillig anonym brukervurdering", "Voluntary anonymous user assessment")[li] + "\n\n" + (
            "Antall innsamlede svar: 0. Dette er et instrument og en tom mal, ikke et resultat. Deltakelse er frivillig. Ikke oppgi navn, e-post, adresser, kontoer, helseopplysninger eller fritekst som kan identifisere noen. Ikke registrer IP, tidspunkt, enhet-ID eller demografi. Ingen automatisk utsending eller datainnsamling er aktivert.\n\nBruk oppdiktede generelle oppgaver: finn parkering, spør om bygging uten søknad, finn offisiell kilde og vurder et utilstrekkelig svar. Svar 1=helt uenig, 2=uenig, 3=nøytral, 4=enig, 5=helt enig; tomt felt betyr ikke besvart.\n\n",
            "Collected responses: 0. This is an instrument and an empty template, not a result. Participation is voluntary. Do not provide names, email addresses, locations, accounts, health information or identifying free text. Do not record IP addresses, timestamps, device identifiers or demographics. No distribution or data collection has been enabled.\n\nUse fictional general tasks: find parking information, ask about building without an application, locate an official source and assess an insufficient-evidence answer. Rate 1=strongly disagree, 2=disagree, 3=neutral, 4=agree, 5=strongly agree; leave unanswered items blank.\n\n")[li] + "\n".join(f"- Q{i}: {item}" for i, item in enumerate(survey_items, 1)) + "\n\n" + (
            "Analyseplan: rapporter antall gyldige svar, frekvens i hver svarkategori, median og manglende svar per spørsmål. Ikke erstatt manglende svar med null eller bruk meninger som mål på teknisk faktakorrekthet. Ikke publiser svært små undergrupper; oppgi utvalgs- og selvseleksjonsbias. Ingen statistikk skal beregnes fra den tomme malen.",
            "Analysis plan: report valid response counts, category frequencies, median and missing responses per item. Do not impute missing values as zero or treat opinions as technical factual accuracy. Do not publish tiny subgroups; disclose sampling and self-selection bias. No statistics should be computed from the empty template.")[li])
        csvwrite(folder / "survey_response_template.csv", [f"Q{i}" for i in range(1, 9)], [])
        write(folder / "08_architecture.md", "# " + ("Problem, arkitektur og kontekst", "Problem, architecture and context")[li] + "\n\n" + (
            "Problem: innbyggere må finne og vurdere kommunal tjenesteinformasjon. Prototypen samler søk og avgrensede kildeutdrag med offisielle lenker; nytte er en hypotese, ikke dokumentert samfunnseffekt. Suksess i denne evalueringen betyr riktige tekniske tilstander, eksakt avsnittsstøtte og trygge avslag, ikke generell faktakorrekthet.\n\nKontekst: systemregler om ubetrodd kildetekst, utvalgte godkjente avsnitt, JSON-kontrakt og eventuelle saniterte verifikasjonsfunn. Brukerens frie spørsmål sendes ikke til realadapteren. Søk og regelbaserte porter bestemmer avsnittsutvalget. Modellen velger ett helt avsnitt; den skriver ikke et fritt semantisk verifisert sammendrag.\n\nTrinn: inndatakontroll → lokal kataloggjenfinning og gyldighet → evidensport → lokal modell → uavhengig verifikasjon → høyst én korreksjon → ny kontroll → kildebasert svar. Ett spørsmål utløser disse trinnene automatisk. Verktøyene er filer, deterministisk søkeindeks og lokal HTTP-modell, ikke en fri shell-agent. Mennesket godkjenner kildemateriale før opptak og bestemmer om et faktisk kildevedlikehold er lovlig. Ingen ny kildeaktivering skjer automatisk.\n\nKjøreoppsett: Windows 11, Python 3.12.10, Ollama 0.40.8, llama3.2:3b, temperatur 0, seed 0, num_predict 700, 90 s socket-timeout i testene. Ingen ny avhengighet ble installert. Se ../logger/miljo.json. Diagram: figurer/03_workflow.mmd.",
            "Problem: residents need to locate and assess municipal service information. The prototype combines search with bounded excerpts and official links; usefulness is a hypothesis, not an established social impact. Success in this evaluation means correct technical states, exact paragraph support and safe refusals, not general factual accuracy.\n\nContext: system rules treating source content as untrusted data, selected approved paragraphs, the JSON contract and optional sanitized verification findings. Free-form user questions are not sent to the real adapter. Search and rule-based gates determine the paragraph selection. The model selects one whole paragraph rather than composing a freely generated semantically verified summary.\n\nStages: input checks → local catalog retrieval and validity → evidence gate → local model → independent verification → at most one correction → re-verification → source-linked answer. A single question triggers these stages automatically. Tools comprise files, a deterministic search index and local model HTTP, not an unrestricted shell agent. Humans approve source material before admission and decide whether actual source maintenance is lawful. No new source is activated automatically.\n\nRuntime: Windows 11, Python 3.12.10, Ollama 0.40.8, llama3.2:3b, temperature 0, seed 0, num_predict 700, 90 s socket timeout in tests. No new dependency was installed. See ../logger/miljo.json. Diagram: figurer/03_workflow.mmd.")[li])
        meetings = sorted(p.name for p in (ROOT / "docs/meetings").glob("*.md"))
        assert len(meetings) == 8
        write(folder / "09_agent_changes_meetings.md", "# " + ("Codex-arbeid, beslutninger og møter", "Codex work, decisions and meetings")[li] + "\n\n" + (
            "Det finnes 8 kandidatnotater i docs/meetings. Ingen av de 8 kan i dette revisjonssporet bekreftes som et faktisk møte med deltakerbekreftelse. Dette betyr ikke at møter ikke fant sted. Antall dokumentfiler er ikke antall genuine møter. Notatene inneholder implementasjonsvalg, testsummer, eierskapsgrenser og revisjoner; studentene må selv bekrefte faktisk møteproveniens uten å publisere personopplysninger.\n\n",
            "There are 8 candidate notes in docs/meetings. None of these 8 can be verified in this audit as an actual participant-confirmed meeting. This does not mean meetings did not occur. Document count is not a count of genuine meetings. Notes record implementation choices, test totals, ownership boundaries and revisions; students must confirm actual meeting provenance without publishing personal information.\n\n")[li] + "\n".join("- `docs/meetings/" + name + "`" for name in meetings) + "\n\n" + (
            "Tidligere Codex-endringer som inngår i commit-grunnlaget: synlig eksport og manuelt kontrollpanel fjernet, tekster forenklet og Om tjenesten lagt til, med regresjonstester. Denne oppgaven endrer bare resultatpakken. docs/prompt-log.md har saniterte sammendrag; representative faktiske dialogutdrag finnes i 17_prompt_excerpts.md. Bekreftede teammøter og individualisert arbeidsfordeling kan ikke konstrueres av assistenten.",
            "Earlier Codex changes in the evaluated commit remove visible export/manual control panels, simplify wording and add About information with regression tests. This task changes only the evidence package. docs/prompt-log.md contains sanitized summaries; representative actual dialogue excerpts are in 17_prompt_excerpts.md. The assistant cannot manufacture confirmed meetings or individual contribution histories.")[li])
        write(folder / "11_limitations.md", "# " + ("Begrensninger og refleksjon", "Limitations and reflection")[li] + "\n\n" + (
            "Utvalget er lite, gjentatt og valgt av utviklings-/evalueringsarbeidet. Ingen blind menneskelig relevans- eller sannhetsvurdering foreligger. Eksakt avsnittsstøtte er ikke semantisk faktasjekk; godkjent tekst kan være utdatert eller ha vilkår i andre avsnitt. Godkjenningen utløper 2026-10-28 og er ikke endret.\n\nGlobal nødstopp og aggregert token-/kostnadsbudsjett er ikke demonstrert som appkontroller. GPU-stoppen er kun i forsøksverktøyet, prøvetatt mellom bølger, og kunne først observere 80 °C etter at stoppgrensen 78 °C var passert. Ingen nye kall ble startet etter observasjonen; måleplanen ble ikke fullført. Den lille samtidighetsgruppen gir ikke en produksjons-SLA.\n\nMenneskelige undersøkelsessvar mangler. Nettleserskjermstørrelser er emulert i Chrome; ingen fysisk mobil- eller skjermleserstudie er utført. Full sluttoppgave og original mal mangler. Dette er ikke bevis på full oppgaveetterlevelse eller sikkerhet. Historiske mislykkede injeksjons-/belastningsforsøk skal beholdes, ikke skjules bak dagens beståtte tester.",
            "The sample is small, repeated and selected during development/evaluation. There is no blind human relevance or truth assessment. Exact paragraph support is not semantic fact checking; approved text may be outdated or have conditions in other paragraphs. Approval expires on 2026-10-28 and was not changed.\n\nA global emergency stop and aggregate token/cost budget have not been demonstrated as application controls. The GPU stop exists only in the experiment tool, sampled between waves, and first observed 80 °C after the specified 78 °C threshold had been crossed. No new calls were submitted after that observation; the plan was not completed. The small concurrency group does not establish a production SLA.\n\nHuman survey responses are absent. Viewports are emulated in Chrome; no physical mobile or screen-reader study was performed. The complete final assignment and original template are unavailable. This is not evidence of full assignment compliance or complete safety. Historical failed injection/load experiments must remain visible rather than being hidden behind current passing tests.")[li])
        counts = summary["coverage"]
        count_table = mdtable((["Status", "Antall"], ["Status", "Count"])[li], [[s, counts[s]] for s in counts])
        write(folder / "12_coverage_gaps.md", "# " + ("Kravdekning og mangelliste", "Coverage and outstanding evidence")[li] + "\n\n" + count_table + "\n" + (
            "Dette er 36 atomære poster med ulike omfang, inkludert tillegg og undervisningsmateriale; ingen offisiell karakterprosent er beregnet. Ved første gjennomgang ble manglende tokenmåling, fersk feilinjeksjon, gjenoppretting og godkjenningskontroll identifisert. Nye forsøk dekket disse målene avgrenset. Ved andre gjennomgang ble faktiske sikkerhetsmangler, termisk stopp og manglende menneskelig/offisiell evidens beholdt som åpne. Den siste gjennomgangen kontrollerer språkparitet, filintegritet og sporbarhet.\n\nNeste handlinger: skaff full sluttoppgave, de fire klassenavnene, W40 og LaTeX-mal; bekreft demonstrasjonsdato og baklengs plan; dokumenter genuine møter; godkjenn eventuelt separat reparasjon av global nødstopp og budsjett; gjennomfør menneskelig vurdering; bygg engelsk rapport og vedlegg og kontroller sidetall. Ingen menneskelige eller eksterne krav er utfylt med oppdiktet evidens.",
            "These are 36 atomic entries spanning different scopes, including supplements and teaching material; no official grading percentage was calculated. The first review identified missing token measurement, fresh fault injection, recovery and approval-gate evidence. New experiments provided bounded evidence for those aims. The second review retained actual safety gaps, the thermal stop and missing human/official evidence as open items. The final review checks language parity, integrity and traceability.\n\nNext actions: obtain the complete final assignment, four class names, W40 and LaTeX template; confirm the demonstration date and backwards plan; document genuine meetings; separately authorize any global-stop/budget repairs; conduct human assessment; compile the English report and appendices and verify page counts. No human or external requirement was filled using invented evidence.")[li])
        readiness_rows = [
          [("Full offisiell sluttoppgave", "Complete official final assignment")[li], "MISSING", "E01; W40"],
          [("Minst to av fire offisielle feilklasser", "At least two of four official fault classes")[li], "PARTIAL", "E02; ../logger/fault-injection.json"],
          [("Global kill switch", "Global kill switch")[li], "MISSING", "E03; KILL"],
          [("Token- og kostnadsbudsjetter", "Token and cost budgets")[li], "PARTIAL", "E04; ../19_tokenbruk.csv"],
          [("Tillatelser og ekte menneskegodkjenning", "Permissions and genuine human approval")[li], "PARTIAL", "E05; ../logger/approval-gates.json"],
          [("Åtte genuine møtereferater", "Eight genuine meeting reports")[li], "PARTIAL", "E06; 09_agent_changes_meetings.md"],
          [("Representative promptutdrag", "Representative prompt excerpts")[li], "PARTIAL", "E07; 17_prompt_excerpts.md"],
          [("Kjørbar evaluering og artefakter", "Executable evaluation and artifacts")[li], "VERIFIED", "O1; M1; S; B"],
          [("Ferdig formatert engelsk innlevering", "Completed formatted English submission")[li], "MISSING", "C11–C16"],
        ]
        write(folder / "13_final_exam_readiness.md", "# " + ("Eksamensberedskap", "Final-exam readiness")[li] + "\n\n" + mdtable((["Kontrollpunkt", "Status", "Evidens"], ["Check", "Status", "Evidence"])[li], readiness_rows) + "\n" + (
            "Ikke klar for endelig innlevering. Teknisk rapportskriving kan starte fra denne pakken, men obligatoriske krav kan ikke godkjennes uten støttende evidens. Den lokale oppgaveteksten nevner ikke de fire navngitte feilklassene eller åtte-møterskravet. Disse er eksplisitte brukerkrav og åpne offisielle avklaringer, ikke gjetning fra assistenten. Fjerning av en injisert feil er ikke en kodereparasjon; et observert driftsproblem er ikke et planlagt stressforsøk.",
            "Not ready for final submission. Technical report writing can start from this package, but mandatory requirements cannot be signed off without evidence. The local assignment does not specify the four named fault classes or the eight-meeting requirement. These are explicit user requirements pending official clarification, not assistant-invented rubric items. Removing an injected fault is not a code repair; an observed operational problem is not a planned stress experiment.")[li])
        write(folder / "14_risks_schedule.md", "# " + ("Risiko og baklengs fremdriftsmal", "Risks and backwards schedule template")[li] + "\n\n" + (
            "Risikovurderingen er kvalitativ, ikke en målt sannsynlighetsmodell. Viktige risikoer er historisk HTML/personvern, utløpt kildegrunnlag, irrelevant men korrekt sitat, promptinjeksjon, kaldstart/timeout, termisk belastning, manglende global nødstopp og ufullstendig rapportproveniens. Tiltak: sperret HTML-innhenting, faktiske kildevurderinger, eksplisitte avslag, uavhengig menneskelig kontroll, små temperaturbegrensede forsøk og separat godkjenning av appreparasjoner.\n\nDemonstrasjonsdato D er IKKE OPPGITT. Foreslåtte relative milepæler, ikke historiske hendelser: D−21: bekreft krav og datagrense; D−14: gjennomgå sikkerhetsmangler og godkjenn eventuelle reparasjoner; D−7: frys kode, kjør regresjon og ferdigstill analyse; D−3: bygg rapport/vedlegg og øv demonstrasjon; D−1: kontroller lokal drift og gyldige kilder; D: demonstrer. Studentene må bekrefte datoer og ansvar. Ingen kildeutløp erstattes med D.",
            "The risk assessment is qualitative, not a measured probability model. Key risks include historical HTML/privacy handling, expired source evidence, irrelevant but exact quotations, prompt injection, cold starts/timeouts, thermal load, missing global cancellation and incomplete report provenance. Mitigations include blocked HTML acquisition, genuine source review, explicit refusals, independent human assessment, small thermally bounded experiments and separate approval of application repairs.\n\nDemonstration date D is NOT PROVIDED. Suggested relative milestones, not historical events: D−21: confirm requirements and data boundary; D−14: review safety gaps and authorize any repairs; D−7: freeze code, run regression and finalize analysis; D−3: compile report/appendices and rehearse; D−1: check local operation and source validity; D: demonstrate. Students must confirm dates and responsibilities. Source expiry is not replaced by D.")[li])
        write(folder / "15_reproduction.md", "# " + ("Reproduksjon og kjørelogg", "Reproduction and execution record")[li] + "\n\n" + (
            "Kjør fra repo-roten med samme commit og Python-miljø. Alle tidligere kommandoer, UTC-tider, utfall og saniterte råutdata finnes i ../logger/kommandoer.jsonl. Reelle tester krever eksisterende godkjent lokal katalog og installert modell. Godkjenning skal ikke forlenges for å få en test til å kjøre. Ingen rå HTML hentes.\n\n",
            "Run from the repository root using the same commit and Python environment. Exact recorded commands, UTC times, outcomes and sanitized raw output are in ../logger/kommandoer.jsonl. Real tests require the existing approved local catalog and installed model. Approval must not be extended merely to make a test run. No raw HTML is retrieved.\n\n")[li] + "```powershell\npython -X utf8 resultat/run_experiments.py offline\npython -X utf8 resultat/run_experiments.py faults\npython -X utf8 resultat/run_experiments.py gates\npython -X utf8 resultat/run_experiments.py stress\npython -X utf8 resultat/run_experiments.py real\npython -X utf8 resultat/run_experiments.py browser\npython -X utf8 resultat/build_package.py\npython -X utf8 resultat/publish_bilingual.py\n```\n\n" + (
            "Kommandoene er de faktiske inngangspunktene, men eksisterende utdata opprettes eksklusivt. For ny kjøring må en separat forsøkskopi med tom resultatmappe brukes; ikke slett eller overskriv evidens. Testverktøyet starter egne loopback-servere på ledige porter og lar port 8000 være urørt. Chrome-profilen opprettes midlertidig og beholdes ikke. Diagrammer bygges med allerede tilgjengelig matplotlib. Git-kloning alene gir ikke den ignorerte katalogen; lovlig overføring og gyldighet må avklares.\n\nHistoriske resultater og metodeforbehold gjenbrukes fra docs/reports/verified-results-2026-10-23.md, evidence-2026-10-23.json og verify_evidence.py. De 43 gamle filene ble hashkontrollert uten nye historiske eksperimenter.",
            "These are the actual entry points, but output creation is exclusive. A new run requires a separate experimental checkout with an empty results directory; do not delete or overwrite evidence. Test tools create private loopback servers on available ports and leave port 8000 untouched. The Chrome profile is temporary and is not retained. Plots use the already available matplotlib installation. A Git clone alone does not provide the ignored catalog; lawful transfer and validity must be resolved.\n\nHistorical results and methodological caveats are reused from docs/reports/verified-results-2026-10-23.md, evidence-2026-10-23.json and verify_evidence.py. The 43 older files were hash-checked without repeating historical experiments.")[li])
        write(folder / "16_experiment_protocol.md", "# " + ("Forsøksprotokoll og endringsgrense", "Experimental protocol and change boundary")[li] + "\n\n" + (
            "Forsøkene ble valgt etter gjennomgang av faktisk tilgjengelig oppgavetekst, eksisterende harness, syntetiske fixtures, promptlogg, beslutningsnotater og tidligere rapportpakke. Selvvalgte tillegg er kausal gjenoppretting, samtidige negative HTTP-kontroller, faktiske tokenmålinger, budsjettgrenser og kontroll av forskjellen mellom tilstandsreset og beregningsavbrytelse. De presenteres ikke som ordrette undervisningskrav.\n\nFor hvert F-tilfelle er hypotese, baseline, perturbasjon, forventning, observasjon, kallantall, gjenoppretting og begrensning bevart i ../logger/fault-injection.json og 06. Ingen appfunksjonalitet ble endret. Eksisterende korreksjon er testet; nye globale kontroller krever egen godkjenning. Sikkerhetsprøver brukte bare syntetisk data. Ingen utenforstående fikk tilgang; ingen tunnel, commit eller push ble utført.",
            "Experiments were selected after inspecting the actually available assignment text, existing harnesses, synthetic fixtures, prompt log, decision notes and previous evidence package. Researcher-selected additions comprise causal recovery, concurrent negative HTTP controls, actual token measurements, budget boundaries and the distinction between state reset and computation cancellation. They are not presented as verbatim teaching requirements.\n\nFor each F case, hypothesis, baseline, perturbation, expectation, observation, call count, recovery and limitations are preserved in ../logger/fault-injection.json and 06. Application functionality was not changed. Existing correction was tested; new global controls require separate authorization. Safety probes used synthetic data only. No external party received access; no tunnel, commit or push was performed.")[li])
        # These are genuine quotations from the current recorded interaction, not invented history.
        excerpts = [
            "Do not invent measurements or claim a test was performed when it was not.",
            "Do not equate a 100% test pass rate with 100% factual accuracy or complete real-world reliability.",
            "Do not modify application functionality without separate approval.",
            "Do not fabricate missing results or survey responses.",
        ]
        write(folder / "17_prompt_excerpts.md", "# " + ("Representative saniterte promptutdrag", "Representative sanitized prompt excerpts")[li] + "\n\n" + (
            "Utdragene nedenfor er faktiske brukerformuleringer fra denne oppgaven, gjengitt uten identifikatorer. Originalspråket beholdes av hensyn til sitatnøyaktighet. De dokumenterer evalueringsoppgaven, ikke alle tidligere utviklingsinteraksjoner. Sammendrag av tidligere implementasjonsdialog finnes i docs/prompt-log.md og beslutningsnotatene. Ingen oppdiktet møtedialog eller skjult resonnering er lagt til.\n\n",
            "The excerpts below are actual user instructions from this task, reproduced without identifiers. The original language is retained for quotation fidelity. They document the evaluation task, not all earlier development interactions. Earlier implementation interactions are summarized in docs/prompt-log.md and decision notes. No invented meeting dialogue or hidden reasoning was added.\n\n")[li] + "\n\n".join("> " + e for e in excerpts) + "\n\n" + (
            "Utfall: lokale kontrollerte forsøk og en tospråklig evidenspakke, med reelle sikkerhetsmangler bevart som åpne. Studentene må velge representative utviklingsutdrag og kontrollere to-sidersgrensen i faktisk PDF. Denne Markdown-filen dokumenterer ikke ferdig sideantall.",
            "Outcome: controlled local experiments and a bilingual evidence package, retaining genuine safety gaps as unresolved. Students must select representative development excerpts and verify the two-page limit in the actual PDF. This Markdown file does not establish the final page count.")[li])
        write(folder / "18_meeting_confirmation_template.md", "# " + ("Mal for bekreftelse av genuine møter", "Template for confirming genuine meetings")[li] + "\n\n" + (
            "TOM MAL — IKKE MØTEREFERAT. Bruk bare for en faktisk hendelse. Registrer dato, formål, deltakerroller uten personidentifikatorer, vurderte alternativer, begrunnet beslutning, kobling til kode/test, hva som ble revidert og hvordan deltakerne bekrefter at møtet fant sted. Ikke lag åtte kopier som om de dokumenterte åtte møter. Ved åtte-møterskravet må åtte faktiske hendelser kunne etterprøves.",
            "EMPTY TEMPLATE — NOT MEETING MINUTES. Use only for an actual event. Record the date, purpose, participant roles without identifiers, alternatives considered, justified decision, code/test references, revisions and how participants confirm the meeting occurred. Do not make eight copies and present them as eight meetings. The eight-meeting requirement needs evidence of eight actual events.")[li])
        # Figures are translations of the same arrays; no second dataset or run.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        values = [[r["wall_ms"] for r in model["rows"] if r["batch"] == b] for b in ("sequential", "concurrency-2")]
        fig, ax = plt.subplots(figsize=(7, 4))
        for i, group in enumerate(values, 1):
            ax.scatter([i] * len(group), group, alpha=.7)
            ax.plot([i - .18, i + .18], [statistics.median(group)] * 2, color="black")
        ax.set_xticks([1, 2], [("Sekvensielt (n=12)", "Sequential (n=12)")[li], ("Samtidighet 2 (n=2)", "Concurrency 2 (n=2)")[li]])
        ax.set_ylabel(("Portalresponstid (ms)", "Portal response time (ms)")[li])
        ax.set_title(("Reelle modellkall; temperaturavbrutt utvalg", "Real model calls; thermally curtailed sample")[li])
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(folder / f"figurer/01_model_response_times.{ext}", dpi=160)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 4))
        for phase in ("baseline", "perturbation", "recovery"):
            group = sorted(r["wall_ms"] for r in stress["rows"] if r["phase"] == phase)
            ax.plot(group, [(i + 1) / len(group) for i in range(len(group))], label=stage_names[phase][li] + f" (n={len(group)})")
        ax.set_xlabel(("HTTP-søkeresponstid (ms)", "HTTP search response time (ms)")[li])
        ax.set_ylabel(("Empirisk kumulativ andel", "Empirical cumulative proportion")[li])
        ax.set_title(("Syntetisk HTTP-belastning; 8 arbeidere; ingen modell", "Synthetic HTTP load; 8 workers; no model")[li])
        ax.legend(); ax.grid(alpha=.2); fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(folder / f"figurer/02_http_latency_distribution.{ext}", dpi=160)
        plt.close(fig)
        diagram = (BASE / "figurer/03_arbeidsflyt.mmd").read_text(encoding="utf-8")
        if li:
            replacements = {"Bruker: generelt tjenestespørsmål": "User: general service question", "Personvern og temaavgrensning": "Privacy and topic constraints", "Lokal godkjent katalog: søk og gyldighet": "Approved local catalog: retrieval and validity", "Tilstrekkelig kildegrunnlag?": "Sufficient source evidence?", "Avslag og offisiell veiledning": "Refusal and official guidance", "Ollama velger helt godkjent avsnitt": "Ollama selects complete approved paragraph", "Verifikasjon og eksakt avsnittssamsvar": "Verification and exact paragraph match", "Funn?": "Findings?", "Svar med offisiell kilde": "Answer with official source", "Høyst én korreksjon": "At most one correction", "Obligatorisk ny verifikasjon": "Mandatory re-verification", "Uløst eller feil": "Unresolved or failed", "Ingen funn": "No findings", "Menneskelig kildevurdering: før opptak": "Human source review before admission", "Levende HTML-innhenting sperret": "Live HTML acquisition blocked", "|Nei|": "|No|", "|Ja|": "|Yes|"}
            for before, after in replacements.items():
                diagram = diagram.replace(before, after)
        write(folder / "figurer/03_workflow.mmd", diagram)
        figure_data = {"model_groups_ms": values, "http_groups_ms": {p: sorted(r["wall_ms"] for r in stress["rows"] if r["phase"] == p) for p in stress["phases"]}}
        write(folder / "figurer/data.json", json.dumps(figure_data, indent=2))

    # Machine-check numerical payload, every measurement cell and every figure input.
    assert numeric_payloads["norsk"] == numeric_payloads["english"]
    for name in ("02_test_results.csv", "04_response_times.csv", "19_token_usage.csv"):
        no = list(csv.reader((BASE / "norsk" / name).open(encoding="utf-8", newline="")))[1:]
        en = list(csv.reader((BASE / "english" / name).open(encoding="utf-8", newline="")))[1:]
        # Result descriptions translate; all other cells must match exactly.
        if name == "02_test_results.csv":
            assert [r[:-1] for r in no] == [r[:-1] for r in en]
        else:
            assert no == en
    assert read("norsk/figurer/data.json") == read("english/figurer/data.json")
    # Captions use identical numeric tokens and the same data references.
    for pair in captions.values():
        assert re.findall(r"\d+(?:\.\d+)?", pair[0]) == re.findall(r"\d+(?:\.\d+)?", pair[1])
    write(BASE / "logger/bilingual-consistency.json", json.dumps({
        "date": datetime.now(timezone.utc).isoformat(), "pass": True,
        "shared_data_sha256": hashlib.sha256((BASE / "data/shared.json").read_bytes()).hexdigest(),
        "same_numeric_payload": True, "same_measurement_cells_and_references": True,
        "same_figure_input_arrays": True, "same_caption_numbers": True,
        "limitations": "Human review of translation is still recommended; equality is not factual validity"}, indent=2))
    write(BASE / "00_LES_MEG.md", (BASE / "norsk/00_READ_ME.md").read_text(encoding="utf-8").replace("../data/shared.json", "data/shared.json") + "\n\nSpråkversjoner: norsk/ og english/. Komplett filoversikt: FILOVERSIKT.md. Rålogger og SHA-manifest følger pakken.\n")
    # Preserve the requested Norwegian entry points without changing existing matrices/CSVs.
    aliases = {
        "03_evaluering_og_malemetode.md": "03_methodology.md", "05_kildekontroll_og_personvern.md": "05_sources_privacy_security.md",
        "06_stresstesting_og_feilanalyse.md": "06_stress_failures_regression.md", "07_brukertest_og_sporreundersokelse.md": "07_user_survey.md",
        "08_arkitektur_og_arbeidsflyt.md": "08_architecture.md", "09_codex_endringer_og_motereferater.md": "09_agent_changes_meetings.md",
        "10_figurer_og_tabeller.md": "10_figures_and_tables.md", "11_begrensninger_og_refleksjon.md": "11_limitations.md",
        "12_kravdekning_og_mangelliste.md": "12_coverage_gaps.md", "13_eksamensberedskap.md": "13_final_exam_readiness.md",
        "14_risiko_og_fremdrift.md": "14_risks_schedule.md", "15_reproduksjon_og_kjorelogg.md": "15_reproduction.md",
        "16_forsoksprotokoll.md": "16_experiment_protocol.md", "17_representative_promptutdrag.md": "17_prompt_excerpts.md",
        "18_referater_bekreftelsesmal.md": "18_meeting_confirmation_template.md"}
    for target, source in aliases.items():
        write(BASE / target, f"# Norsk rapportgrunnlag\n\nDen fullstendige norske teksten finnes i [norsk/{source}](norsk/{source}). Tilsvarende engelsk tekst finnes i [english/{source}](english/{source}). Begge bruker data/shared.json.\n")
    inventory = sorted(p.relative_to(BASE).as_posix() for p in BASE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    write(BASE / "FILOVERSIKT.md", "# Komplett filoversikt\n\n" + "\n".join("- `" + name + "`" for name in inventory) + "\n- `FILOVERSIKT.md`\n- `logger/pakke-manifest.json`\n")
    manifest = [{"path": p.relative_to(BASE).as_posix(), "bytes": p.stat().st_size,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(BASE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    write(BASE / "logger/pakke-manifest.json", json.dumps({"date": datetime.now(timezone.utc).isoformat(), "files": manifest}, indent=2))
    print("Bilingual package published; identical measurements and figure arrays verified.")


if __name__ == "__main__":
    main()
