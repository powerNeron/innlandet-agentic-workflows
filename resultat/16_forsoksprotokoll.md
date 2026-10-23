# Forsøksprotokoll og endringsgrense

Forsøkene ble valgt etter gjennomgang av faktisk tilgjengelig oppgavetekst, eksisterende harness, syntetiske fixtures, promptlogg, beslutningsnotater og tidligere rapportpakke. Selvvalgte tillegg er kausal gjenoppretting, samtidige negative HTTP-kontroller, faktiske tokenmålinger, budsjettgrenser og kontroll av forskjellen mellom tilstandsreset og beregningsavbrytelse. De presenteres ikke som ordrette undervisningskrav.

For hvert F-tilfelle er hypotese, baseline, perturbasjon, forventning, observasjon, kallantall, gjenoppretting og begrensning bevart i logger/fault-injection.json og 06. Ingen appfunksjonalitet ble endret. Eksisterende korreksjon er testet; nye globale kontroller krever egen godkjenning. Sikkerhetsprøver brukte bare syntetisk data. Ingen utenforstående fikk tilgang; ingen tunnel, commit eller push ble utført.
