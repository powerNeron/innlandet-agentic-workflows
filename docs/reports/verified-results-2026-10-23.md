# Verifiserte resultater for Hamar KommuneAgent

**Emne:** KIUA-2003. **Evidensgjennomgang:** 23.10.2026. **Kodegrunnlag:** `e8987cfe9ec87bbf6baa01138ae37d18e5025536`.

## 1. Eksperimentelt oppsett

Hamar KommuneAgent er en lokal prototype for søk og kildebaserte svar om kommunale tjenester. Evalueringen gjelder et begrenset kildeutvalg og en ekstraktiv svarmekanisme. Den måler ikke kommunens samlede informasjonstilbud eller en generell språkmodells faktakunnskap.

| Komponent | Dokumentert oppsett |
| --- | --- |
| Operativsystem og testmiljø | Windows 11, AMD64; `python` rapporterte Python 3.12.10 ved evidensgjennomgangen. Ingen nye avhengigheter ble installert. |
| Nettleserverktøy | Node.js v24.14.0 og Chrome 155.0.8059.85, avlest 23.10.2026. Chrome kjøres automatisk i headless-modus gjennom DevTools-protokollen. |
| Modellserver | Lokal Ollama, versjon 0.40.8 avlest fra `/api/version` 23.10.2026. Ingen nye modellkall ble utført under evidensgjennomgangen. |
| Modell | `llama3.2:3b`, 3,2 milliarder parametere, GGUF, Q4_K_M. Modellens rapporterte digest var `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`. |
| Kontekst | `/api/ps` viste aktiv kontekst på 4096 token og `size_vram=2561000078` byte. Modellmetadata oppgir maksimal kontekst på 131072; dette er ikke den aktive kontekstlengden. |
| Generering | Temperatur 0, seed 0, `num_predict=700`. Real- og nettleserharness bruker 90 sekunders socket-timeout. Den generiske klientens standard er 45 sekunder; disse må ikke forveksles. |
| Datagrunnlag | Åtte godkjente kilder med 39 utvalgte avsnitt, gjennomgått 21.10.2026, godkjenning til 28.10.2026. Manifestene er uendret. |

Den tidligere undersøkte serveren på port 8000 brukte et annet virtuelt miljø med Python 3.13.7. Testkommandoene her bruker Python 3.12.10. Det foreligger ikke et kontrollert sammenligningsforsøk mellom disse miljøene. Nettleserharnesset starter sin egen loopback-server på en ledig port; tidligere tester mot den faktiske port 8000 er separat dokumentert i [UI-notatet](../meetings/2026-10-23-simplified-website-copy.md).

### Arkitektur og arbeidsflyt

1. Nettleseren og backend kontrollerer inndata. Syntetiske personvernprøver brukes i testene. I realmodus er tillatte temaord, normalisering og oppfølgingskontekst avgrenset; dette er ingen generell garanti for gjenkjenning av personopplysninger.
2. Et deterministisk søk finner relevante avsnitt i den lokale godkjente katalogen. Kildens identitet, godkjenning og gyldighet kontrolleres. Enkelte spørsmål om pris, søknadsprosedyre og lignende avvises før modellkall dersom nødvendig grunnlag mangler.
3. Utvalgte avsnitt gjøres til en avgrenset modellkontekst. Brukerens spørsmål sendes ikke som fri tekst til den reelle modelladapteren. Modellen velger ett helt avsnitt gjennom et begrenset JSON-skjema. Relevansen avhenger derfor i vesentlig grad av søk og forhåndskontroller.
4. Eksisterende verifikasjon suppleres med kravet `påstandstekst == evidenssitat == helt godkjent avsnitt`. Avsnittsidentitet og kildeproveniens kontrolleres. Dette gir sporbarhet og bevaring av avsnittets formuleringer, ikke semantisk faktasjekk.
5. Ved verifikasjonsfunn tillates høyst ett korrigeringsforsøk, etterfulgt av obligatorisk ny verifikasjon. Uløste funn eller modell-/verifikasjonsfeil hindrer publisering av svaret. Avvist kandidattekst beholdes ikke i korrigeringshistorikken.
6. Godkjente svar vises med kildehenvisning og offisiell lenke. Backendens JSON-eksport er bevart, men eksportkontroller og manuelle kilde-/arbeidsflytpaneler er fjernet fra brukergrensesnittet.

