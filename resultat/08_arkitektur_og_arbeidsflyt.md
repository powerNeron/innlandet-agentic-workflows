# Problem, arkitektur og kontekst

Problem: innbyggere må finne og vurdere kommunal tjenesteinformasjon. Prototypen samler søk og avgrensede kildeutdrag med offisielle lenker; nytte er en hypotese, ikke dokumentert samfunnseffekt. Suksess i denne evalueringen betyr riktige tekniske tilstander, eksakt avsnittsstøtte og trygge avslag, ikke generell faktakorrekthet.

Kontekst: systemregler om ubetrodd kildetekst, utvalgte godkjente avsnitt, JSON-kontrakt og eventuelle saniterte verifikasjonsfunn. Brukerens frie spørsmål sendes ikke til realadapteren. Søk og regelbaserte porter bestemmer avsnittsutvalget. Modellen velger ett helt avsnitt; den skriver ikke et fritt semantisk verifisert sammendrag.

Trinn: inndatakontroll → lokal kataloggjenfinning og gyldighet → evidensport → lokal modell → uavhengig verifikasjon → høyst én korreksjon → ny kontroll → kildebasert svar. Ett spørsmål utløser disse trinnene automatisk. Verktøyene er filer, deterministisk søkeindeks og lokal HTTP-modell, ikke en fri shell-agent. Mennesket godkjenner kildemateriale før opptak og bestemmer om et faktisk kildevedlikehold er lovlig. Ingen ny kildeaktivering skjer automatisk.

Kjøreoppsett: Windows 11, Python 3.12.10, Ollama 0.40.8, llama3.2:3b, temperatur 0, seed 0, num_predict 700, 90 s socket-timeout i testene. Ingen ny avhengighet ble installert. Se logger/miljo.json. Diagram: norsk/figurer/03_workflow.mmd.
