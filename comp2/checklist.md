# Compulsory 2 — krav- og innleveringskontroll

Autoritet: `docs/official-assignment-user-supplied.md`, §§1–2. Status gjelder den dokumenterbare pakken, ikke en garanti for faglig godkjenning. Endelig innlevering: **IKKE KLAR**. Tabellen blander ikke Compulsory 2 med ukjente sluttprøvekrav.

| Krav og oppgavested | Rapportsted | Kilde / verifikasjon | Status / neste handling |
|---|---|---|---|
| Lokalt tilbakevendende behov, §1 og §2 rapport | §§1–2 | README.md; SPEC.md; lokale tjenestekilder | VERIFIED som problemdefinisjon; ingen brukerundersøkelse hevdes |
| Målbrukere og konkret produkt, §2 rapport | §§2–3 | Offisiell lenke, helt avsnitt eller avvisning | VERIFIED som avgrenset design; behov ikke empirisk validert |
| Suksess og kontrollerbar korrekthet, §2 rapport | §3 | application.py; real_sources.py; evidence/archived-evidence-audit.json | VERIFIED for avsnittsstøtte, ikke faktuell sannhet |
| Arkitektur, kontekst, stadier og autonomi, §2 rapport | §§4–5; figur 1 | portal.py; ollama_provider.py; workflow.mmd | VERIFIED; ingen oppdiktede subagenter |
| Datofestet plan baklengs fra demonstrasjon, §2 rapport | §8 | Relativ plan D−21 til D | PARTIAL; faktisk demonstrasjons- og innleveringsdato må bekreftes |
| Risiko og tiltak, §2 rapport | §9 | Kildeutløp, personvern, evidens og budsjettbegrensning | VERIFIED som risikovurdering; alle risikoer er ikke løst |
| Repository-lenke, §2 rapport | §10 | https://github.com/powerNeron/innlandet-agentic-workflows | VERIFIED |
| Input og kontrollerbar output, teknisk minimum 1 | §§3,6 | CLI; syntetisk fixture; JSON og sitater | VERIFIED i eksisterende harness; ny kjøring i evidence/new-command-register.json |
| Flere stadier, teknisk minimum 2 | §§3–5 | Kildevalg → modell → verifikasjon → høyst én retting → ny verifikasjon | VERIFIED |
| Verktøybruk, teknisk minimum 3 | §§3–6 | Filer, indeks, Ollama HTTP, JSON | VERIFIED |
| Automatisk del, teknisk minimum 4 | §§3–6 | Orkestrator etter initiering | VERIFIED; kildegodkjenning er menneskelig |
| Reproduserbar ende-til-ende-kjøring, §2 skeleton | §6; comp2/README.md | CLI-kommandoer og nye utdata | VERIFIED for syntetisk modus hvis exit 0; reell modus krever privat lokal katalog og gyldighet |
| README og faktiske kontekstfiler, §2 skeleton | §6 | README.md, SPEC.md, AGENTS.md, fixtures/, source manifests | VERIFIED i repository; katalog følger ikke Git-klon |
| Ingen personopplysninger, §1 begrensninger | §9 | Nåværende lokal kildegrense; blokkert HTML-henting | PARTIAL for historisk prosess: tidligere transient HTML må avklares; ny pakke skal ikke inneholde persondata |
| Respekter kilder, §1 begrensninger | §§4,9 | URL-/avsnittsspesifikke godkjenninger; eksakt utvalg | VERIFIED som nåværende begrensning; fornyelse er blokkert og utløp beholdt |
| Engelsk hovedrapport, §2 format | main.tex | Engelsk tekst i alle ti seksjoner | VERIFIED ved kildegjennomgang |
| Utlevert NeurIPS-mal og preprint, §2 format | main.tex | Riktig usepackage; ingen sty-fil funnet | PARTIAL; innhent faktisk utlevert neurips_2025.sty og kompiler |
| Hovedtekst 3–4 sider, §2 format | maintextend-etikett | Ingen PDF; ingen kompilator funnet | MISSING; kompiler og tell hovedsider |
| Ingen NeurIPS-sjekkliste, §2 format | main.tex | Kun egne fagseksjoner og vedlegg | VERIFIED i kilde |
| Obligatorisk vedlegg, §2 format | Vedlegg A–B | main.tex; appendices/ | VERIFIED som utkast; møteinnhold mangler |
| Representative ekte promptutdrag ≤2 sider, §2 vedlegg | Vedlegg A | Eksisterende genuine sitater; docs/prompt-log.md sammendrag | PARTIAL; studentene bør bekrefte representativitet; PDF-lengde må måles |
| Ekte møter og iterative beslutninger, §2 vedlegg | Vedlegg B | appendices/meeting_reports.md; åtte kandidatnotater | MISSING som bekreftede møtereferater; ikke fabrikkert |
| Figurer, tabeller og referanser er korrekte | §§4,7,10 | En felles datasetfil; SHA-256 på utvalgte originaler | VERIFIED maskinelt av verify_package.py; PDF-layout ikke verifisert |
| Tospråklige tall, brukerkrav | tables/ | Felles JSON; identiske tall/dato/kildereferanser | VERIFIED maskinelt |
| Original app, resultat/, kilder og historikk uendret | Hele arbeidet | Pakke-manifest; Git diff/status | Må etterkontrolleres før eventuell commit; bare comp2/ er autorisert |

## Kritiske gjenstående handlinger

1. Innhent den utleverte NeurIPS 2025-malen og et tilgjengelig LaTeX-miljø; kompiler og kontroller PDF visuelt.
2. Juster teksten til 3–4 hovedsider og verifiser promptvedlegg på maksimalt to sider. Ingen sidetall er antatt fra ordmengde.
3. Bekreft demonstrasjonsdato, faktisk innleveringsdato og en realistisk datofestet milepælsplan.
4. Dokumenter bare møter som faktisk fant sted og iterative begrunnelser; avklar hvordan møtedokumentasjon kan oppfylle personverngrensen.
5. Avklar historisk behandling av rå HTML opp mot oppgavens personvernkrav, og hvordan lovlig reproduksjon av godkjent katalog skal skje etter utløp. Ikke endre datoer.
6. Kjør ny pakkeaudit og kildeintegritetskontroll. Først når obligatoriske krav er verifisert, kan betinget autorisert commit og push gjennomføres.

Detaljert stresstesting, to av fire perturbasjonsklasser og krav om åtte møter er ikke spesifisert i den tilgjengelige Compulsory 2-teksten. Slike eventuelle sluttprøvekrav finnes ikke oppfunnet i denne sjekklisten.
