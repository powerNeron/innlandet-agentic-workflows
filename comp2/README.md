# Compulsory 2 — Aisha Agent

Avgrenset rapportpakke basert på eksisterende, verifisert prosjektevidens. **Ikke innleveringsklar:** levert NeurIPS-mal, kompilert sidetall, bekreftede møtereferater og datofestet fremdriftsplan mangler. Ingen commit/push skal utføres før obligatoriske kontrollpunkter er verifisert.

## Innhold og autoritet

- `report/main.tex`: engelsk rapport med de ti forespurte seksjonene, referanser og vedlegg.
- `report/references.bib`: referanser til faktiske oppgave- og prosjektfiler.
- `tables/english/` og `tables/norwegian/`: identiske målinger fra `evidence/selected-results.json`; CSV, Markdown og kompakt LaTeX-tabell, samt ytelsesoversikt.
- `figures/`: rendret arbeidsflyt, opprinnelig Mermaid, eksisterende engelsk responstidsfigur og tospråklige figurtekster.
- `evidence/`: byteidentiske utvalgte logger, kilde-/kopimanifest, nye kjøre- og kontrollresultater.
- `appendices/`: ekte promptutdrag og eksplisitt status for manglende bekreftet møtedokumentasjon.
- `checklist.md`: krav, rapportsted, implementasjon/evidens og verifikasjonsstatus.
- `build_package.py`: engangsgenerering fra eksisterende evidens, med eksklusiv filoppretting; skal ikke kjøres over eksisterende pakke.
- `verify_package.py`: lesende kontroll av kilder, tospråklige tall og opprinnelig evidens; rapporterer obligatoriske mangler.

Autoritativ oppgavetekst: [docs/official-assignment-user-supplied.md](../docs/official-assignment-user-supplied.md), abstrakt og §§1–2. Senere eksamenskrav er ikke automatisk krav for denne delinnleveringen. Evalueringen fra 2026-10-23 gjenbrukes uten å kjøre modell- og browser-seriene på nytt. Nåværende synlige navn er Aisha Agent; eldre resultater beholder sin opprinnelige proveniens.

## Reproduser walking skeleton

Kjør fra repository-roten i PowerShell, med Python 3.12. Ingen av kommandoene nedenfor laster ned en modell eller kommunale nettsider.

```powershell
python --version
python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
```

Dette er eksplisitt syntetisk mock-modus, ikke en reell modelltest. Forvent JSON med støttede påstander og kildehenvisninger; kontrollresultatet lagres i `evidence/walking-skeleton-synthetic.json` og metadata i `evidence/new-command-register.json`.

Reell lokal modell krever at Ollama allerede kjører, `llama3.2:3b` er installert og den godkjente lokale katalogen `output/municipal-catalog.json` finnes og fortsatt er gyldig:

```powershell
ollama list
python -X utf8 -m hamar_agent --real-sources --source hamar-byggesak --model llama3.2:3b --ollama-timeout 90
```

Forvent kildebegrenset JSON med ett helt godkjent avsnitt og offisiell kilde. CLI-kilden over tester kildebasert kjøring; browser-testen dokumenterer spørsmålsbasert søk. Reell katalog følger ikke med Git-klonen. Godkjenningene utløper 2026-10-28; ikke endre utløpsdato eller hent HTML for å omgå dette. Reproduksjon på ny maskin krever lovlig godkjent lokal kildepakke, ellers skal reell modus stanse.

Nettside, bare dersom port 8000 ikke allerede brukes av korrekt server:

```powershell
python -X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Åpne http://127.0.0.1:8000 og spør «Hva kan jeg bygge uten å søke?». Offisiell lenke skal vises. Ikke start duplikat server, eksponer Ollama eller opprett tunnel. Backendens personvern- og kildekontroller må beholdes.

## Evidens og videre verifikasjon

Historiske eksakte kommandoer/tidspunkter finnes i `evidence/original-command-register.jsonl`; originalfilene er uendret. Den lagrede browser-loggen er fra siste Aisha-heading-kjøring på desktop, nettbrett og mobil. 23 Ollama-tilfeller inkluderer forventede avvisninger. Tabellen med 17 kontrollerte positive svar viser den eldre arkiverte serien, kontrollert på nytt av `verify_evidence.py`; den er ikke samme kjøring som den senere 23-tilfellersloggen som også er valgt ut. Disse seriene og nevnerne skal ikke blandes.

```powershell
python -X utf8 comp2/verify_package.py
python -X utf8 docs/reports/verify_evidence.py --archive-only --output comp2/evidence/ANOTHER-UNIQUE-audit.json
```

Den første kommandoen gir ikke-null exitkode så lenge innleveringskritiske krav er uavklart; det er tilsiktet. Den andre lager en **ny** fil og kontrollerer arkivert evidens, ikke en ny modellevaluering. Ikke kjør generatorer i `resultat/` over historiske logger. Eventuelle nye testresultater må få unike filnavn og egen dato.

## LaTeX

Ingen NeurIPS-stilfil eller LaTeX-kompilator ble funnet i denne arbeidsøkten. `report.pdf` er derfor ikke produsert, og 3–4 hovedsider samt maksimum to promptsider er ikke bekreftet. Kilden har riktig `\usepackage[preprint]{neurips_2025}` og ingen NeurIPS-sjekkliste, men dette er ikke bevis på riktig kompilert format.

Etter at den faktisk utleverte malen er tilgjengelig som `comp2/report/neurips_2025.sty`, kjør fra `comp2/report/` med installert TeX:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Disse kompileringskommandoene er foreløpig ikke kjørt. Kontroller referanser, figurtekst, tabellbredde og PDF visuelt. `maintextend`, `promptstart` og `promptend` i `.aux` hjelper med sidetall; hovedteksten må være 3–4 sider, promptvedlegget høyst to. Gi endelig fremdriftsplan faktiske datoer og avklar møte- og personvernkrav før pakken kan godkjennes for commit og innlevering.
