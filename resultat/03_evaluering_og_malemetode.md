# Evaluering og målemetode

Offline-tester blokkerer sockets og DNS. Reelle modelltester bruker kun godkjent lokal katalog og Ollama på loopback. Feilinjeksjon skjer i nye prosesslokale testinstanser med oppdiktet tekst; ingen godkjent kilde endres. Testfixture merkes eksplisitt som syntetisk i forsøksloggen selv når realadapterens ikke-syntetiske kodebane simuleres. Nettlesertester er automatiserte Chrome-forsøk, ikke en menneskelig brukerstudie.

Enheten er henholdsvis unittest, kuratert spørsmål, HTTP-forespørsel, modellkall eller sikkerhetsegenskap. Disse skal ikke summeres til én suksessrate. Modelltilfellene er gjenbrukte tjenestespørsmål, ikke uavhengige tilfeldige observasjoner. p95 bruker nearest-rank: sortert observasjon ceil(0.95*n). Vi oppgir ikke populasjonskonfidensintervall fra dette avhengige utvalget.

M2 måler veggklokketid rundt portal.answer; M1s provider_latency_ms måler arbeidsflyt inklusive kontroll. HTTP-søketiden inkluderer klient/server, men ingen modell. Ollamas varighetsfelt har enhet ns. Samtidige tokenposter følger fullføringsrekkefølge og er ikke koblet vilkårlig til en forespørselsindeks. Måleinstrumentering og GPU-stopp finnes bare i evalueringsskriptet.

Forsøkene var ikke forhåndsregistrert eksternt. Kriteriene ble kodet før den aktuelle kjøringen. Den separat lagrede holdout-filen er allerede kjent i prosjektet og er derfor ingen ny blindtest. Ingen ny kjøring ble gjort for språkoversettelsen. Se run_experiments.py og logger/kommandoer.jsonl.