Arbeidsflyten er en kontrollert flertrinnspipeline. Den er ikke en agent med ubegrenset autonom nettlesing eller vilkårlige eksterne verktøy.

### Lokal gjenfinning og levende nettinnhenting

**Automatisert lokal gjenfinning** betyr at programmet søker i `output/municipal-catalog.json`. Det innebærer ingen forespørsel til kommunens nettsted. Offisielle lenker og hentetidspunkt i svarene er proveniens fra katalogen, ikke bevis på at nettsiden nettopp er kontrollert.

Kildene ble opprinnelig valgt manuelt på URL- og avsnittsnivå og importert historisk. Gjeldende kode sperrer levende HTML-innhenting og CLI-import av HTML-snapshots. Dette er kontrollert i `portal_sources.py` og `municipal_import.py`. Eldre dokumentasjon, blant annet deler av kravmatrisen, beskriver tidligere tilstander og må ikke brukes ukritisk som beskrivelse av dagens kode. Avsnittsfiltrering etter nedlasting kan ikke garantere at personopplysninger aldri ble behandlet i den historiske innhentingen.

## 2. Evalueringsmetodikk

Tre evidenstyper holdes atskilt:

- **Offline-tester:** `unittest` med ekte sockets og DNS blokkert av harnesset. Modelladferd kan være simulert; dette er ikke reelle Ollama-forsøk.
- **Reelle modelltester:** lokal Ollama og den eksisterende godkjente katalogen. De kontrollerer avsnittsstøtte, kildeidentitet, avslag og noen stabilitets-/sikkerhetstilfeller.
- **Automatiserte nettlesertester:** ekte Chrome og ekte lokal modell, med programmerte UI-handlinger. Visuell inspeksjon av skjermbilder er en separat manuell kontroll og ingen brukerstudie.

Ved denne gjennomgangen ble eksisterende logger analysert, summer kontrollert og 17 lagrede positive modellresultater sammenlignet direkte med godkjente katalogavsnitt og offisielle kilde-URL-er. Ingen nye inferens-, belastnings- eller nettleserkjøringer var nødvendige. [Kontrollskriptet](verify_evidence.py) leser bare lokal evidens og oppretter en ny oppsummering; det endrer ikke appen eller kildene.

[Evidensfilen](evidence-2026-10-23.json) inneholder kontrollerte summer, utvalgte historiske målinger og SHA-256 for 43 underliggende filer. Tidsstempel fra filsystemet registreres uttrykkelig som filmetadata, ikke som sikkert bevis på kjøretid. Testdatoene nedenfor bygger på datert kjøringsdokumentasjon og loggnavn; de historiske ytelsesfilene har også interne UTC-tidsstempler.

## 3. Resultater

