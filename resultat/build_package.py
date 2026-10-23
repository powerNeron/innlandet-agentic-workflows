"""Lag norske rapporttabeller og figurer fra bevarte logger; ingen modellkall.

python -X utf8 resultat/build_package.py
Alle opprettelser er eksklusive. Ikke overskriv tidligere forsok.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "resultat"
LOG = DEST / "logger"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, text):
    with (DEST / path).open("x", encoding="utf-8") as stream:
        stream.write(text.rstrip() + "\n")


def json_file(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2))


def table(path, columns, rows):
    with (DEST / path).open("x", encoding="utf-8", newline="") as stream:
        out = csv.DictWriter(stream, fieldnames=columns)
        out.writeheader(); out.writerows(rows)


def main():
    fault = load(LOG / "fault-injection.json")
    gates = load(LOG / "approval-gates.json")
    model = load(LOG / "model-measurements.json")
    smoke = load(LOG / "real-smoke/summary.json")
    stress = load(LOG / "http-stress.json")
    browser = (LOG / "browser/browser-check.txt").read_text(encoding="utf-8")
    assert load(LOG / "browser-run.json")["exit_code"] == 0
    assert "HTTP_FAILURES []" in browser and '"console_errors":[]' in browser
    browser_summary = json.loads(next(x for x in browser.splitlines() if x.startswith('{"title":')))
    browser_questions = json.loads(next(x.split(" ", 1)[1] for x in browser.splitlines() if x.startswith("REQUIRED_AI_QUESTIONS ")))
    old = load(ROOT / "docs/reports/evidence-2026-10-23.json")
    checked = []
    for name, meta in old["artifacts"].items():
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert digest == meta["sha256"], name
        checked.append({"path": name, "sha256": digest, "unchanged": True})
    json_file("logger/historisk-hashkontroll.json", {"date": datetime.now(timezone.utc).isoformat(),
              "reused": "docs/reports/evidence-2026-10-23.json", "artifacts": checked})
    # Capture source and code integrity without copying personal author metadata.
    protected = [*sorted((ROOT / "hamar_agent").rglob("*.py")),
                 *sorted((ROOT / "hamar_agent/web_assets").glob("*")),
                 ROOT / "docs/approved-service-pages.json", ROOT / "docs/reviewed-service-selection.json"]
    json_file("logger/kode-og-kildeintegritet.json", {"files": [
        {"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in protected if p.is_file()], "approved_catalog_unchanged": True,
        "baseline_catalog_hash": old["artifacts"]["output/municipal-catalog.json"]["sha256"]})
    git = ["git", "-c", "safe.directory=" + ROOT.as_posix()]
    commit = subprocess.check_output([*git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert not subprocess.check_output([*git, "diff", "--name-only"], cwd=ROOT, text=True).strip()
    json_file("logger/miljo.json", {"date": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "os": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "commit": commit, "ollama": model["ollama_version"],
        "model": model["model"], "new_dependencies_installed": False,
        "no_application_changes": True, "no_source_changes": True})
    offline = (LOG / "offline.txt").read_text(encoding="utf-8")
    total, seconds = re.search(r"Ran (\d+) tests in ([\d.]+)s", offline).groups()
    assert offline.rstrip().endswith("OK")
    total = int(total)
    results = []
    def result(identifier, category, count, passed, meaning, log):
        results.append(dict(id=identifier, type=category, dato="2026-10-23", antall=count,
                            bestatt=passed, ikke_bestatt=count - passed, tolkning=meaning, logg=log))
    result("O1", "offline", total, total, "Regresjon; ikke modellkvalitet", "logger/offline.txt")
    result("O2", "syntetisk_holdout", 1, int(load(LOG / "holdout.json")["passed"]), "Ett kjent separat lagret mock-tilfelle", "logger/holdout.json")
    score = load(LOG / "verifier-scorecard.json")
    result("O3", "syntetisk_verifier", 8, sum(x["detected"] for x in score["cases"]), "Forventede funnkoder; ikke semantisk sannhet", "logger/verifier-scorecard.json")
    result("M1", "reell_modell", smoke["tests"], smoke["passing"], "18 positive tilfeller og fem tilsiktede avslag", "logger/real-smoke/summary.json")
    result("M2", "reell_maling", model["completed"], sum(x["pass"] for x in model["rows"]), "Temperaturstopp; planlagt 20, ikke fullfort", "logger/model-measurements.json")
    result("F", "syntetisk_feilinjeksjon", len(fault["cases"]), sum(x["pass"] for x in fault["cases"]), "Baseline-feil-gjenoppretting / eksisterende korreksjon", "logger/fault-injection.json")
    result("P", "grensekontroller", len(fault["control_cases"]), sum(x["pass"] for x in fault["control_cases"]), "Tillatelser og promptgrense", "logger/fault-injection.json")
    result("G", "godkjenningsporter", len(gates["cases"]), sum(x["pass"] for x in gates["cases"]), "Flagg og sjekklister; ikke identitetsautentisering", "logger/approval-gates.json")
    result("S", "syntetisk_http_belastning", len(stress["rows"]), sum(x["pass"] for x in stress["rows"]), "Inkluderer 16 forventede HTTP403; ingen modellkall", "logger/http-stress.json")
    result("B", "ekte_Chrome", len(browser_questions), sum(x["http_status"] == 200 for x in browser_questions), "Forventede svar og avslag; desktop/nettbrett/mobil", "logger/browser/browser-check.txt")
    result("KILL", "negativ_sikkerhetsprobe", 1, 0, "Global beregningsavbrytelse mangler; reset gir409", "logger/fault-injection.json")
    result("SEM", "semantisk_moteksempel", 1, 0, "Ordrett instruksjonsavsnitt passerer; ikke semantisk immunitet", "logger/fault-injection.json")
    table("02_testresultater.csv", list(results[0]), results)
    latencies = []
    for row in model["rows"]:
        latencies.append({"forsok": "M2", "case": row["index"], "gruppe": row["batch"], "enhet": "ms",
                          "verdi": row["wall_ms"], "omfang": "portal.wall", "logg": "logger/model-measurements.json"})
    for row in smoke["rows"]:
        if row.get("provider_latency_ms") is not None:
            latencies.append({"forsok": "M1", "case": row["case"], "gruppe": "sekvensiell", "enhet": "ms",
                              "verdi": row["provider_latency_ms"], "omfang": "workflow", "logg": "logger/real-smoke/summary.json"})
    for row in stress["rows"]:
        latencies.append({"forsok": "S", "case": row["index"], "gruppe": row["phase"], "enhet": "ms",
                          "verdi": row["wall_ms"], "omfang": "HTTP.search", "logg": "logger/http-stress.json"})
    table("04_ytelse_og_responstider.csv", list(latencies[0]), latencies)
    tokens = []
    for index, row in enumerate(model["model_call_metrics"], 1):
        tokens.append({"fullforingsrekkefolge": index,
                       **{k: row.get(k, "") for k in ("prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration", "load_duration", "total_duration", "requested_output_limit", "done_reason")}})
    table("19_tokenbruk.csv", list(tokens[0]), tokens)
    # Requirements are atomic; evidence readiness is separate from a submitted PDF.
    reqs = []
    def req(identifier, scope, location, description, needed, existing, collected, method, status, action):
        reqs.append(dict(id=identifier, omfang=scope, plassering=location, krav=description, evidensbehov=needed,
                         eksisterende=existing, ny_evidens=collected, metode=method, status=status, neste_handling=action))
    authority = "docs/official-assignment-user-supplied.md"
    req("A01", "felles", "Abstract; §1", "Tilbakevendende behov i Innlandet", "Problem og mottakere", "README; SPEC", "08_arkitektur_og_arbeidsflyt.md", "Dokumentanalyse", "VERIFIED", "Studentene vurderer formuleringen")
    req("A02", "felles", "Abstract", "Arbeid i par", "Ekte samarbeid og ansvar", "Eierskapsnotater", "09_codex_endringer_og_motereferater.md", "Dokumentanalyse; ingen persondata", "PARTIAL", "Studentene bekrefter bidrag og samarbeid")
    req("A03", "felles", "§1 Constraints", "Ingen identifiserende persondata behandles", "Datagrense og faktisk etterlevelse", "Historisk HTML-behandling; kildepolicy", "F/P/G; 05_kildekontroll_og_personvern.md", "Feilinjeksjon og kildeanalyse", "PARTIAL", "Avklar historisk HTML og institusjonell personverngodkjenning")
    req("A04", "felles", "§1 Constraints", "Respekter kilder; begrens republisering", "Eksakte URL-er og innhentingsgrenser", "Manifester; robots-tester", "Integritetskontroll; O1", "Hasher og offline-tester", "VERIFIED", "Ingen ny innhenting; reell vurdering ved utløp")
    req("A05", "felles", "§1 Constraints", "Norsk lokalkontekst og offisielle institusjoner", "Kildelenker og lokalt relevante svar", "Åtte Hamar-kilder", "M1; B", "Reell modell og nettleser", "VERIFIED", "Menneskelig relevansvurdering anbefales")
    for identifier, desc, evidence in (("T01", "Input og kontrollerbart output", "O1; M1; O3"),
                                       ("T02", "Mer enn ett trinn", "F01-F11; 08"),
                                       ("T03", "Verktøy/filer/eksterne data", "M1; lokal fil og Ollama HTTP"),
                                       ("T04", "Minst ett automatisk ledd", "M1; B; CLI/harness")):
        req(identifier, "Compulsory 2", "§2 Technical minimum", desc, "Kjørbar observerbar sti", "Implementert pipeline", evidence, "Eksisterende harness og kausal feilinjeksjon", "VERIFIED", "Bevar begrensningene i rapporten")
    req("C01", "Compulsory 2", "§2 Submission", "Både rapport og walking skeleton", "Ferdig rapport og kjørbar kode", "Skeleton kjører; ingen innleverings-PDF", "M1; B; rapportgrunnlag", "Artefaktsjekk", "PARTIAL", "Skriv og bygg innleveringsrapport")
    for identifier, desc, evidence in (("C02", "Problem, behov, målgruppe og output", "08"),
                                      ("C03", "Suksess og kontroll av korrekthet", "03; 02; 05"),
                                      ("C04", "Arkitektur, kontekst, trinn og automatisering", "08; figurer/03_arbeidsflyt.mmd"),
                                      ("C06", "Risikovurdering og tiltak", "14_risiko_og_fremdrift.md"),
                                      ("C07", "Repository-lenke i rapporten", "00_LES_MEG.md")):
        req(identifier, "Compulsory 2", "§2 The report", desc, "Innhold i faktisk innlevering", "README; SPEC; docs", evidence, "Dokumentutkast; ingen PDF", "PARTIAL", "Overfør verifisert innhold til engelsk rapport")
    req("C05", "Compulsory 2", "§2 The report: schedule", "Baklengs milepæler fra demonstrasjonsdato", "Bekreftet D-dato og plan", "Dato ikke funnet", "14: relativ D-plan som mal", "Ingen dato oppfunnet", "PARTIAL", "Oppgi dato og godkjenn milepæler")
    req("C08", "Compulsory 2", "§2 Walking skeleton", "En ende-til-ende-sti", "Reelt input til etterprøvbart output", "Forrige verifiserte resultater", "M1; B; JSON", "Faktisk lokal modell og Chrome", "VERIFIED", "Ingen")
    req("C09", "Compulsory 2", "§2 Walking skeleton", "README muliggjør reproduksjon", "Alle nødvendige inndata tilgjengelige", "README; lokal ignorert katalog", "15_reproduksjon_og_kjorelogg.md", "Ny lokal kjøring", "PARTIAL", "Avtal lovlig overføring av katalog; test fra ren kopi")
    req("C10", "Compulsory 2", "§2 Walking skeleton", "Kontekstfiler i repo", "Instruksjoner og fixtures", "AGENTS; SPEC; fixtures", "Inventar og filhasher", "Filkontroll", "VERIFIED", "Ingen")
    req("C11", "Compulsory 2", "§2 Report format", "Utdelt LaTeX-mal", "Original mal og rapportkilde", "Ikke funnet", "Mangelliste", "rg --files", "MISSING", "Tilgjengeliggjør utdelt mal")
    req("C12", "Compulsory 2", "§2 Report format", "NeurIPS preprint; fjern checklist", "Kilde og bygget PDF", "Ingen rapportkilde", "Ingen", "Artefaktsjekk", "MISSING", "Bruk neurips_2025 med preprint; kontroller PDF")
    req("C13", "Compulsory 2", "§2 Report format", "3–4 sider hovedtekst", "Kompilert rapport og sidetall", "Ingen PDF", "Ingen", "Artefaktsjekk", "MISSING", "Bygg og kontroller sider ekskl. vedlegg/referanser")
    req("C14", "Compulsory 2", "§2 Report format", "Rapport på engelsk", "Ferdig engelsk hovedtekst", "Tekniske engelske notater", "Norsk evidenspakke", "Dokumentanalyse", "MISSING", "Skriv engelsk innleveringsrapport")
    req("C15", "Compulsory 2", "§2 Appendices", "Vedlegg inkludert", "Ferdig vedlegg", "Spredte docs", "17 og møteinventar", "Artefaktsjekk", "PARTIAL", "Sett sammen og bygg vedlegg")
    req("C16", "Compulsory 2", "§2 Appendices", "Representative promptutdrag, maks to sider", "Faktiske utdrag og sidetall", "docs/prompt-log.md: sammendrag", "17_representative_promptutdrag.md", "Saniterte reelle dialogutdrag", "PARTIAL", "Velg utdrag og kontroller maks to PDF-sider")
    req("C17", "Compulsory 2", "§2 Appendices", "Møter viser iterativ resonnering og revisjon", "Ekte hendelser bekreftet av deltakerne", "Åtte kandidatnotater", "09 og 18; ingen møter oppfunnet", "Innholdssjekk uten personnavn", "PARTIAL", "Bekreft hvilke dokumenter som gjelder faktiske møter")
    req("A06", "felles", "Abstract", "Systematisk testing, stress og validering før demo", "Kjøringer og demonstrasjonsbekreftelse", "Historiske målinger", "O1; M1; F/P/G; S; B; M2 delvis", "Ny kontrollert forsøksserie", "PARTIAL", "Bekreft demonstrasjon; fullfør temperaturtrygg plan om nødvendig")
    req("E01", "sluttartikkel", "Full offisiell sluttoppgave mangler", "Sluttartikkelens vurderingskriterier", "Komplett autoritativ tekst", "Lokal fil stopper etter Compulsory 2", "13_eksamensberedskap.md", "Kildesøk og eksplisitt spørsmål", "MISSING", "Oppgi full offisiell sluttoppgave")
    req("E02", "sluttartikkel", "Brukerens tillegg; offisiell klasseoversikt mangler", "Minst to av fire navngitte feilklasser med feil, årsak, reparasjon og regresjon", "Klassenavn og komplette forsøkskjeder", "Historiske feil og reparasjonsnotater", "F01-F11 og kausal analyse i 06", "Baseline/perturbasjon/gjenoppretting; ingen ny appreparasjon", "PARTIAL", "Koble til offisielle klasser og avklar reparasjonskrav; godkjenn nødvendige appendringer separat")
    req("E03", "sluttartikkel", "Brukerens tillegg", "Global kill switch håndheves", "Pågående arbeid stoppes", "AbortController/reset i UI", "Negativ KILL-probe", "Trådbarriere viser videre beregning", "MISSING", "Godkjenn separat design og implementering av reell nødstopp")
    req("E04", "sluttartikkel", "Brukerens tillegg", "Token- og kostnadsbudsjetter håndheves", "Per-kall og aggregert budsjett", "700 ut-token; maks to kall", "F05/F06; B24000/B24001; målte token", "Grensetester og transportinstrumentering", "PARTIAL", "Godkjenn globalt øktbudsjett; mål kostnad/energi hvis relevant")
    req("E05", "sluttartikkel", "Brukerens tillegg", "Tillatelser og menneskelige porter håndheves", "Avslag på forbudte handlinger", "Loopback/allowlist; selverklærte roller", "P01-P08; G15; O1", "Negative kontrolltilfeller", "PARTIAL", "Avklar autentisering av reell godkjenner; OS-kontroller er ikke en appport")
    req("E06", "sluttartikkel", "Brukerens tillegg; ikke i lokal §2", "Minst åtte genuine møtereferater", "Åtte faktiske møter med bekreftede beslutninger", "Åtte md-filer i docs/meetings", "09: åtte kandidater, ingen bekreftet som møte", "Proveniens- og innholdskontroll", "PARTIAL", "Studentene dokumenterer åtte reelle hendelser; ikke tilbakedater eller oppfinn")
    req("E07", "sluttartikkel", "Brukerens tillegg", "Representativ Codex-logg", "Reelle representative interaksjoner", "Promptlogg og beslutningsnotater", "17", "Eksakte saniterte dialogutdrag", "PARTIAL", "Studentene velger og bekrefter representativitet")
    req("W40", "undervisningskontekst", "W40_KIUA_2003 ikke funnet", "Sammenhold med faktisk W40-materiale", "Original undervisningsfil", "Ingen lokal fil", "Eksplisitt mangelliste", "Prosjektlokalt filsøk", "MISSING", "Oppgi filsti; ingen eksterne kriterier gjettes")
    req("U01", "tilleggsanbefaling", "Frivillig survey i brukeroppgaven", "Brukervurdering", "Anonyme frivillige svar", "Ingen respondenter", "07 og tom svarmal", "Spørreskjema er forberedt, ikke gjennomført", "PARTIAL", "Studentene gjennomfører frivillig og godkjent undersøkelse")
    table("kravmatrise.csv", list(reqs[0]), reqs)
    statuses = {s: sum(r["status"] == s for r in reqs) for s in ("VERIFIED", "PARTIAL", "MISSING", "NOT APPLICABLE")}
    json_file("logger/dekning.json", {"counts": statuses, "total": len(reqs), "requirements": reqs,
              "not_a_grade_or_official_percentage": True, "final_submission_ready": False})
    text = "# Oppgavekrav og sporbar sjekkliste\n\nAutoritet: [lokal brukerbekreftet oppgavetekst](../docs/official-assignment-user-supplied.md). Teksten slutter etter §2. Den inneholder ikke sluttartikkelens fire feilklasser, et åtte-møterskrav eller W40-materialet. E-kravene nedenfor er derfor brukerens tillegg, ikke påståtte sitater fra manglende offisiell tekst.\n\nVERIFIED betyr at angitt avgrenset krav har evidens; PARTIAL at vesentlige deler mangler; MISSING at nødvendig evidens eller kontroll ikke finnes. Ingen vekting eller karakterprosent utledes. Full tabell finnes også i [CSV](kravmatrise.csv).\n\n"
    text += "| ID / omfang | Krav og plassering | Nødvendig evidens | Eksisterende / samlet nå | Metode | Status | Neste handling |\n|---|---|---|---|---|---|---|\n"
    for r in reqs:
        text += f"| {r['id']} / {r['omfang']} | {r['krav']} — {r['plassering']} | {r['evidensbehov']} | {r['eksisterende']} / {r['ny_evidens']} | {r['metode']} | {r['status']} | {r['neste_handling']} |\n"
    write("01_oppgavekrav_og_sjekkliste.md", text)
    summary = {"commit": commit, "offline": {"n": total, "passed": total, "seconds": float(seconds)},
               "model": {"smoke_tests": smoke["tests"], "smoke_passed": smoke["passing"],
                         "measurements_completed": model["completed"], "measurements_planned": 20,
                         "input_tokens": sum(x.get("prompt_eval_count", 0) for x in model["model_call_metrics"]),
                         "output_tokens": sum(x.get("eval_count", 0) for x in model["model_call_metrics"]),
                         "stop": model["stopped_reason"], "latency_by_batch": model["latency_by_batch"]},
               "faults": {"n": len(fault["cases"]), "passed": sum(x["pass"] for x in fault["cases"])},
               "controls": {"n": 10, "passed": 10}, "gates": {"n": 15, "passed": 15},
               "http": {"n": 384, "expected_outcomes": sum(x["pass"] for x in stress["rows"]), "phases": stress["phases"]},
               "browser": browser_summary, "coverage": statuses}
    json_file("logger/oppsummering.json", summary)
    # Standard scientific plotting; no synthesized or illustrative measurements.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = DEST / "figurer"; figures.mkdir(exist_ok=True)
    groups = ([x["wall_ms"] for x in model["rows"] if x["batch"] == "sequential"],
              [x["wall_ms"] for x in model["rows"] if x["batch"] == "concurrency-2"])
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, data in enumerate(groups, 1):
        ax.scatter([i] * len(data), data, alpha=.7)
        ax.plot([i - .18, i + .18], [statistics.median(data)] * 2, color="black")
    ax.set_xticks([1, 2], [f"Sekvensielt (n={len(groups[0])})", f"Samtidighet 2 (n={len(groups[1])})"])
    ax.set_ylabel("Portalresponstid (ms)")
    ax.set_title("Reelle modellkall; temperaturstopp før fullført plan")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figures / ("01_modellresponstid." + ext), dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, phase in enumerate(("baseline", "perturbation", "recovery"), 1):
        values = sorted(x["wall_ms"] for x in stress["rows"] if x["phase"] == phase)
        ax.plot(values, [(j + 1) / len(values) for j in range(len(values))], label=f"{phase} (n={len(values)})")
    ax.set_xlabel("HTTP-søkeresponstid (ms)"); ax.set_ylabel("Empirisk kumulativ andel")
    ax.set_title("Syntetisk HTTP-belastning; 8 arbeidere; ingen modell")
    ax.legend(); ax.grid(alpha=.2); fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figures / ("02_http_responstidsfordeling." + ext), dpi=160)
    plt.close(fig)
    write("figurer/03_arbeidsflyt.mmd", '''flowchart TD
    A[Bruker: generelt tjenestespørsmål] --> B[Personvern og temaavgrensning]
    B --> C[Lokal godkjent katalog: søk og gyldighet]
    C --> D{Tilstrekkelig kildegrunnlag?}
    D -->|Nei| E[Avslag og offisiell veiledning]
    D -->|Ja| F[Ollama velger helt godkjent avsnitt]
    F --> G[Verifikasjon og eksakt avsnittssamsvar]
    G --> H{Funn?}
    H -->|Nei| I[Svar med offisiell kilde]
    H -->|Ja| J[Høyst én korreksjon]
    J --> K[Obligatorisk ny verifikasjon]
    K -->|Uløst eller feil| E
    K -->|Ingen funn| I
    L[Menneskelig kildevurdering: før opptak] -.-> C
    M[Levende HTML-innhenting sperret] -.-> E
''')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
