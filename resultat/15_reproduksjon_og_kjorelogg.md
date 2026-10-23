# Reproduksjon og kjørelogg

Kjør fra repo-roten med samme commit og Python-miljø. Alle tidligere kommandoer, UTC-tider, utfall og saniterte råutdata finnes i logger/kommandoer.jsonl. Reelle tester krever eksisterende godkjent lokal katalog og installert modell. Godkjenning skal ikke forlenges for å få en test til å kjøre. Ingen rå HTML hentes.

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

Kommandoene er de faktiske inngangspunktene, men eksisterende utdata opprettes eksklusivt. For ny kjøring må en separat forsøkskopi med tom resultatmappe brukes; ikke slett eller overskriv evidens. Testverktøyet starter egne loopback-servere på ledige porter og lar port 8000 være urørt. Chrome-profilen opprettes midlertidig og beholdes ikke. Diagrammer bygges med allerede tilgjengelig matplotlib. Git-kloning alene gir ikke den ignorerte katalogen; lovlig overføring og gyldighet må avklares.

Historiske resultater og metodeforbehold gjenbrukes fra docs/reports/verified-results-2026-10-23.md, evidence-2026-10-23.json og verify_evidence.py. De 43 gamle filene ble hashkontrollert uten nye historiske eksperimenter.


Rapportgeneratorene validerer det innsamlede utvalget eksplisitt. Ved en ny forsøksserie med annet antall fullførte kall må nye utvalg og etiketter gjennomgås i forsøkskopien; ikke tving gamle summer inn i nye logger. Full tospråklig tabell: norsk/01_full_requirements.md. Historiske tabeller: norsk/20_historical_evidence.md. Sluttkontroll kjøres med `python -X utf8 resultat/audit_package.py`.