| ID og type | Dato | Verifisert resultat | Hva resultatet viser / begrensning |
| --- | --- | --- | --- |
| O1: offline-regresjon | 23.10.2026 | 282 tester; 282 bestått, 0 feilende, 0 kjørefeil; 2,281 s | Korrekthet mot det implementerte testsettet. Kjøretiden omfatter offline-suite, ikke en AI-forespørsel. |
| M1: reell Ollama-smoke | 23.10.2026 | 23/23 testtilfeller bestått: 18 positive modelltilfeller, 4 avslag ved utilstrekkelig evidens, 1 personvernavslag | Lite, sekvensielt utvalg. Ikke 23 genererte svar. Ett SFO-tilfelle gjentas. |
| M1: påstander og sitater | 23.10.2026 | 18 påstander ved summering av alle rader; 17 lagrede positive svar kontrollert på nytt, alle med ordrett støtte og kilde-URL | Den gjentatte SFO-kjøringen har ikke egen resultatfil. Ingen uavhengig semantisk eller menneskelig kvalitetsvurdering. |
| M1: responstid | 23.10.2026 | 18 målinger: median 1359 ms, p95 2181 ms, min. 1016 ms, maks. 2181 ms | `provider_latency_ms` omfatter arbeid i realarbeidsflyten, inkludert kontroll; ikke ren GPU-inferenstid eller hele nettleseropplevelsen. |
| B1: Chrome-regresjon | 23.10.2026 | 8 kategorisøk; 13 navngitte spørsmål med HTTP 200: 7 `evidence_checked`, 5 `insufficient_evidence`, 1 `clarification_required` | Forventede avslag regnes som beståtte tester. Ingen testprosent for generell svarkvalitet utledes. |
| B1: responsivitet og sikkerhet | 23.10.2026 | Desktop 1440×1100, nettbrett 820×1180, mobil 390×844; mobilt byggespørsmål med reell modell og offisiell kilde; 0 JavaScript-/konsollfeil og 0 observerte HTTP-feil | Simulerte skjermstørrelser i Chrome. Ikke fysisk mobiltest eller full tilgjengelighetssertifisering. Privatinndata avvist lokalt; samtalenullstilling og backendeksport kontrollert. |
| H1: kort modellbelastning | 22.10.2026 | 12/12 forespørsler verifisert; 4 sekvensielle og 8 med samtidighet 2. Registrert p50 2,391 s, p95 2,547 s, maks. 2,563 s | Historisk måling på én SFO-kilde. Kvantiler beregnet med gulvindeks i skriptet, ikke samme metode som M1. |
| H2: lengre modellbelastning | 22.10.2026 | Samtidighet 2: 44 fullførte, 0 forespørselsfeil, 59,625 s, p95 2,719 s. Samtidighet 1: 50 fullførte, 0 forespørselsfeil, 75,453 s, p95 1,516 s | Begge har `all_60_verified_no_errors=false`. Første nådde heller ikke 60 sekunder. Maksimal registrert GPU-temperatur var 80 °C, som er stoppgrense i skriptene. Ikke bestått 60-forespørselsmål. |
| H3: lokal søkebelastning | 22.10.2026 | 800 forespørsler, 8 arbeidere, 0 feil; 12,4467 s; registrert 64,27 forespørsler/s og p95 137,554 ms | Kun `/api/search`, ingen modellgenerering. Full original kjørekommando er ikke bevart. |
| H4: historisk kvalitet/sikkerhet | 22.10.2026 | Korrekt kildevalg 8/8; samlet positivt svarkriterium 7/8. Tre brukerangrep avvist; 0/3 syntetiske kildeinjeksjonsforsøk bestod sikkerhetskriteriet | Testen fikk samlet negativt kvalitets-/sikkerhetsutfall. Byggesak ga et sikkert evidensavslag i stedet for forventet positivt svar. Injeksjonsforsøkene brukte den generiske syntetiske modellbanen. |
| H5: korrigering og adapterprobe | 22.10.2026 | Ett injisert feiltilfelle korrigert gjennom faktisk Ollama: 1 forsøk, 0 sluttfunn, 1 sluttpåstand, 1,376 s. Én separat probe med produksjonsadapteren valgte faktavsnittet, 0 funn | Korrigeringsforsøket er feilinjeksjon, ikke en spontant oppstått modellfeil. Én positiv adapterprobe opphever ikke injeksjonsfeilene i H4. |

### Telleavvik og ressursmålinger

M1-sammendraget lagrer `grounded_claims=14`, fordi summeringen bare inkluderer radene som har akkurat dette feltet. Fire ytterligere positive spørsmål har `claims=1`, men mangler `grounded_claims`. Summen av `claims` over alle rader er derfor 18. Applikasjonen og den opprinnelige loggen er ikke endret; begge tall er bevart og forklart i evidenspakken.

