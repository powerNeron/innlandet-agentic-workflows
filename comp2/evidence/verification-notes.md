# Verifikasjon av den nye rapportpakken

Dato: 2026-10-23. Arbeidsgrunnlag: `be3884c3bcd5e55f8b5fe5ef9f03505eb7bd94c8`. `origin/main` ble hentet; HEAD og origin/main hadde ingen divergens. Ingen filer er staged, og ingen commit eller push er utført.

## Nye kontroller

- `python -X utf8 docs/reports/verify_evidence.py --archive-only --output comp2/evidence/archived-evidence-audit.json`: vellykket kontroll av eksisterende arkiv, uten modellkjøring. Bekrefter 282 offline-tester, 23 historiske Ollama-tilfeller, 17 positive lagrede svar og 13 browser-spørsmål. Tidligere og senere modellserier er ikke slått sammen.
- `python -X utf8 comp2/run_walking_skeleton.py`: to nye CLI-kjøringer med Python 3.12.10; begge exit 0. Syntetisk fixture ga to støttede påstander; reell byggesak ga én påstand, offisiell URL og ingen verifikasjonsfunn. Eksakte kommandoer og UTC-tider er lagret i `new-command-register.json`. Reell kjøring brukte eksisterende lokal katalog og Ollama, ikke nettsidehenting.
- `python -X utf8 comp2/verify_package.py`: tallparitet, kildehenvisninger, byteidentiske kopier, tidligere kontroll av 17 svar, browser-logg for tre Aisha-oppsett og nye CLI-utdata kontrolleres. Forventet ikke-null exit fordi innleveringskritiske krav ikke er verifisert. JSON skiller tekniske kontroller fra innleveringsklarhet.
- `git diff --check`: ingen rapporterte formateringsfeil i sporede endringer. Nye filer kontrolleres separat; ingen originalfiler er endret.
- Eksisterende `resultat/logger/pakke-manifest.json`: samtlige 190 registrerte originalfiler samsvarer med SHA-256. Manifestet selv er bare lest. Git-status viser bare ny `comp2/`.
- Enkel sensitivitetsskanning fant ingen e-postadresser, lokale hjemmestier eller gjenkjente nøkkelmønstre i tekstmaterialet. Manuell gjennomgang av valgte tekstfiler fant ingen personopplysninger eller hemmeligheter. Dette er ikke en generell garanti for all historisk prosjektbehandling.
- Arkitekturfiguren ble åpnet og visuelt kontrollert: leselige engelske etiketter og piler, uten overlapp. Den er en kompakt gjengivelse; Mermaid-filen viser hele avvisnings- og korrigeringsforløpet. PDF-rapportens figurstørrelse er ikke kontrollert uten kompilering.

## Bevisste avgrensninger

Ingen ny kjøring av alle 282 tester, 23 Ollama-tilfeller eller Chrome-serien var nødvendig for denne dokumentasjonsoppgaven. Tallene er gjenbrukte, sporbare målinger fra 2026-10-23, ikke påstått nye testserier. Nye CLI-kjøringer er separat dokumentert og inngår ikke i de historiske nevnerne. Ingen nye brukerdata, brukerundersøkelser eller stressresultater er produsert.

## Kritiske mangler — ikke commit/push

1. Faktisk utlevert NeurIPS-mal og kompilator mangler; `report.pdf` finnes ikke.
2. Hovedtekst på 3–4 sider og promptvedlegg på maksimalt to sider kan ikke bekreftes.
3. Faktisk demonstrasjons- og innleveringsdato mangler; planen er relativ.
4. Reelle møtereferater er ikke bekreftet av tilgjengelig materiale.
5. Historisk transient HTML-behandling må avklares opp mot oppgavens strenge personvernkrav. Nåværende henting er blokkert, og godkjenningsdatoer er uendret.

Etter brukerens betingede autorisasjon skal pakken bli liggende lokalt inntil disse obligatoriske forholdene er avklart og nye kontroller består. Det finnes derfor ingen ny remote commit-hash å rapportere.
