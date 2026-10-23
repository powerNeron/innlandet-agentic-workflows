# Ytelse og tokenmåling

| Gruppe | n | Median ms | p95 ms | Min ms | Maks ms | Logg |
|---|---|---|---|---|---|---|
| Sekvensielt | 12 | 1511.1545 | 2103.674 | 1155.707 | 2103.674 | ../logger/model-measurements.json |
| Samtidighet 2 | 2 | 2299.8905 | 3066.538 | 1533.243 | 3066.538 | ../logger/model-measurements.json |

Totalt rapporterte Ollama 4120 prompttoken og 1716 genererte token for 14 fullførte modellkall. Tokendata gjelder bare den instrumenterte måleserien, ikke hele prosjektet. Grensen 700 er en forespurt utgrense per kall, ikke et globalt token- eller kostnadsbudsjett. Lokale API-kall er målt; energikostnad og fakturert pris er ikke målt.

| Fase | n | Median ms | p95 ms | Forespørsler/s | Forventede avslag | Uventede utfall |
|---|---|---|---|---|---|---|
| Baseline | 64 | 102.975 | 145.027 | 55.015 | 0 | 0 |
| Perturbasjon | 256 | 112.574 | 151.673 | 59.338 | 16 | 0 |
| Gjenoppretting | 64 | 120.452 | 170.404 | 58.233 | 0 | 0 |
