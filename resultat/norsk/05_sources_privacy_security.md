# Kildekontroll, personvern og sikkerhet

| Mål | Verdi | Kilde |
|---|---|---|
| Godkjente dokumenter | 8 | docs/approved-service-pages.json |
| Godkjente avsnitt | 39 | docs/reviewed-service-selection.json |
| Lagrede positive svar kontrollert på nytt | 17 | logger/real-smoke/*.json |
| Påstander med eksakt samsvar og kilde-URL | 17 | logger/real-smoke/*.json |
| Godkjenningsutløp | 2026-10-28 | docs/approved-service-pages.json |
| Nye kommunale nettinnhentinger | 0 | run_experiments.py |

M1 har 18 positive modelltilfeller. Bare 17 egne resultatfiler finnes fordi én SFO-repetisjon ikke lagres separat. Sammendragets grounded_claims=14 er en delsummering; fire positive spørsmålsrader mangler dette feltet. citation_checks_passed=23 omfatter også riktige avslag, ikke 23 positive sitater.

Backend krever ordrett helt kildeavsnitt og gyldig proveniens. Dette sertifiserer ikke semantisk sannhet eller full kontekst. Menneskelig godkjenning av kildetekst er en sentral tillitsgrense. Et isolert syntetisk moteksempel viste at et ordrett instruksjonsavsnitt kan få null verifikasjonsfunn.

Tillatelser ble testet med ugyldig Host, Origin, økt-token, modellvalg, ukjent request-felt og oversize request. Personverntilfellet bruker bare oppdiktet kontakttekst. Modellen ble ikke kalt for disse avslagene. G-testene verifiserer at både eksternaktivering og personvernflagg kreves, og at alle lokale sjekklister må være satt før en godkjenningspost opprettes. Selv en slik post kan ikke aktivere kilden. Rollene er selverklærte, ikke identitetsautentiserte.

Ingen rå HTML ble hentet. Lokalt katalogoppslag er ikke levende nettsøk. Historisk HTML-behandling og full institusjonell personvernetterlevelse forblir uavklart. 43 gamle evidensfiler, inkludert kildekatalogen og manifestene, er kontrollert uendret mot tidligere SHA-256. Se ../logger/historisk-hashkontroll.json. Reelle økt-token og nettleserprofiler publiseres ikke.
