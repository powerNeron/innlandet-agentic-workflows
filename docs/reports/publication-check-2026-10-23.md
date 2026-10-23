# Kontroll før deling av rapportgrunnlaget

Denne integreringen gjelder rapporter, evidens, figurer og verifikasjonsskript. Ingen app-, merkevare-, modell- eller kildegodkjenningsendring er inkludert. De tidligere resultatene er ikke nye eksperimenter og blir ikke omskrevet.

## Kontroller

- `python -X utf8 resultat/publish_bilingual.py`: eksisterende språkpublisering kontrolleres uten å overskrive målinger eller rålogger.
- `python -X utf8 resultat/audit_package.py`: datalikhet, CSV-er, figurdatasett, numeriske tekstverdier, kildelenker og kilde-/kodeintegritet kontrolleres. Generert inventar og filmanifest oppdateres før staging.
- `python -X utf8 docs/reports/verify_evidence.py --output <midlertidig>/local.json`: eksisterende 282 offline-tester, 23 Ollama-tilfeller, 17 lagrede positive svar og 13 nettlesertilfeller etterkontrollert. Utdata ligger midlertidig og erstatter ikke original evidens.
- Samme kommando med `--archive-only` kontrollerer det historiske arkivet uten å lese den aktive katalogen eller bruke lokale `output/`-logger.
- `python -X utf8 resultat/archive_evidence.py --check`: arkivkopier kontrolleres bytevis og mot bevarte SHA-256-verdier.
- En ren midlertidig kopi av de staged Git-filene, uten lokale `output/`-filer og uten aktiv katalog, bestod språkpublisering, rapportaudit og arkivbasert evidenskontroll. Alle klikkbare Markdown-evidenslenker fungerte i kopien. Her kan 42 historiske filhasher kontrolleres; den utelatte aktive katalogens hash kan bare kontrolleres lokalt. De opprinnelige 43 hashene ble kontrollert i arbeidskopien.

## Avgrensninger og publiseringsvalg

Begge språkversjonene, det felles datasettet, tabeller, figurer, metodetekster og rå målelogger inngår. Valgte historiske logger følger med som byteidentiske kopier slik at rapportens klikkbare referanser også virker i det delte repoet. Kun et eksplisitt feltsanert utdrag av det eldre kjøringsregisteret følger med; person-/kontometadata er utelatt. Originalregisteret endres ikke.

Den aktive kommunale katalogen, rå HTML, nettleserprofiler, Python-cache, lokale konfigurasjoner og midlertidige revisjonsutdata er utelatt. Rapportarkivets filbytes beskyttes mot automatisk linjeskiftkonvertering gjennom `resultat/.gitattributes`. Datasettet `resultat/data/shared.json` må stages eksplisitt fordi prosjektets generelle `data/`-regel ellers ignorerer det.

Kode-/kontekstfiler kan ved Git-checkout skifte mellom CRLF og LF. En separat baseline tillater bare denne dokumenterte linjeskiftforskjellen for slike filer; historiske målelogger sammenlignes fortsatt byteidentisk. Kontroll av en allerede publisert pakke er lesebasert, mens `audit_package.py --refresh` oppdaterer generert inventar før staging. Overflødige linjeavsluttende mellomrom i genererte SVG-filer ble fjernet uten endring av koordinater, måledata eller bilderesultater.

Oppstartsdiagnosen er relevant og publiseres med den lokale kontospesifikke Python-stien utelatt. Tidspunkter, målte varigheter, miljøforskjellen og usikkerheten i årsaksanalysen er bevart.

Kravmatrisens åpne krav forblir åpne: dette er ikke en erklæring om full eksamensberedskap, global nødstopp, aggregert token-/kostnadsbudsjett, bekreftede åtte møter eller dekning av manglende offisielle feilklasser. Ingen kildeutløp er endret.
