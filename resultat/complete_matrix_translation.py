"""Fullstendig kravmatrise pa begge sprak, fra uendrede felles kravposter."""
import csv
from pathlib import Path
from publish_bilingual import EN_REQ, mdtable, csvwrite, write

BASE = Path(__file__).resolve().parent
EXISTING = {
"700 ut-token; maks to kall": "700 output tokens; at most two calls",
"AGENTS; SPEC; fixtures": "AGENTS; SPEC; fixtures",
"AbortController/reset i UI": "AbortController/reset in the UI",
"Dato ikke funnet": "Date not found", "Eierskapsnotater": "Ownership notes",
"Forrige verifiserte resultater": "Previously verified results",
"Historisk HTML-behandling; kildepolicy": "Historical HTML processing; source policy",
"Historiske feil og reparasjonsnotater": "Historical failures and repair notes",
"Historiske målinger": "Historical measurements", "Ikke funnet": "Not found",
"Implementert pipeline": "Implemented pipeline", "Ingen PDF": "No PDF",
"Ingen lokal fil": "No local file", "Ingen rapportkilde": "No report source",
"Ingen respondenter": "No respondents",
"Lokal fil stopper etter Compulsory 2": "Local file ends after Compulsory 2",
"Loopback/allowlist; selverklærte roller": "Loopback/allowlist; self-attested roles",
"Manifester; robots-tester": "Manifests; robots tests",
"Promptlogg og beslutningsnotater": "Prompt log and decision notes",
"README; SPEC": "README; SPEC", "README; SPEC; docs": "README; SPEC; docs",
"README; lokal ignorert katalog": "README; local ignored catalog",
"Skeleton kjører; ingen innleverings-PDF": "Running skeleton; no submission PDF",
"Spredte docs": "Scattered documentation", "Tekniske engelske notater": "Technical notes in English",
"docs/prompt-log.md: sammendrag": "docs/prompt-log.md: summaries",
"Åtte Hamar-kilder": "Eight Hamar sources", "Åtte kandidatnotater": "Eight candidate notes",
"Åtte md-filer i docs/meetings": "Eight md files in docs/meetings",
}
METHOD = {
"Artefaktsjekk": "Artifact inspection",
"Baseline/perturbasjon/gjenoppretting; ingen ny appreparasjon": "Baseline/perturbation/recovery; no new application repair",
"Dokumentanalyse": "Document analysis", "Dokumentanalyse; ingen persondata": "Document analysis; no personal data",
"Dokumentutkast; ingen PDF": "Document draft; no PDF",
"Eksakte saniterte dialogutdrag": "Exact sanitized dialogue excerpts",
"Eksisterende harness og kausal feilinjeksjon": "Existing harness and causal fault injection",
"Faktisk lokal modell og Chrome": "Actual local model and Chrome",
"Feilinjeksjon og kildeanalyse": "Fault injection and source analysis",
"Filkontroll": "File inspection", "Grensetester og transportinstrumentering": "Boundary tests and transport instrumentation",
"Hasher og offline-tester": "Hashes and offline tests", "Ingen dato oppfunnet": "No date invented",
"Innholdssjekk uten personnavn": "Content inspection without personal names",
"Kildesøk og eksplisitt spørsmål": "Source search and explicit clarification request",
"Negative kontrolltilfeller": "Negative control cases", "Ny kontrollert forsøksserie": "New controlled experimental series",
"Ny lokal kjøring": "New local execution", "Prosjektlokalt filsøk": "Project-local file search",
"Proveniens- og innholdskontroll": "Provenance and content inspection",
"Reell modell og nettleser": "Real model and browser", "Saniterte reelle dialogutdrag": "Sanitized actual dialogue excerpts",
"Spørreskjema er forberedt, ikke gjennomført": "Questionnaire prepared, not administered",
"Trådbarriere viser videre beregning": "Thread barrier demonstrates continued computation",
"rg --files": "rg --files",
}
COLLECTED = {
"07 og tom svarmal": "07 and empty response template", "09 og 18; ingen møter oppfunnet": "09 and 18; no meetings invented",
"09: åtte kandidater, ingen bekreftet som møte": "09: eight candidates, none confirmed as a meeting",
"14: relativ D-plan som mal": "14: relative D schedule template", "17 og møteinventar": "17 and meeting inventory",
"Eksplisitt mangelliste": "Explicit missing-evidence list", "F01-F11 og kausal analyse i 06": "F01-F11 and causal analysis in 06",
"F05/F06; B24000/B24001; målte token": "F05/F06; B24000/B24001; measured tokens",
"Ingen": "None", "Integritetskontroll; O1": "Integrity check; O1", "Inventar og filhasher": "Inventory and file hashes",
"M1; B; rapportgrunnlag": "M1; B; report evidence", "M1; lokal fil og Ollama HTTP": "M1; local file and Ollama HTTP",
"Mangelliste": "Missing-evidence list", "Negativ KILL-probe": "Negative KILL probe",
"Norsk evidenspakke": "Norwegian evidence package", "O1; M1; F/P/G; S; B; M2 delvis": "O1; M1; F/P/G; S; B; M2 partial",
}
SCOPE = {"felles": "shared", "Compulsory 2": "Compulsory 2", "sluttartikkel": "final white paper",
         "undervisningskontekst": "teaching context", "tilleggsanbefaling": "additional recommendation"}