`citation_checks_passed=23` betyr beståtte testkriterier for sitater eller korrekt fravær av sitater. Det betyr ikke 23 positive svar med hver sin verifiserte påstand. Personvernavslag og evidensavslag inngår i dette feltet.

H1 registrerte 9 ressursprøver, med toppverdier CPU 21,0 %, brukt systemminne 20907 MiB, GPU-utnyttelse 95 %, GPU-minne 3058 MiB og temperatur 73 °C. Dette er system-/GPU-observasjoner som kan omfatte andre prosesser. Ollama-prosessenes rapporterte RSS på 119 MiB omfatter ikke GPU-modellminnet. H2s ressursprøver er bevart i originalfilene; målingene dokumenterer ikke kapasitet for en produksjonstjeneste.

**Faktisk tokenforbruk er ikke registrert i disse resultatene.** `num_predict=700` er en øvre forespurt grense per modellkall, ikke målt forbruk. Høyst to modellkall gir en teoretisk forespurt utgrense på 1400 token per svarforløp. Promptgrensen på 24000 tegn er ikke en tokenmåling. Token/s, energi og kostnad per svar kan derfor ikke oppgis.

## 4. Analyse av pålitelighet og sikkerhet

Resultatene støtter at prototypen kan finne et begrenset utvalg kommunale avsnitt og presentere dem med sporbare kilder. Avslag når pris eller prosedyre ikke er dokumentert, er tilsiktet adferd. De skal ikke omtolkes til at systemet har svart på alle spørsmål.

Verifikasjonen kontrollerer tekstsamsvar, avsnittsidentitet og godkjenning. Den kan avdekke endret ordlyd, manglende støtte og enkelte motstridende påstander, men kan ikke avgjøre om kommunens tekst er fullstendig, fortsatt riktig eller relevant for en konkret persons situasjon. Dersom vesentlige vilkår står i andre avsnitt, kan et korrekt sitert enkeltavsnitt være utilstrekkelig.

Realmodus bruker kun godkjent katalog, lokal modelladresse, avgrensede modellvalg og ingen automatisk overgang til syntetisk eller betalt leverandør ved feil. HTTP-serveren bindes til loopback og kontrollerer Host, Origin og økt-token. Resultater tilhører riktig økt, er tids-/antallsbegrensede og feiltekster er sanitert. Kildetekst behandles som data, og modellen får et begrenset svarskjema. Kontrollene reduserer angrepsflaten; de gir ikke grunnlag for å erklære systemet immunt mot promptinjeksjon eller personvernbrudd.

H4 viste at den generiske modellbanen kunne velge instruksjonslignende syntetisk tekst. Verifikasjonen registrerte funn; loggen alene dokumenterer ikke at slike svar ble publisert til brukere. Produksjonsadapterens ene positive probe er et smalt tilleggseksperiment. Begge observasjonene må omtales i rapporten.

En tidligere kaldstart etter Windows-omstart er dokumentert med et `/api/chat`-kall som endte med HTTP 500 etter 90 sekunder, mens modelloppstart tok omtrent 65 sekunder. Senere varme kall lyktes uten kodeendring. Full historisk Hamar-traceback og eksakt reproduksjonskommando for den opprinnelige feilen mangler. Dette er en kjent driftsbegrensning, ikke en kontrollert kaldstartbenchmark. Se det lokale, upubliserte diagnostikknotatet `docs/meetings/2026-10-23-ai-answer-restart-diagnosis.md`; det inngår ikke som personlig rålogg i denne pakken.

## 5. Kjente begrensninger

