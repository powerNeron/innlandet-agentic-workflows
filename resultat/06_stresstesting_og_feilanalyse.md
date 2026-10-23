# Stresstesting og kausal feilanalyse

| Fase | n | Median ms | p95 ms | Forespørsler/s | Forventede avslag | Uventede utfall |
|---|---|---|---|---|---|---|
| Baseline | 64 | 102.975 | 145.027 | 55.015 | 0 | 0 |
| Perturbasjon | 256 | 112.574 | 151.673 | 59.338 | 16 | 0 |
| Gjenoppretting | 64 | 120.452 | 170.404 | 58.233 | 0 | 0 |

| ID | Injisert mekanisme | Baseline HTTP | Feil HTTP | Kall under feil | Gjenoppretting HTTP | Forventet kontroll bestått |
|---|---|---|---|---|---|---|
| F01 | Tidsavbrudd | 200 | 422 | 1 | 200 | True |
| F02 | Tilkobling avvist | 200 | 422 | 1 | 200 | True |
| F03 | Avkortet JSON | 200 | 422 | 1 | 200 | True |
| F04 | Manglende svarfelt | 200 | 422 | 1 | 200 | True |
| F05 | For stort svar | 200 | 422 | 1 | 200 | True |
| F06 | Feil avgift vedvarer | 200 | 422 | 2 | 200 | True |
| F07 | Falsk avsnitts-ID | 200 | 422 | 2 | 200 | True |
| F08 | Vilkår fjernet | 200 | 422 | 2 | 200 | True |
| F09 | Verifikator utilgjengelig | 200 | 422 | 1 | 200 | True |
| F10 | Utløpt testgodkjenning | 200 | 400 | 0 | 200 | True |
| F11 | Feil avgift korrigeres | — | 200 | 2 | — | True |

Hypotese for F01–F10: en injisert feil skal hindre nye publiserte svar; fjerning av feilen skal gjenopprette normal behandling. Baseline gir HTTP200. Testen måler provider-kall og resultatlager før/etter, og gjentar normalforespørselen etter restaurering. HTTP400 ved utløpt kilde skyldes avvisning i kildevalget før modellkall.

Avhengighetsklassen: F01/F02 fjerner tilgjengelig modelltransport i en isolert instans. Årsaken er det injiserte unntaket; appens eksisterende feilgrense gir HTTP422 uten nytt resultat. Transporten gjenopprettes, og samme instans gir HTTP200. Dette er gjenoppretting fra feil, ikke en ny kodereparasjon.

Evidensklassen: F06 returnerer feil avgift både før og etter korreksjon. To kall gir fortsatt utilstrekkelig støtte og HTTP422. F11 endrer bare andre modellrespons til riktig godkjent avsnitt: eksisterende korreksjon og ny verifikasjon gir HTTP200 etter to kall. Dette er en kontrollert kontrafaktisk demonstrasjon av eksisterende reparasjonsmekanisme, ikke en nylig reparert programdefekt.

Global nødstopp: en barriere holder transporten i arbeid; samtalen nullstilles mens den kjører. Etter frigivelse fullfører transporten, men publisering av det gamle svaret avvises med HTTP409. Publiseringsvern fungerer; beregningsavbrytelse gjør det ikke. Foreslått separat reparasjon: global avbrytelsestilstand, nye kall sperres, avbrytbar transport og etterprøvbar terminering. Ingen appreparasjon er utført.

Det finnes seks egenvalgte mekanismeklasser i F-serien. Navnene på de fire offisielle klassene mangler. Vi kan derfor ikke hevde at minst to av dem er dekket. Kaldstartfeilen i historiske logger er en driftsobservasjon, ikke planlagt feilinjeksjon. Eldre belastningsforsøk og sikkerhetsfeil er fortsatt bevart i docs/reports/verified-results-2026-10-23.md.
