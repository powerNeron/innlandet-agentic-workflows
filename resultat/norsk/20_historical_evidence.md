# Historisk evidens og feiltilfeller

Tallene nedenfor er hentet fra den tidligere verifiserte pakken i docs/reports/. Originale historiske logger er ikke endret eller kjørt om igjen. De er hashkontrollert i logger/historisk-hashkontroll.json. Historiske og nye målinger skal ikke slås sammen som uavhengige observasjoner.

| ID | Dato | n | Observasjon | Begrensning | Primærfil |
|---|---|---|---|---|---|
| H1 | 2026-10-22 | 12 | p50=2.391 s; p95=2.547 s; max=2.563 s | Blandet sekvensiell og samtidig modellkjøring; historisk kode | [JSON](../logger/historisk/output/final-technical-evidence/ollama-performance-20261022.json) |
| H2a | 2026-10-22 | 44 | duration=59.625 s; p95=2.719 s; errors=0; all_60=False | Samtidighet 2; nådde ikke målet om 60 forespørsler | [JSON](../logger/historisk/output/final-technical-evidence/ollama-sustained-performance-20261022.json) |
| H2b | 2026-10-22 | 50 | duration=75.453 s; p95=1.516 s; errors=0; all_60=False | Samtidighet 1; nådde ikke målet om 60 forespørsler | [JSON](../logger/historisk/output/final-technical-evidence/ollama-sustained-performance-c1-20261022.json) |
| H3 | 2026-10-22 | 800 | workers=8; failures=0; rate=64.27 requests/s; p95=137.554 ms | Kun søk; full historisk inline-kommando mangler | [JSON](../logger/historisk/output/final-technical-evidence/local-http-search-stress-20261022.json) |
| H4a | 2026-10-22 | 8 | source_selection=8/8; answer_criteria=7/8 | Byggesak ble trygt avvist, men oppfylte ikke forventet positivt svarkriterium | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H4b | 2026-10-22 | 3 | rejected=3/3 | Kun testede brukerangrep | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H4c | 2026-10-22 | 3 | security_pass=0/3 | Generisk syntetisk modellbane; instruksjonsavsnitt valgt og verifikasjonsfunn registrert | [JSON](../logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) |
| H5 | 2026-10-22 | 1 | attempts=1; final_findings=0; elapsed=1.376 s | Injisert første feil; reell modellkorreksjon; full inline-kommando mangler | [JSON](../logger/historisk/output/final-technical-evidence/ollama-correction-20261022.json) |
| H6 | 2026-10-22 | 1 | findings=0; selected_injection=False | Én produksjonsadapterprobe er ikke generell immunitet | [JSON](../logger/historisk/output/final-technical-evidence/production-adapter-injection-probe-20261022.json) |

De historiske modellbelastningsforsøkene nådde GPU-temperatur 80 °C, som var stoppgrense i de daværende verktøyene. Dette var ufullførte mål, ikke produksjonskapasitetsbevis. Gamle p95-verdier bruker skriptenes gulvindeks og må ikke forveksles med nearest-rank brukt i nye målinger.

Kaldstart etter Windows-omstart var en observert driftsfeil, ikke planlagt injeksjon: chat-kallet feilet etter 90 s mens modelloppstart tok omtrent 65 s. Senere varme kall virket uten kodeendring. Hvorfor resten av første inferens tok så lang tid er ikke fastslått. Historisk Hamar-traceback og eksakt reproduksjonskommando mangler.

Full metode og forbehold: docs/reports/verified-results-2026-10-23.md; docs/reports/evidence-2026-10-23.json; docs/reports/verify_evidence.py.