- Lite og delvis håndvalgt testmateriale; én gjentatt SFO-test er ikke en statistisk stabilitetsanalyse. Flere tester bruker de samme kildene.
- Ingen uavhengig menneskelig vurdering av semantisk korrekthet, lesbarhet eller opplevd nytte. Ingen brukerstudie eller menneskelig skjermlesergodkjenning.
- Eldre målinger er fra tidligere kodeversjoner og er ikke gjentatt på sluttversjonen. De må ikke blandes til én samlet suksessrate.
- Ingen dokumentert full end-to-end-sporing av alle modellkall, tokenforbruk eller produksjonsmessig flerbrukerdrift. Historiske belastningsforsøk nådde ikke alle målene.
- Katalog, logger og hjelpeskript i `output/` er lokale, ignorerte artefakter. Git-kloning alene gjenskaper ikke realmodellforsøkene. SHA-256 bekrefter filidentitet, ikke at innholdet opprinnelig ble målt korrekt.
- Godkjenningen utløper 28.10.2026. Senere realkjøringer krever faktisk fornyet kildevurdering og godkjent datatilgang. Ingen dato skal forlenges for å få testen til å bestå. Historiske logganalyser kan fortsatt utføres, men kontrollskriptets katalogvalidering kan da avvise utløpt materiale.
- Historisk behandling av HTML og full personvern-/oppgaveetterlevelse er ikke avklart av disse testene. Konklusjonen må begrenses til de dokumenterte kontrollene og forsøkene.

## 6. Reproduksjon

Alle kommandoer kjøres fra prosjektroten. Bruk Python 3.12.10 og samme kodeversjon for sammenlignbare forsøk. Ollama og modellen må være tilgjengelige lokalt; ingen ny modellnedlasting eller installasjon er utført her. Nye resultatnavn er nødvendige fordi harnessene nekter å overskrive eksisterende filer.

| ID | Kommando knyttet til primærresultatet | Underliggende fil |
| --- | --- | --- |
| O1 | `python -X utf8 -m harness.offline_tests --output output/approved-ui-prepush-offline-20261023.txt` | [Offline-logg](../../resultat/logger/historisk/output/approved-ui-prepush-offline-20261023.txt) |
| M1 | `python -X utf8 -m harness.real_source_smoke --enable-local-llm --output output/restart-ai-real-20261023` | [Sammendrag og rader](../../resultat/logger/historisk/output/restart-ai-real-20261023/summary.json), samt individuelle JSON-resultater i samme mappe |
| B1 | `python -X utf8 -m harness.browser_smoke --enable-local-llm --output output/approved-ui-prepush-browser-20261023` | [Chrome-logg](../../resultat/logger/historisk/output/approved-ui-prepush-browser-20261023/browser-check.txt) og skjermbilder i samme mappe |
| H1 | Rekonstruert fra bevart skript: `python -X utf8 -m output.final-technical-evidence.ollama-performance-20261022` | [12 forespørsler](../../resultat/logger/historisk/output/final-technical-evidence/ollama-performance-20261022.json) og tilsvarende `.py` |
| H2 | Rekonstruert: `python -X utf8 -m output.final-technical-evidence.ollama-sustained-performance-20261022` og `python -X utf8 -m output.final-technical-evidence.ollama-sustained-performance-c1-20261022` | [Samtidighet 2](../../resultat/logger/historisk/output/final-technical-evidence/ollama-sustained-performance-20261022.json), [samtidighet 1](../../resultat/logger/historisk/output/final-technical-evidence/ollama-sustained-performance-c1-20261022.json) og tilsvarende `.py` |
| H3 | Eksakt kommando mangler; historisk register oppgir bare PowerShell-tekst pipet til `python -` | [Søkebelastning](../../resultat/logger/historisk/output/final-technical-evidence/local-http-search-stress-20261022.json) og [historisk kjøringsregister](../../resultat/logger/historisk/test-results-sanitized.json) |
| H4 | Rekonstruert: `python -X utf8 -m output.final-technical-evidence.ollama-quality-adversarial-20261022` | [Kvalitet og injeksjonsforsøk](../../resultat/logger/historisk/output/final-technical-evidence/ollama-quality-adversarial-20261022-postfix.json) og bevart skript uten `-postfix` i filnavnet |
| H5 | Korrigering: eksakt inline-kommando mangler. Adapterprobe, rekonstruert: `python -X utf8 -m output.final-technical-evidence.production-adapter-injection-probe-20261022` | [Korrigering](../../resultat/logger/historisk/output/final-technical-evidence/ollama-correction-20261022.json), [adapterprobe](../../resultat/logger/historisk/output/final-technical-evidence/production-adapter-injection-probe-20261022.json) |

