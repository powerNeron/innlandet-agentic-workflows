# Verifiserte resultater

KIUA-2003 — Hamar KommuneAgent. 2026-10-23. Commit `e8987cfe9ec87bbf6baa01138ae37d18e5025536`.

Dette er et rapportgrunnlag, ikke en ferdig eller godkjent innlevering. Offisiell tekst som er tilgjengelig lokalt dekker bare Compulsory 2. Full sluttoppgave, W40-materiale, utdelt LaTeX-mal og demonstrasjonsdato mangler. Alle tall hentes fra [felles datasett](data/shared.json); ingen forsøk ble kjørt om igjen for oversettelsen.

Les resultatoversikten, målemetoden, sikkerhetsanalysen og eksamenssjekklisten samlet. Rålogger ligger i logger/. Engelske tabeller og figurer har samme tall som de norske.

Repository: https://github.com/powerNeron/innlandet-agentic-workflows

| ID | Dato | n | Bestått | Ikke bestått | Logg | Tolkning |
|---|---|---|---|---|---|---|
| O1 | 2026-10-23 | 282 | 282 | 0 | logger/offline.txt | Offline-regresjon |
| O2 | 2026-10-23 | 1 | 1 | 0 | logger/holdout.json | Separat lagret syntetisk holdout |
| O3 | 2026-10-23 | 8 | 8 | 0 | logger/verifier-scorecard.json | Syntetisk funnkodedeteksjon |
| M1 | 2026-10-23 | 23 | 23 | 0 | logger/real-smoke/summary.json | Reell modell: svar og tilsiktede avslag |
| M2 | 2026-10-23 | 14 | 14 | 0 | logger/model-measurements.json | Reelle målinger: temperaturavbrutt utvalg |
| F | 2026-10-23 | 11 | 11 | 0 | logger/fault-injection.json | Isolerte feil- og korreksjonsforsøk |
| P | 2026-10-23 | 10 | 10 | 0 | logger/fault-injection.json | Tillatelses- og promptgrenser |
| G | 2026-10-23 | 15 | 15 | 0 | logger/approval-gates.json | Godkjennings- og endepunktporter |
| S | 2026-10-23 | 384 | 384 | 0 | logger/http-stress.json | Syntetisk HTTP-baseline, feil og gjenoppretting |
| B | 2026-10-23 | 13 | 13 | 0 | logger/browser/browser-check.txt | Navngitte spørsmål i ekte Chrome |
| KILL | 2026-10-23 | 1 | 0 | 1 | logger/fault-injection.json | Global beregningsstopp: ikke håndhevet |
| SEM | 2026-10-23 | 1 | 0 | 1 | logger/fault-injection.json | Semantisk injeksjonsimmunitet: ikke etablert |


Språkversjoner: [norsk](norsk/00_READ_ME.md) og [English](english/00_READ_ME.md). [Komplett filinventar](FILOVERSIKT.md). [Endelig kontroll](logger/final-audit.json).