LOCATION = {"Full offisiell sluttoppgave mangler": "Complete official final assignment unavailable",
            "Brukerens tillegg; offisiell klasseoversikt mangler": "User supplement; official class list unavailable",
            "Brukerens tillegg": "User supplement", "Brukerens tillegg; ikke i lokal §2": "User supplement; absent from local §2",
            "W40_KIUA_2003 ikke funnet": "W40_KIUA_2003 not found",
            "Frivillig survey i brukeroppgaven": "Voluntary survey in the user task"}


def main():
    with (BASE / "kravmatrise.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    headers_no = ["ID", "Omfang", "Plassering", "Krav", "Evidensbehov", "Eksisterende evidens", "Samlet nå", "Verifikasjonsmetode", "Status", "Neste handling"]
    headers_en = ["ID", "Scope", "Location", "Requirement", "Evidence needed", "Existing evidence", "Collected now", "Verification method", "Status", "Next action"]
    values_no, values_en = [], []
    for row in rows:
        description, needed, action = EN_REQ[row["id"]]
        collected = row["ny_evidens"]
        # File paths and symbolic case references remain exact source references.
        translated = COLLECTED.get(collected, collected)
        values_no.append(list(row.values()))
        values_en.append([row["id"], SCOPE[row["omfang"]], LOCATION.get(row["plassering"], row["plassering"]),
                          description, needed, EXISTING[row["eksisterende"]], translated,
                          METHOD[row["metode"]], row["status"], action])
    for language, headers, values, title, note in (
        ("norsk", headers_no, values_no, "Fullstendig krav- og evidensmatrise",
         "Hver post bruker samme status, kildehenvisninger og tall som felles kravmatrise. Det finnes et avledet W40/W43-notat i output/final-technical-evidence/w40-w43-addendum.json, men ikke originalt undervisningsmateriale. Dette notatet erstatter ikke den manglende autoritative teksten."),
        ("english", headers_en, values_en, "Complete requirements and evidence matrix",
         "Each entry uses the same status, source references and numbers as the shared matrix. A derived W40/W43 note exists at output/final-technical-evidence/w40-w43-addendum.json, but the original teaching material is unavailable. That note does not replace the missing authoritative text.")):
        csvwrite(BASE / language / "01_full_requirements.csv", headers, values)
        write(BASE / language / "01_full_requirements.md", "# " + title + "\n\n" + note + "\n\n" + mdtable(headers, values))
    print("Full bilingual requirement evidence chains written:", len(rows))


if __name__ == "__main__":
    main()