De rekonstruerte historiske kommandoene er ikke bevart som faktisk terminalhistorikk og er ikke kjørt på nytt her. Skriptene forutsetter lokale filer og noen bruker `psutil` og `nvidia-smi`. De har faste utdatafilnavn og skal bare gjentas i en separat forsøkskopi med nye mål; ikke overskriv original evidens. H3 og korrigeringsdelen av H5 kan ikke gjenskapes nøyaktig fra det bevarte kjøringsregisteret. Dette er et eksplisitt reproduksjonsavvik.

For en ny kontroll av evidensen, uten modellkall eller kommunal nettinnhenting:

```powershell
python -X utf8 docs/reports/verify_evidence.py --output docs/reports/evidence-NEW.json
```

For nye forsøk erstattes O1/M1/B1s utdata med ubrukte navn. For lokal manuell kontroll kan den eksisterende serveren brukes, eller én server startes med:

```powershell
python -X utf8 -m hamar_agent.web --real-sources --model llama3.2:3b --ollama-timeout 90 --port 8000
```

Åpne `http://127.0.0.1:8000/`, søk etter byggesak og spør «Hva kan jeg bygge uten å søke?». Kontroller kildeutdrag, verifikasjonsstatus og offisiell lenke. Ikke start en ekstra server dersom porten allerede er i bruk. Dette er en reproduksjonsinstruksjon, ikke en påstand om en ny manuell test i denne gjennomgangen.

## 7. Evidensregister og faglig anvendelse

Pakken består av denne rapporten, [maskinlesbar evidens](evidence-2026-10-23.json) og [kontrollskriptet](verify_evidence.py). Evidensfilen identifiserer originalene med relative stier og filhasher uten å kopiere kommunal kildetekst, personopplysninger, modellprompter eller nettleserprofiler. Primærloggene må gjøres tilgjengelige separat i en faktisk innlevering etter gjennomgang; ingen automatisk publisering er utført.

Metodebeskrivelsen er kontrollert mot [realadapteren](../../hamar_agent/real_sources.py), [søke-/svarlaget](../../hamar_agent/portal.py), [modellklienten](../../hamar_agent/ollama_provider.py), [kildekontrollene](../../hamar_agent/portal_sources.py) og [leverandørdokumentasjonen](../provider-configuration.md). [Kravmatrisen](../assignment-requirements-matrix.md) gir oppgavekontekst, men dens historiske vurderinger erstatter ikke dagens kodegjennomgang.

Et forsvarlig rapportutsagn er at prototypen demonstrerer lokal gjenfinning, modellbasert avsnittsvalg og etterfølgende kontroll med tydelige avslag i et avgrenset materiale. Resultatene dokumenterer ikke generell sannhetsgaranti, full kommunal dekning eller fullstendig sikkerhet. Teksten er utarbeidet med kodeassistent og må vurderes faglig av studentene før innlevering.

### Publiseringspresisering

Klikkbare primærlenker peker nå til kontrollerte arkivkopier under `resultat/logger/historisk/`. Arkivets rålogger er byteidentiske med originalene; originalene i `output/` er ikke endret. Det historiske kjøringsregisteret er et tydelig merket, feltsanert utdrag som utelater konto-, forfatter- og maskinstimetadata. Den aktive kommunale katalogen er ikke publisert eller fornyet.

For kontroll uten den lokale katalogen kan `python -X utf8 docs/reports/verify_evidence.py --archive-only --output NY-evidens.json` brukes. Dette validerer historiske sitater mot de uendrede godkjente avsnittshashene og autoriserer ikke ny kildebruk eller inferens etter godkjenningens utløp. Historiske kommandoer og målinger ovenfor er bevart som historiske, ikke omskrevet til nye forsøk.
