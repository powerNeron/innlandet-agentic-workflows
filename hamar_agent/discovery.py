"""Topic-neutral candidate discovery; candidates never confer evidence rights.

No network client, credential loading or implicit domain grant lives here. A
reviewed discovery profile and the existing pinned/robots transport are required
even for navigation. Raw labels, paths and query terms stay request-local.
"""
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re
from threading import RLock
import unicodedata
from weakref import WeakKeyDictionary
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree


_STOP = frozenset(('hva hvilke hvilken hvor hvordan når hvem hva heter what which where how when who '
    'i in om for fra og and the en et til er is are kan can du you jeg vi do does '
    'fortell tell me beskriv describe finner finne kommunen kommunens kommunal kommunale '
    'kommune innlandet informasjon opplysninger fiktiv fiktivt syntetisk offentlig '
    'ønsker trenger vil hjelp man om det dette tjenesten tjeneste søker søke søknad søknader '
    'søknadsfrist frist frister pris priser gebyr gebyrer koster gjelder gjør gjøre '
    'publisert omtalt sier beskriver generelle oppført finnes heter kort neste år hvilken').split())


def query_terms(question, municipality=None, *, limit=24):
    """Local lexical terms, not a non-personal-data certificate or remote query."""
    from .question_router import canonical_question
    text=canonical_question(question)
    if municipality:
        for name in (municipality.name,*municipality.aliases):
            text=re.sub(r'(?<!\w)'+re.escape(name)+r'(?!\w)',' ',text,flags=re.I)
    text=unicodedata.normalize('NFKC',text).casefold()
    return tuple(dict.fromkeys(w for w in re.findall(r'[^\W\d_][\w-]{2,39}',text) if w not in _STOP))[:limit]


def relevance(question, text, municipality=None):
    """Bounded transparent lexical ranking, not semantic truth verification."""
    need=query_terms(question,municipality)
    words=query_terms(text,municipality,limit=256)
    return sum(1 for term in need if any(term==w or min(len(term),len(w))>=5
        and (term.startswith(w) or w.startswith(term)) for w in words))


_PROCEDURE_WORD=r'(?:søk(?:e[rs]?|jer|je|jast)?|søknad\w*|skjema\w*|send\w*|fyll\w*|ut|lever\w*|apply|applies|applying|applications?|forms?|submit\w*|complet(?:e\w*|ing))'
_SCOPE_NEUTRAL=frozenset(('slik digital digitalt digitale elektronisk elektroniske online '
    'søknadsinformasjon kontakt kontaktinformasjon veiledning guidance guide information contact '
    'feilmelding feilmeldinger melding rapportering reporting report complaint klage '
    'vilkår krav kriterier målgruppe eligibility conditions requirements tilbud tilbudet tjeneste tjenesten '
    'ordning ordningen denne dette den det de this that the service services offer scheme '
    'plass plassen plasser place places få fa get obtain receive tilgang adgang access '
    'å at av of med ved via på hos fra frå from with to through using for om about '
    'en ei et eit a an som only kun bare berre kan skal må bør blir vert is are must can be '
    'og eller and or need trenger treng behøver use bruke bruk gjøre').split())
_REFERENCE_WORDS=frozenset(('du you jeg eg i we vi for å korleis hvordan how to '
    'din ditt dine your the det dette denne den som which that through '
    'måten slik søker søkje søkjar søkast sendast fyllast levert levertes sent '
    'is are be been being can must should may will shall kan skal må bør blir vert '
    'en ei et eit a an ved med via gjennom inn ut in out til for om av få '
    'ønsker ønskjer want wants tilgang adgang bruke brukes bruka brukt '
    'søknadsskjema søknadsskjemaet søknadsskjemaer papirskjema papirskjemaet '
    'tjenesteside tjenestesiden nettside nettsiden hjemmeside nettsted nettstedet '
    'vanligvis vanlegvis usually forklarer forklarar beskriver omtaler explains describes '
    'krever krev requires require completed fill filled filling opptak innmelding admission enrollment '
    'generell generelle general vurdering assessment viser steg oss har has have egen eget egne '
    'tema temaet topic theme omtales separat separate separately mentioned discussed '
    'nettportal nettportalen portal portalen portals skjemaet skjema skjemaene '
    'digitalt digitale digital elektronisk elektroniske online '
    'post posten postalt mail postal veiledning rettleiing hjelp guidance '
    'kontakte kontakt kontakter contact contacting ta fylle fyller fylles fylt '
    'tilbudet tjenesten tenesta ordningen service offer scheme plass plassen '
    'fastboende busette residents kun bare berre only gjelder gjeld '
    'ikke ikkje not trenger treng behøver need require without uten '
    'innen før etter before after within på hos frå fra from og eller and or').split())
_INSTITUTION_WORD=re.compile(r"(?:[^\W\d_][\w-]*)?(?:kontor(?:et)?|administrasjon(?:en)?|avdeling(?:en|a)?|etat(?:en)?|kommune(?:n)?|enhet(?:en|a)?|office|department|administration|authority|agency|council|municipality)(?:s|['’]s)?",re.I)


def _implicit_application_reference(text,municipality,*,topic=lambda value:False):
    """Fail closed on unresolved subjects/objects in a procedure clause.

    This is grammatical vocabulary and institutional roles, not services. It
    cannot grant relevance; the caller must also prove a matching topic.
    Preserve the complete original unit, including any conditions, on admission.
    """
    from .question_router import CALENDAR_WORDS
    return all(word in _REFERENCE_WORDS or word in _SCOPE_NEUTRAL or word in CALENDAR_WORDS
        or re.fullmatch(_PROCEDURE_WORD,word,re.I) or _INSTITUTION_WORD.fullmatch(word) or topic(word)
        for word in query_terms(text,municipality,limit=256))


def _application_targets(text):
    """Explicit application purposes, independent of pronouns and voice.

    These are grammatical heads/relations, never a list of municipal services.
    Return complete purpose phrases so a modifier cannot hide another object.
    """
    from .live_research import procedural_text
    markers=[r'\b(?:plass(?:en|er)?|places?)\s+(?:i|på|in|at|for)\s+',
        r'\b(?:gjelder|gjeld|angår|vedrører|concerns?|relat(?:es?|ed|ing)\s+to|(?:bruk\w*|nytt\w*)\s+til|(?:used|intended)\s+for)\s+',
        r'\b(?:angående|vedrørende|vedrørande|regarding|concerning|når|dersom|hvis|when|if)\s+',
        r'\b(?:søk(?:er|e|jer|je)?|apply|applies|applying)\s+(?!(?:ved|via|med|gjennom|with|using|through)\b)']
    # Inspect purpose relations throughout application prose, not just a
    # fixed verb bridge: adverbs, voice or pronouns must not hide an object.
    if procedural_text(text):
        markers.append(r'\b(?:for|om|til|to|about|regarding|concerning|angående|vedrørende|vedrørande)\s+')
    for marker in markers:
        for match in re.finditer(marker,text,re.I):
            tail=text[match.end():]
            tail=re.split(r'[.!?;|]|\b(?:for|om|til|to|about|gjennom|via|ved|through|using|skal|må|must|should|har|have|has|contains?|containing|includes?|including|omtaler|beskriver|forklar\w*|explains?|describes?)\b|,\s*(?=(?:send|lever|submit|complete|fyll)\b)',tail,maxsplit=1,flags=re.I)[0]
            for phrase in re.split(r'\s+(?:og|eller|and|or)\s+|,',tail,flags=re.I):
                if phrase.strip():yield phrase.strip()


def _asserted_service_text(text):
    """A closed cross-reference is not an assertion of the referenced topic.

    Project only for service attribution/ranking. Never edit the source unit
    returned to privacy, conditions, dates, claim checks or the user.
    """
    from .live_research import procedural_text
    reference=(r'\s*(?:[^\W\d_][\w-]*\s+){0,7}[^\W\d_][\w-]*\s+'
        r'(?:beskrives|omtales|nevnes|(?:is|are)\s+(?:mentioned|discussed|described))\s+'
        r'(?:separat|separately|i\s+(?:den\s+)?samme\s+(?:veiledningen|dokumentet|artikkelen)|'
        r'in\s+(?:the\s+)?same\s+(?:guide|document|article))\s*')
    chunks=re.split(r'([.!?;|])',text)
    return ''.join('' if i%2==0 and re.fullmatch(reference,chunk,re.I)
        and not procedural_text(chunk) else chunk for i,chunk in enumerate(chunks))



def source_path_priority(question,url,municipality=None):
    """Rank URL candidates without treating URLs as factual evidence."""

    question=explicit_overview_subject(question) or question
    import unicodedata
    from urllib.parse import urlsplit,unquote
    from .research import FEE_INTENT
    from .question_router import service_alias_text

    parts=urlsplit(url)

    if not FEE_INTENT.search(question):
        if re.search(
            r'(?:^|/)(?:faq-prisliste[^/]*|prisliste[^/]*|'
            r'priser(?:-[^/]*)?|gebyrer(?:-[^/]*)?)(?:/|$)',
            parts.path.casefold()
        ):
            return 0

    def fold(value):
        value=value.casefold().replace('\u00f8','o').replace('\u00e6','ae')
        return ''.join(
            c for c in unicodedata.normalize('NFKD',value)
            if not unicodedata.combining(c)
        )

    ignored=set("""
        jeg du vi det dette hva hvor hvordan hvem
        hvilken hvilket hvilke slags vil kan skal ma bor
        kommune kommuner tjeneste tjenester informasjon
        soker soke soknad soknaden
        pris priser koster betaling vilkar krav frist
        gjore gjor gjores fungerer ordne
        i pa til for om med fra og eller en et
        the a an how what where who can should
        information service services
    """.split())

    modifiers=set("""
        kommunal kommunale offentlig offentlige
        melder melde kontakter kontakte
        bygge bygger flytte flytting
    """.split())

    def words(value):
        value=service_alias_text(value)
        value=re.sub(r'[-_]+',' ',value)

        result={
            fold(w) for w in query_terms(
                value,municipality,limit=128
            )
        }-ignored

        # Preserve meaningful institutional qualifiers.
        if re.search(r'\bkommunal(?:e)?\b',value,re.I):
            result.add('kommunal')

        return result

    wanted=words(question)

    segments=[
        unquote(s).replace('-',' ').replace('_',' ')
        for s in parts.path.split('/') if s
    ]

    if not wanted or not segments:
        return 0

    topics=wanted-modifiers

    if not topics:
        topics=wanted

    qualifiers=wanted-topics

    def stem(word):
        for suffix in (
            'hetene','heter','elser','ene',
            'ende','er','en','et','n','a','s'
        ):
            if word.endswith(suffix) and len(word)-len(suffix)>=5:
                return word[:-len(suffix)]

        return word

    def similarity(a,b):
        if a==b:
            return 4

        if min(len(a),len(b))<5:
            return 0

        if stem(a)==stem(b):
            return 3

        if a.startswith(b) or b.startswith(a):
            return 2

        return 0

    leaf=words(segments[-1])
    complete=words(' '.join(segments))

    def score(requested,available):
        return sum(
            max(
                (similarity(a,b) for b in available),
                default=0
            )
            for a in requested
        )

    direct=score(topics,leaf)
    overall=score(topics,complete)

    if not overall:
        return 0

    qualification=score(qualifiers,leaf)

    extra=sum(
        not any(similarity(w,q) for q in wanted)
        for w in leaf
    )

    specialized=bool(
        re.search(r'\b(?:demens|kognitiv svikt)\b',segments[-1],re.I)
        and not re.search(r'\b(?:demens|kognitiv svikt)\b',question,re.I)
    )

    return max(
        1,
        20*direct
        +5*overall
        +3*qualification
        -min(12,2*extra)
        -8*specialized
    )


def official_href_candidates(raw,*,include_navigation=False,include_labels=False):
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.depth=0
            self.values={}
            self.labels={}
            self.active=None

        def handle_starttag(self,tag,attrs):
            if tag in ('main','article'):
                self.depth+=1

            if (
                tag!='a'
                or not (self.depth or include_navigation)
                or len(self.values)>=4096
            ):
                return

            hrefs=[
                value for name,value in attrs
                if name=='href'
            ]

            if len(hrefs)==1:
                href=hrefs[0]

                if isinstance(href,str) and 0<len(href)<=2048:
                    self.values[href]=None
                    self.active=href
                    self.labels.setdefault(href,'')

        def handle_data(self,data):
            if include_labels and self.active is not None:
                href=self.active
                self.labels[href]=(self.labels[href]+' '+data)[:512]

        def handle_endtag(self,tag):
            if tag=='a':
                self.active=None
            if tag in ('main','article'):
                self.depth=max(0,self.depth-1)

    parser=Links()
    parser.feed(raw.decode('utf-8-sig',errors='strict'))
    parser.close()
    if include_labels:
        return tuple(
            (href,' '.join(parser.labels.get(href,'').split()))
            for href in parser.values
        )
    return tuple(parser.values)



def linked_service_priority(question,url,municipality,label=""):
    from urllib.parse import quote

    parts=urlsplit(url)
    score=source_path_priority(question,url,municipality)

    def lexical_priority(value):
        if not value:
            return 0
        return source_path_priority(
            question,
            "https://candidate.invalid/"+quote(value,safe=""),
            municipality
        )

    score=max(score,lexical_priority(label))

    if parts.hostname!=municipality.official_host:
        host=(parts.hostname or "").removeprefix("www.").split(".")[0]

        for name in (municipality.name,*municipality.aliases):
            token=re.sub(r"[^\w]","",name.casefold())

            if token and host.startswith(token):
                host=host[len(token):].strip("-_")

            elif token and host.endswith(token):
                host=host[:-len(token)].strip("-_")

        score=max(score,lexical_priority(host))

    return score


def official_seed_candidates(question,entry):
    """Public navigation bootstrap, never a stored factual answer."""
    from urllib.parse import urlsplit

    catalog={
        'hamar':(
            '/helseogomsorg/',
            '/helseogomsorg/tjenester-til-hjemmeboende/',
            '/helseogomsorg/tjenester-til-hjemmeboende/dagopphold/',
            '/helseogomsorg/tjenester-til-hjemmeboende/dagopphold/dagopphold-for-eldre/',
            '/helseogomsorg/tjenester-til-hjemmeboende/dagopphold/dagopphold-for-personer-med-demens/',
            '/politikk-og-administrasjon/priser-kommunale-tjenester/'
        ),
        'elverum':(
            '/vare-tjenester/',
            '/vare-tjenester/helse-omsorg-og-sosiale-tjenester/',
            '/vare-tjenester/helse-omsorg-og-sosiale-tjenester/eldreomsorg/',
            '/vare-tjenester/helse-omsorg-og-sosiale-tjenester/eldreomsorg/dagsenter-for-mennesker-med-demens/'
        ),
        'gjovik':(
            '/tjenester/',
            '/tjenester/helse-og-omsorg/',
            '/tjenester/helse-og-omsorg/tjenester-i-helse-og-omsorg/tjenester-i-hjemmet/dagtilbud/',
            '/tjenester/helse-og-omsorg/tjenester-i-helse-og-omsorg/tjenester-i-hjemmet/dagtilbud/dagtilbud-etter-soknad/',
            '/kontakt/priser-og-gebyrer/'
        )
    }

    additions={'hamar': ('/helseogomsorg/tjenester-til-hjemmeboende/praktisk-bistand-daglige-gjoremal-og-personlig-assistanse/praktisk-bistand-daglig-gjoremal-hjemmehjelp/',), 'elverum': ('/vare-tjenester/helse-omsorg-og-sosiale-tjenester/hjemmetjenester/trygghetsalarm/',), 'gjovik': ('/tjenester/barnehage-og-skole/skole/skolefritidsordningen-sfo/sok-plass-i-sfo/',)}
    for city,paths in additions.items():
        catalog[city]=tuple(dict.fromkeys(
            (*catalog.get(city,()),*paths)
        ))

    urls=[
        'https://'+entry.official_host+path
        for path in catalog.get(entry.id,())
    ]

    ranked=sorted(
        (
            url for url in urls
            if urlsplit(url).hostname==entry.official_host
            and source_path_priority(question,url,entry)>0
        ),
        key=lambda url:(
            -source_path_priority(question,url,entry),
            url
        )
    )

    return tuple(ranked[:3])



def source_link_label(url):
    from urllib.parse import urlsplit,unquote
    parts=urlsplit(url)
    path=parts.path.rstrip('/').rsplit('/',1)[-1]
    label=unquote(path).replace('-',' ').replace('_',' ')
    label=re.sub(r'\.(?:html?|aspx?)$','',label,flags=re.I)
    label=' '.join(label.split())

    if not label:
        return parts.hostname

    return label[:1].upper()+label[1:100]



def official_phone_records(raw):
    from html.parser import HTMLParser

    if not isinstance(raw, bytes) or len(raw)>524288:
        return ()

    offices=(
        r'(?:kommunens\s+)?(?:sentralbord(?:et)?|'
        r'servicetorg(?:et)?|innbyggertorg(?:et)?|'
        r'servicekontor(?:et)?|tjenestekontor(?:et)?|'
        r'tildelingskontor(?:et)?|forvaltningskontor(?:et)?|'
        r'koordinerende enhet|kontor for tjenestetildeling)'
    )

    phone_pattern=r'(?:\+47\s*)?[23567]\d(?:\s?\d{2}){3}'

    pattern=re.compile(
        r'(?P<label>'+offices+r')'
        r'\s*(?:telefon(?:nummer)?|tlf\.?|ring)?'
        r'\s*[:\-]?\s*(?P<number>'+phone_pattern+r')'
        r'\s*[.]?',
        re.I
    )

    def number(value):
        digits=re.sub(r'\D','',value)

        if len(digits)==10 and digits.startswith('47'):
            digits=digits[2:]

        return (
            digits
            if re.fullmatch(r'[23567]\d{7}',digits)
            else None
        )

    class ContactParser(HTMLParser):
        blocks={'p','li','div','address','dd'}

        void={
            'br','hr','img','input','meta','link',
            'area','base','col','embed','param',
            'source','track','wbr'
        }

        excluded={
            'script','style','head','template',
            'form','noscript','dialog','details'
        }

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack=[]
            self.records={}

        def handle_data(self,data):
            for frame in self.stack:
                if frame['capture']:
                    if len(frame['text'])+len(data)>400:
                        frame['bad']=True
                    else:
                        frame['text']+=data

        def handle_starttag(self,tag,attrs):
            attributes=dict(attrs)

            blocked=bool(
                len(attributes)!=len(attrs)
                or tag in self.excluded
                or 'hidden' in attributes
                or 'inert' in attributes
                or str(attributes.get('aria-hidden','')).lower()=='true'
                or any(k.startswith('on') for k in attributes)
                or re.search(
                    r'display\s*:\s*none|visibility\s*:\s*hidden',
                    attributes.get('style') or '',re.I
                )
                or re.search(
                    r'\b(?:hidden|d-none|is-hidden|visually-hidden)\b',
                    attributes.get('class') or '',re.I
                )
                or self.stack and self.stack[-1]['blocked']
            )

            if blocked:
                for frame in self.stack:
                    if frame['capture']:
                        frame['bad']=True

            if tag in self.void:
                if tag=='br':
                    self.handle_data(' ')
                return

            if len(self.stack)>=128:
                raise ValueError('Excessive nesting')

            href=attributes.get('href') or ''
            phone=None

            if tag=='a' and re.fullmatch(
                r'tel:\+?[\d ]{8,14}',href,re.I
            ):
                phone=number(href[4:])

            self.stack.append(dict(
                tag=tag,
                blocked=blocked,
                bad=blocked,
                capture=tag in self.blocks or tag=='a',
                text='',
                phone=phone,
                phones=[]
            ))

        def handle_startendtag(self,tag,attrs):
            self.handle_starttag(tag,attrs)

            if tag not in self.void:
                self.handle_endtag(tag)

        def handle_endtag(self,tag):
            index=next((
                i for i in range(len(self.stack)-1,-1,-1)
                if self.stack[i]['tag']==tag
            ),None)

            if index is None:
                return

            frame=self.stack[index]

            if index!=len(self.stack)-1:
                frame['bad']=True

            self.stack=self.stack[:index]

            if frame['bad'] or frame['blocked']:
                return

            text=' '.join(frame['text'].split())

            if tag=='a' and frame['phone']:
                if (
                    re.fullmatch(phone_pattern,text)
                    and number(text)==frame['phone']
                ):
                    for parent in self.stack:
                        if parent['tag'] in self.blocks:
                            parent['phones'].append(frame['phone'])
                return

            if tag in self.blocks:
                match=pattern.fullmatch(text)

                if not match:
                    return

                phone=number(match['number'])

                if phone and frame['phones']==[phone]:
                    self.records[phone]=dict(
                        label=match['label'],
                        number=phone,
                        text=text
                    )

    parser=ContactParser()

    try:
        parser.feed(raw.decode('utf-8-sig'))
        parser.close()
    except (UnicodeError,ValueError):
        return ()

    return tuple(parser.records.values())



def _previous_guidance_kind(text):
    from .question_router import intent_evidence,navigation_only
    from .live_research import procedural_text

    leaf=text.rsplit(" | ",1)[-1].strip()

    if navigation_only(text):
        return "navigation"

    if intent_evidence(text,"price"):
        return "price"

    if intent_evidence(text,"deadline"):
        return "deadline"

    if intent_evidence(text,"hours"):
        return "hours"

    if (
        len(leaf.split())>=4
        and (
            intent_evidence(text,"application")
            or procedural_text(text)
        )
    ):
        return "application"

    if re.search(
        r"\b(?:m\u00e5lgruppe\w*|beregnet|"
        r"vilk\u00e5r\w*|kriterier|krav|"
        r"forutsetning\w*|gjelder bare)\b",
        text,re.I
    ):
        return "eligibility"

    if re.search(
        r"\b(?:bes\u00f8ksadresse|adresse|ligger)\b",
        leaf,re.I
    ):
        return "location"

    if named_service_places(text):
        return "location"

    return "overview"


def guidance_kind(text):
    from .question_router import procedural_evidence

    if has_service_location(text):
        return "location"

    result=_previous_guidance_kind(text)

    if (
        result=="application"
        and not procedural_evidence(text.rsplit(" | ",1)[-1])
    ):
        return "overview"

    return result


def select_guidance_documents(documents,question,limit=3):
    from .question_router import municipal_answer_intent

    documents=list(documents)

    if not documents:
        return documents

    intent=municipal_answer_intent(question)

    if intent!="overview":
        from .question_router import (
            requested_actions,procedural_evidence
        )

        if intent=="application" and "map" in requested_actions(question):
            eligible=[
                d for d in documents
                if d.tier==1 and d.supports_request
            ]

            procedure=next((
                d for d in eligible
                if procedural_evidence(d.text)
            ),None)

            locations=[
                d for d in eligible
                if has_service_location(d.text)
            ]

            selected=[]

            if procedure:
                selected.append(procedure)

                locations.sort(
                    key=lambda d:d.url!=procedure.url
                )

            if locations and locations[0] not in selected:
                selected.append(locations[0])

            for d in documents:
                if len(selected)>=limit:
                    break

                if d not in selected:
                    selected.append(d)

            return selected[:limit]

        return documents[:limit]

    # Select complementary evidence without increasing retrieval.
    tier=documents[0].tier

    candidates=[
        d for d in documents
        if d.tier==tier and d.supports_request
        and guidance_kind(d.text)!="navigation"
    ]

    if not candidates:
        return documents[:limit]

    selected=[]

    broad=bool(re.search(
        r"\b(?:hvilke|alle|oversikt|which|all)\b",
        question,re.I
    ))

    if broad:
        seen_urls=set()

        for d in candidates:
            if d.url not in seen_urls:
                selected.append(d)
                seen_urls.add(d.url)

            if len(selected)>=limit:
                return selected

    for kind in ("location","overview","application","eligibility"):
        if len(selected)>=limit:
            break

        candidate=next((
            d for d in candidates
            if guidance_kind(d.text)==kind
            and d not in selected
        ),None)

        if candidate is not None:
            selected.append(candidate)

    for d in candidates:
        if len(selected)>=limit:
            break

        if d not in selected:
            selected.append(d)

    return selected[:limit]


def _compose_municipal_guidance_base(
    question,documents,*,contacts=(),links=(),partial=False
):
    from .question_router import (
        municipal_answer_intent,requested_actions
    )

    intent=municipal_answer_intent(question)
    actions=requested_actions(question)

    labels={
        "overview":"Om tilbudet",
        "application":"Slik s\u00f8ker du",
        "eligibility":"Hvem tilbudet gjelder",
        "price":"Pris og betaling",
        "deadline":"S\u00f8knadsfrist",
        "hours":"\u00c5pningstider",
        "location":"Hvor finner du tilbudet"
    }

    missing={
        "application":"Jeg fant ikke en bekreftet s\u00f8knadsprosedyre.",
        "price":"Jeg fant ikke en bekreftet pris for tjenesten.",
        "eligibility":"Jeg fant ikke tilstrekkelige opplysninger om vilk\u00e5rene.",
        "deadline":"Jeg fant ikke en bekreftet s\u00f8knadsfrist.",
        "hours":"Jeg fant ikke bekreftede \u00e5pningstider.",
        "location":"Jeg fant ikke en bekreftet bes\u00f8ksadresse."
    }

    groups={}
    seen=set()
    titles=[]

    for document in documents:
        if document.tier!=1:
            continue

        value=document.text.strip()
        key=" ".join(value.casefold().split())

        if key in seen:
            continue

        seen.add(key)
        kind=guidance_kind(value)

        if kind=="navigation":
            continue

        if kind=="overview" and re.match(
            r'^\s*(?:at|og|eller|som)\s+',
            value.rsplit(" | ",1)[-1],re.I
        ):
            continue

        parts=[
            part.strip()
            for part in value.split(" | ")
            if part.strip()
        ]

        if not parts:
            continue

        if len(parts)>1:
            titles.append(parts[0])

        groups.setdefault(kind,[]).append(parts)

    common_title=(
        titles[0]
        if titles and len(set(titles))==1
        else None
    )

    sections=[]

    has_phone=any(
        link.get("public_phones")
        for link in links[:4]
    )

    has_map=any(
        link.get("map_query")
        for link in links[:4]
    )

    # Direct contact requests take priority over general prose.
    if "contact" in actions:
        sections.append(
            "Kontakt\nBruk ringelenken nedenfor."
            if has_phone else
            "Jeg fant ikke et bekreftet offentlig telefonnummer."
        )

    if intent=="overview":
        order=[
            "overview","eligibility","application",
            "location","hours","price","deadline"
        ]
    else:
        order=[intent]

        # Preserve available qualifying information.
        if intent in ("application","price","deadline"):
            order.append("eligibility")

    if "map" in actions and "location" not in order:
        order.append("location")

    if intent in missing and not groups.get(intent):
        sections.append(missing[intent])

        for supporting_kind in ('overview','eligibility','location'):
            if (
                intent in ('application','location') and groups.get(supporting_kind)
                and supporting_kind not in order
            ):
                order.append(supporting_kind)

    if common_title and any(groups.get(k) for k in order):
        sections.insert(0,common_title)

    for kind in order:
        rows=groups.get(kind,[])

        if not rows:
            continue

        body=[]

        for parts in rows:
            context=parts[:-1]
            leaf=parts[-1]

            if common_title and context[:1]==[common_title]:
                context=context[1:]

            # Identical headings need not be repeated.
            context=[
                c for c in context
                if c.casefold()!=labels[kind].casefold()
            ]

            line=(
                " - ".join(context)+":\n"
                if context else ""
            )+leaf

            if line not in body:
                body.append(line)

        sections.append(
            labels[kind]+"\n"+"\n\n".join(body)
        )

    if "map" in actions:
        sections.append(
            "Kart\nBruk kartlenken for \u00e5 finne tjenesten."
            if has_map else
            "Jeg fant ikke en kartlenke for dette oppslaget."
        )

    if not sections:
        sections.append(
            "Jeg fant en relevant kommunal side, "
            "men ikke tilstrekkelig informasjon til \u00e5 svare."
        )

    return "\n\n".join(sections)


def _application_navigation_notice_base(question,documents,links):
    from urllib.parse import urlsplit
    from .question_router import (
        municipal_answer_intent,procedural_evidence
    )

    if municipal_answer_intent(question)!="application":
        return ""

    if any(
        procedural_evidence(doc.text.rsplit(" | ",1)[-1])
        for doc in documents if doc.tier==1
    ):
        return ""

    official={
        doc.url for doc in documents if doc.tier==1
    }

    for link in links:
        if link.get("url") not in official:
            continue

        domain=urlsplit(link["url"]).hostname
        if not domain:
            continue

        domain=domain.removeprefix("www.")

        for form in link.get("application_actions",()):
            try:
                target=urlsplit(form["url"])

                if (
                    target.scheme!="https"
                    or not target.hostname
                    or target.username
                    or target.password
                    or target.port
                    or target.fragment
                    or not (
                        target.hostname==domain
                        or target.hostname.endswith("."+domain)
                    )
                ):
                    continue

            except (ValueError,TypeError,KeyError):
                continue

            return (
                "Du kan \u00e5pne kommunens s\u00f8knadsskjema "
                "ved \u00e5 trykke p\u00e5 s\u00f8knadslenken nedenfor. "
                "Jeg har funnet skjemaet p\u00e5 kommunens "
                "tjenesteside, men har ikke bekreftet alle "
                "vilk\u00e5rene for s\u00f8knaden."
            )

    return ""


def compose_municipal_guidance(
    question,documents,contacts=(),links=(),partial=False
):
    answer=_compose_municipal_guidance_base(
        question,documents,contacts=contacts,
        links=links,partial=partial
    )

    notice=application_navigation_notice(
        question,documents,links
    )

    if notice:
        answer=answer.replace(
            "Jeg fant ikke en bekreftet s\u00f8knadsprosedyre.",
            ""
        ).strip()

        return notice+("\n\n"+answer if answer else "")

    return answer



def _previous_named_service_places(text):
    """Extract explicit public facility names, never invent destinations."""

    found=[]

    for match in re.finditer(
        r'\b(?:tilbyr|finnes|holder til|ligger|lokalisert|har)\b'
        r'[^.!?|]{0,150}?\b(?:ved|p\u00e5|i)\s+'
        r'([^.!?;|]{3,200})',
        text,re.I
    ):
        parts=re.split(
            r',\s*|\s+og\s+(?=(?:\u00e9n\s+p\u00e5\s+|en\s+p\u00e5\s+)?[A-Z\u00c6\u00d8\u00c5])',
            match[1]
        )

        for value in parts:
            value=re.sub(
                r'^(?:\u00e9n|en)\s+p\u00e5\s+',
                '',value.strip()
            )

            if (
                3<=len(value)<=80
                and value[0].isupper()
                and re.fullmatch(
                    r'[^\W\d_][\w\s-]+',value,re.UNICODE
                )
                and re.search(
                    r'(?:senter(?:et)?|stue[n]?|sykehjem(?:met)?|'
                    r'sjukeheim(?:en)?|skole[n]?|barnehage[n]?|'
                    r'bibliotek(?:et)?|r\u00e5dhus(?:et)?|'
                    r'helsehus(?:et)?|hall(?:en)?)$',
                    value,re.I
                )
            ):
                found.append(value)

    return tuple(dict.fromkeys(found))[:5]


def named_service_places(text):
    original=_previous_named_service_places(text)

    if original:
        return original

    leaf=text.rsplit(' | ',1)[-1]

    match=re.search(
        r'\b(?:en|\u00e9n)\s+p\u00e5\s+'
        r'([^.!?;|]{3,100}?)\s+og\s+'
        r'(?:en|\u00e9n)\s+p\u00e5\s+'
        r'([^.!?;|]{3,100})(?:[.!?;|]|$)',
        leaf,re.I
    )

    if not match:
        return ()

    names=tuple(value.strip() for value in match.groups())

    if not all(
        name[0].isupper()
        and re.fullmatch(r'[^\W\d_][\w\s-]+',name)
        and re.search(
            r'(?:senter(?:et)?|sykehjem(?:met)?|stue[n]?)$',
            name,re.I
        )
        for name in names
    ):
        return ()

    return names


def named_service_areas(text):
    leaf=text.rsplit(' | ',1)[-1].strip()

    match=re.fullmatch(
        r'(?:slike tilbud|dagtilbud(?:et|ene)?|'
        r'dagaktivitetstilbud(?:et|ene)?)\s+'
        r'(?:finnes|tilbys)\s+(?:p\u00e5|i)\s+'
        r'([^.!?;|]{3,180})[.]?',
        leaf,re.I
    )

    if not match:
        return ()

    values=tuple(
        value.strip()
        for value in re.split(r',\s*|\s+og\s+',match[1])
    )

    if not 1<=len(values)<=8:
        return ()

    if not all(
        2<=len(value)<=50
        and value[0].isupper()
        and re.fullmatch(r'[^\W\d_][\w\s-]+',value)
        for value in values
    ):
        return ()

    return values


def has_service_location(text):
    return bool(
        named_service_places(text)
        or named_service_areas(text)
    )


def official_contact_seed(entry):
    paths={
        'hamar':'/innbyggerservice/',
        'elverum':'/vare-tjenester/om-kommunen/kontakt-oss/',
        'gjovik':'/kontakt-oss/'
    }

    path=paths.get(entry.id)

    return 'https://'+entry.official_host+path if path else None


def _public_page_actions_base(raw,entry,source_url):
    """Discover public browser actions from actual fetched HTML."""

    from html.parser import HTMLParser
    from urllib.parse import urljoin,urlsplit

    phones={
        'hamar':'62563000',
        'elverum':'62433000',
        'gjovik':'61189500'
    }

    class Parser(HTMLParser):
        void={
            'br','hr','img','input','meta','link','area',
            'base','col','embed','param','source','track','wbr'
        }

        excluded={
            'script','style','head','template','noscript',
            'dialog','nav','button','textarea','select','option'
        }

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack=[]
            self.text=[]
            self.links=[]

        def handle_starttag(self,tag,attrs):
            a=dict(attrs)

            blocked=bool(
                len(a)!=len(attrs)
                or tag in self.excluded
                or (
                    tag=='form'
                    and any(f['article'] for f in self.stack)
                )
                or 'hidden' in a
                or 'inert' in a
                or str(a.get('aria-hidden','')).lower()=='true'
                or re.search(
                    r'display\s*:\s*none|visibility\s*:\s*hidden',
                    a.get('style') or '',re.I
                )
                or self.stack and self.stack[-1]['blocked']
            )

            if tag in self.void:
                return

            if len(self.stack)>=128:
                raise ValueError('HTML nesting limit')

            self.stack.append(dict(
                tag=tag,blocked=blocked,
                href=a.get('href') or '',
                text=[],
                article=tag in ('article','main') or any(
                    f['article'] for f in self.stack
                )
            ))

        def handle_data(self,value):
            if self.stack and self.stack[-1]['blocked']:
                return

            self.text.append(value)

            for frame in self.stack:
                if frame['tag']=='a' and not frame['blocked']:
                    frame['text'].append(value)

        def handle_endtag(self,tag):
            index=next((
                i for i in range(len(self.stack)-1,-1,-1)
                if self.stack[i]['tag']==tag
            ),None)

            if index is None:
                return

            frame=self.stack[index]
            self.stack=self.stack[:index]

            if (
                tag!='a'
                or frame['blocked']
                or not frame['article']
            ):
                return

            label=' '.join(
                ''.join(frame['text']).split()
            )

            # A category/menu label is not an application action.
            if not re.match(
                r'^(?:s\u00f8k(?:e)?\b|papirs\u00f8knad\w*\b|'
                r's\u00f8knadsskjema\w*\b|'
                r'(?:\u00f8nsker|vil|kan)\s+du\b)',
                label,re.I
            ):
                return

            if not re.search(
                r'\b(?:s\u00f8k(?:e)?\s+(?:digitalt\s+)?om|'
                r's\u00f8k digitalt|papirs\u00f8knad\w*|'
                r's\u00f8k(?:e)?\s+(?:sfo[- ]+plass|'
                r'barnehage[- ]?plass|'
                r'plass\s+i\s+(?:sfo|barnehage))|'
                r's\u00f8knadsskjema\w*)\b',
                label,re.I
            ):
                return

            target=urljoin(source_url,frame['href'])
            parts=urlsplit(target)

            domain=entry.official_host.removeprefix('www.')

            if (
                parts.scheme!='https'
                or parts.username or parts.password or parts.port
                or parts.fragment or len(target)>1800
                or not parts.hostname
                or not (
                    parts.hostname==domain
                    or parts.hostname.endswith('.'+domain)
                )
                or re.search(r'[\x00-\x20\\]|%0[ad]',target,re.I)
                or len(label)>220
            ):
                return

            self.links.append(dict(
                url=target,
                label=label,
                source_url=source_url
            ))

    parser=Parser()

    try:
        parser.feed(raw.decode('utf-8-sig'))
        parser.close()
    except (ValueError,UnicodeError):
        return (),()

    contacts=list(official_phone_records(raw))

    known=phones.get(entry.id)

    if known:
        pattern=r'\s*'.join(known)

        visible=' '.join(' '.join(parser.text).split())

        match=re.search(
            r'\b(?:telefon(?:nummer)?|tlf\.?|ring(?:\s+oss)?(?:\s+p\u00e5)?|sentralbord(?:et)?)\s*:?\s*'
            r'(?:\+47\s*)?'+pattern+r'(?!\d)',
            visible,re.I
        )

        if match and not any(
            c['number']==known for c in contacts
        ):
            contacts.append(dict(
                label='Kommunens sentralbord',
                number=known,
                text=match[0]
            ))

    unique={
        row['url']:row
        for row in parser.links
    }

    return tuple(contacts),tuple(unique.values())[:4]


def _independent_static_section_dom(parsed,index,component_indices):
    """Prove an independently bounded static article section."""

    dom=getattr(parsed,'dom',{})

    if not dom or not parsed.dom_text:
        return False

    def norm(value):
        return ' '.join(value.split())

    def node_text(node):
        return norm(''.join(
            text for _,text in parsed.dom_text[
                node['text_start']:node['text_end']
            ]
        ))

    def visible(node):
        return bool(
            node.get('closed')
            and not any(
                node.get(key) for key in (
                    'ambiguous','hidden','parent_blocked',
                    'forbidden','stateful'
                )
            )
        )

    headings=[
        parsed.blocks[i] for i in component_indices
        if parsed.block_kinds[i]=='h2'
    ]

    if not headings:
        return False

    label=norm(headings[-1])
    leaf=norm(parsed.blocks[index])

    matches=[
        n for n in dom.values()
        if n['tag']=='h2'
        and visible(n)
        and node_text(n)==label
    ]

    if len(matches)!=1:
        return False

    heading=matches[0]
    parent=dom.get(heading.get('parent'))

    if not parent or not visible(parent):
        return False

    ancestor=parent
    inside_article=False

    for _ in range(64):
        if ancestor.get('tag')=='article':
            inside_article=True
            break

        ancestor=dom.get(ancestor.get('parent'))

        if not ancestor:
            break

    if not inside_article:
        return False

    start=heading['source_node']

    stop=min(
        (
            n['source_node']
            for n in dom.values()
            if n.get('parent')==heading.get('parent')
            and n['tag'] in ('h1','h2')
            and n['source_node']>start
        ),
        default=parent['end']+1
    )

    scoped=[
        n for n in dom.values()
        if start<=n['source_node']<stop
    ]

    if not any(
        n['tag'] in ('p','li')
        and visible(n)
        and node_text(n)==leaf
        for n in scoped
    ):
        return False

    for n in scoped:
        attrs=n.get('attrs',{})

        if (
            n['tag'] in (
                'form','input','textarea','select','button',
                'details','summary','fieldset','dialog'
            )
            or 'aria-controls' in attrs
            or n.get('stateful')
            or n.get('ambiguous')
            or any(
                key.startswith('on')
                for key in attrs
            )
        ):
            return False

        if n.get('hidden') and node_text(n):
            return False

    return True


def static_section_key(parsed,index,component_indices):
    import hashlib

    headings=sorted(
        i for i in component_indices
        if parsed.block_kinds[i]=='h2'
    )

    if not headings:
        return None

    value=(
        parsed.blocks[headings[-1]]+'\x00'+
        parsed.blocks[index]
    )

    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def capture_static_section_proofs(raw,parser_type):
    probe=parser_type(public_layout=True,disclosures=None)

    probe.feed(raw.decode('utf-8-sig'))
    probe.close()

    if not probe.dom or len(probe.blocks)>1500:
        return frozenset()

    proofs=set()
    headings={}

    for index,kind in enumerate(probe.block_kinds):
        owner=probe.block_owners[index]

        if kind=='h1':
            headings={
                k:v for k,v in headings.items()
                if k[:len(owner)]!=owner
            }

        elif kind=='h2':
            headings[owner]=index

        elif kind in ('p','li'):
            eligible=[
                h for path,h in headings.items()
                if owner[:len(path)]==path
            ]

            if not eligible:
                continue

            heading=max(eligible)
            indices={heading,index}

            if _independent_static_section_dom(
                probe,index,indices
            ):
                key=static_section_key(probe,index,indices)

                if key:
                    proofs.add(key)

    return frozenset(proofs)


def independent_static_section(parsed,index,component_indices):
    if getattr(parsed,'dom',None):
        return _independent_static_section_dom(
            parsed,index,component_indices
        )

    key=static_section_key(
        parsed,index,component_indices
    )

    return bool(
        key and key in getattr(
            parsed,'independent_section_proofs',()
        )
    )




def application_evidence_queries(question):
    from .question_router import (
        requested_actions,context_ellipse,
        municipal_answer_intent
    )
    from .research import FEE_INTENT

    if (
        municipal_answer_intent(question)!="application"
        or FEE_INTENT.search(question)
        or re.search(
            r"\d|\b(?:ikke|ikkje|not|frist|rettighet|regel)\w*\b",
            question,re.I
        )
    ):
        return question,None

    clauses=[
        part.strip()
        for part in re.split(r"[?!;]+|\.\s+",question)
        if part.strip()
    ]

    primary=[]
    topic=[]

    for clause in clauses:
        intent=municipal_answer_intent(clause)

        if context_ellipse(clause):
            if requested_actions(clause) and intent in (
                "overview","location"
            ):
                continue

            if intent=="application":
                primary.append(clause)
                continue

        primary.append(clause)
        topic.append(clause)

    if not topic or not primary:
        return question,None

    main=". ".join(primary)
    location=". ".join(topic)

    return (
        main,
        location if "map" in requested_actions(question)
        else None
    )




def explicit_service_application(
    question,text,municipality,document_heading,scope_text=None
):
    from .research import FEE_INTENT
    from .question_router import service_alias_text
    from .live_research import procedural_text

    if (
        municipality is None or not document_heading
        or FEE_INTENT.search(question)
        or not re.search(
            r'\b(?:hvordan|korleis)\s+s\u00f8k(?:er|e)\b',
            question,re.I
        )
        or re.search(
            r'\d|\b(?:ikke|ikkje|not|frist|rettighet|vilk\u00e5r|regel)\w*\b',
            question,re.I
        )
    ):
        return False

    parts=text.split(' | ')

    if (
        len(parts)!=3
        or parts[0]!=document_heading
        or scope_text not in (None,parts[-1])
        or not procedural_text(parts[-1])
    ):
        return False

    stop={
        's\u00f8k','s\u00f8ker','s\u00f8ke','s\u00f8knad',
        'slik','hvordan','jeg','du','om','plass',
        'etter','i','p\u00e5','og','\u00e5','f\u00e5','kan'
    }

    def terms(value):
        value=re.sub(
            r'(?<=\w)[-\u2010-\u2015](?=\w)',
            ' ',value.casefold()
        )

        return set(re.findall(
            r'\w+',service_alias_text(value).casefold()
        ))-stop

    title=terms(document_heading)
    requested=terms(question)

    if not title or not title<=requested:
        return False

    if not re.fullmatch(
        r'(?:slik s\u00f8ker du|s\u00f8knad|'
        r'hvordan s\u00f8ker (?:jeg|du)'
        r'(?: om [\w -]+)?\??)',
        parts[1],re.I
    ):
        return False

    section=terms(parts[1])

    if section and section!=title:
        return False

    leaf=parts[-1].strip()

    explicit=re.fullmatch(
        r'(?:du|man)\s+s\u00f8ker(?:\s+om)?'
        r'(?:\s+(?:\u00e5\s+)?f\u00e5)?\s+'
        r'([\w -]{2,100}?)\s+ved\s+\u00e5\s+'
        r'fylle\s+ut\s+'
        r'(?:(?:et|det|kommunens)\s+)?'
        r's\u00f8knads?skjema(?:et)?'
        r'(?:\s+for\s+helse-\s+og\s+omsorgstjenester)?[.]?',
        leaf,re.I
    )

    if explicit:
        subject=re.sub(
            r'^(?:mobil|stasjon\u00e6r)'
            r'(?:\s+eller\s+(?:mobil|stasjon\u00e6r))?\s+',
            '',explicit[1],flags=re.I
        )

        return terms(subject)==title

    portal=re.fullmatch(
        r'(?:du|man)\s+s\u00f8ker\s+om\s+plass\s+'
        r'(?:gjennom|via)\s+'
        r'barnehage-\s+og\s+sfo-portalen[.]?',
        leaf,re.I
    )

    return bool(
        portal and re.search(
            r'\bsfo\b|\bskolefritidsordning\w*\b',
            document_heading,re.I
        )
    )


def contextual_application_procedure(
    question,text,municipality,document_heading,scope_text=None
):
    from .research import FEE_INTENT
    from .question_router import service_families,service_alias_text

    if (
        municipality is None or not document_heading
        or FEE_INTENT.search(question)
        or not re.search(
            r'\b(?:hvordan|korleis)\s+s\u00f8k(?:er|e)\b',
            question,re.I
        )
        or re.search(
            r'\d|\b(?:ikke|ikkje|not|frist|rettighet|vilk\u00e5r|regel)\w*\b',
            question,re.I
        )
    ):
        return False

    if explicit_service_application(
        question,text,municipality,document_heading,scope_text
    ):
        return True

    parts=text.split(' | ')

    if (
        len(parts)!=3
        or parts[0]!=document_heading
        or not re.fullmatch(
            r'(?:slik s\u00f8ker du|hvordan s\u00f8ke|s\u00f8knad)',
            parts[1],re.I
        )
        or scope_text not in (None,parts[-1])
    ):
        return False

    title=re.sub(
        r'\baktivitetstilbud(?=\s+for\s+'
        r'(?:personer|mennesker)\s+med\s+'
        r'(?:demens|kognitiv svikt)\b)',
        'dagaktivitetstilbud',
        document_heading,flags=re.I
    )

    wanted=service_families(service_alias_text(question))
    available=service_families(service_alias_text(title))

    if len(wanted)!=1 or available!=wanted:
        return False

    leaf=parts[-1].strip()

    pattern=(
        r'(?:du|man)\s+s\u00f8ker\s+via\s+'
        r'(?:et|det|kommunens)\s+'
        r'(?:digitalt|digitale|elektronisk|elektroniske)\s+'
        r'(?:s\u00f8knads)?skjema(?:et)?'
        r'(?:\s+eller\s+ved\s+\u00e5\s+sende\s+inn\s+'
        r's\u00f8knaden\s+i\s+posten)?[.]?'
        r'(?:\s+skjemaet\s+m\u00e5\s+fylles\s+ut\s+med\s+'
        r'(?:sensitive\s+)?personopplysninger,\s*'
        r'derfor\s+m\u00e5\s+du\s+logge\s+deg\s+inn\s+med\s+'
        r'(?:MinID|BankID)(?:\s+eller\s+(?:MinID|BankID))?[.]?)?'
    )

    return bool(re.fullmatch(pattern,leaf,re.I))


def _original_content_relevance(question,text,municipality=None,*,url=None,document_heading=None,document_title=None,scope_text=None):
    """One service-scope decision before lexical, inflection or context credit.

    A title/heading nominates context; it cannot contradict the paragraph's
    explicit purpose. URLs discover candidates, not evidence of their topic.
    Existing privacy, complete-unit, date and monetary verification still run.
    """
    from .question_router import service_families,service_alias_text
    from .research import FEE_INTENT
    from .live_research import procedural_text,service_topics
    from .question_router import CALENDAR_WORDS
    critical=bool(FEE_INTENT.search(question) or re.search(r'\d|\b(?:gratis|frist\w*|regl\w*|vilkår|rettighet\w*|deadline\w*|rules?|conditions?|eligib\w*|rights?)\b',question,re.I))
    def terms(value):
        return tuple(w for w in query_terms(value,municipality,limit=256)
            if w not in _SCOPE_NEUTRAL and not re.fullmatch(_PROCEDURE_WORD,w,re.I))
    def stem(word):
        for suffix in ('hetene','heter','elser','ende','ene','ere','er','en','et'):
            if word.endswith(suffix) and len(word)-len(suffix)>=5:return word[:-len(suffix)]
        return word
    # Explicit excluded alternatives cannot donate topic credit, independently
    # of commas/conjunctions. A necessity question keeps its actual object.
    def excluded_alternative(match):
        before=question[:match.start()]
        necessity=r'(?:trenger|treng|behøver|need|require)'
        if (re.search(r'\b'+necessity+r'\s*(?:(?:jeg|eg|du|vi|i|you|we)\s*)?$',before,re.I)
                or re.match(necessity+r'\b',match[1],re.I)):return match[0]
        return ' '
    scope_question=re.sub(r'\b(?:ikke|ikkje|not)\s+([^,.;!?|]+?)(?=$|[,.;!?|]|\b(?:men|but)\b)',
        excluded_alternative,question,flags=re.I)
    need=terms(scope_question)
    if not need:return 0,'none'
    # Existing service aliases can relate two documented names of ONE service,
    # only for general guidance. Neither URL nor search/document title nominates
    # this bridge. Critical facts still need the original lexical verification.
    context_text=' | '.join((question,text,document_heading or ''))
    critical_context=bool(FEE_INTENT.search(context_text) or re.search(
        r'\d|\b(?:gratis|frist\w*|regl\w*|regel\w*|vilkår|betingels\w*|rett(?:en|er|ighet\w*)?|'
        r'nå|når|dato\w*|åpningstid\w*|deadline\w*|rules?|conditions?|eligib\w*|rights?|dates?|when|opening\s+hours)\b',context_text,re.I)
        or set(re.findall(r'\w+',context_text.casefold())) & CALENDAR_WORDS)
    requested_topics=service_topics(scope_question)
    same_service=bool(not critical and not critical_context and len(requested_topics)==1
        and document_heading and service_topics(document_heading)==requested_topics)
    alias_allowed=bool(
        municipality and not critical and not critical_context
        and len(service_families(scope_question))==1
    )
    def score(value,*,inflected=False,aliases=False):
        if aliases:
            requested=terms(service_alias_text(scope_question))
            published=terms(service_alias_text(_asserted_service_text(value)))
            return sum(
                any(n==w for w in published)
                for n in requested
            )
        wanted=tuple(stem(part) for w in need for part in w.split('-')) if inflected else need
        have=terms(_asserted_service_text(value))
        if inflected:have=tuple(stem(part) for w in have for part in w.split('-'))
        return sum(any(n==w or min(len(n),len(w))>=5 and (n.startswith(w) or w.startswith(n)) for w in have) for n in wanted)
    def topic(value):
        return score(value) or (score(value,inflected=True) if not critical else 0) or (
            score(value,aliases=True) if alias_allowed else 0) or (
            int(same_service and service_topics(_asserted_service_text(value))==requested_topics))
    def neutral_target(value):
        if re.match(r'\s*(?:(?:kun|bare|berre|only)\s+)?(?:fastboende|busette|innbyggere|personer|mennesker|elever|barn|voksne|eldre|brukere|residents|people|children|adults|users)\b',value,re.I):
            return True  # An eligibility group is retained, not a different service.
        return not terms(value) or _implicit_application_reference(value,municipality)
    parts=text.split(' | ')
    if scope_text is not None:
        # A proven static panel is one whole procedure/qualification unit.
        # Its internal paragraphs are not independent nomination headings.
        # Check its COMPLETE text through the same common scope guard.
        if not isinstance(scope_text,str) or not scope_text or not text.endswith(scope_text):return 0,'none'
        prefix=text[:-len(scope_text)]
        if prefix and not prefix.endswith(' | '):return 0,'none'
        parts=([*prefix[:-3].split(' | ')] if prefix else [])+[scope_text]
    leaf=parts[-1]
    from .question_router import navigation_only
    if scope_text is None and navigation_only(leaf):
        return 0,'none'
    if scope_text is None and re.fullmatch(
            r"\s*(?:tips en venn|skriv ut|del siden|"
            r"del p\u00e5 facebook|del p\u00e5 x|"
            r"til toppen|tilbake til toppen|"
            r"share this page|print this page|"
            r"back to top)\s*[.!]?\s*",
            leaf,re.I):
        return 0,'none'
    # The SAME checks precede EVERY positive return, including direct matches
    # donated by an ancestor heading and the former independent Du/You path.
    for target in _application_targets(leaf):
        if re.match(r'\s*(?:ikke|ikkje|not)\b',target,re.I):
            if topic(target):return 0,'none'
        elif not neutral_target(target):
            # An incidental later query word cannot rename the object itself,
            # e.g. "garage with information about the requested service".
            target_terms=terms(target)
            if not topic(target) or not target_terms or not topic(target_terms[0]):return 0,'none'
    # Validate the ENTIRE procedural paragraph, including separate contextual
    # sentences. An incidental topic mention cannot erase another subject.
    # Compound application nouns are inspected without erasing their modifier:
    # an unknown service-specific form is not a generic "form" reference.
    procedural=procedural_text(leaf) or re.search(r'\b[\w-]*(?:søknad|skjema)\w*\b',leaf,re.I)
    # Negative contrasts are checked above/below; the original complete
    # unit, including the contrast, remains intact for every later gate.
    # Only a COMPLETE nominal contrast can be omitted from attribution.
    # Never swallow an affirmative "men/but" clause or an additive "not only".
    negative_noun=r'(?!(?:bare|berre|only|kun|men|but|og|and|eller|or|er|is|are)\b)[^\W\d_][\w-]*'
    contrast=(r',\s*(?:ikke|ikkje|not)\s+(?:(?:en|ei|et|eit|a|an|the)\s+)?'
        +negative_noun+r'(?:\s+'+negative_noun+r')?(?=\s*(?:[.!?;|]|$))')
    scope_body=re.sub(contrast,'',_asserted_service_text(leaf),flags=re.I)
    if procedural and not _implicit_application_reference(scope_body,municipality,topic=topic):
        return 0,'none'
    for match in re.finditer(r'\b(?:ikke|ikkje|not)\s+(?:(?:om|for|about)\s+)?([^,.;!?|]+)',leaf,re.I):
        prefix=leaf[max(0,match.start()-40):match.start()]
        if re.search(r'\b(?:trenger|treng|behøver|need|require)\s*(?:(?:du|you)\s*)?$',prefix,re.I):continue
        first=re.match(r'\w+',match[1])
        if first and re.fullmatch(_PROCEDURE_WORD,first[0],re.I):
            # A negated form/application OBJECT is different from a directive
            # such as "do not submit". Neither can grant a different purpose.
            noun=bool(re.fullmatch(r'(?:skjema\w*|søknad\w*|forms?|applications?)',first[0],re.I))
            if (noun or re.match(r'apply\s+to\b',match[1],re.I)) and topic(match[1]):return 0,'none'
            continue
        if topic(match[1]):return 0,'none'
    matched=[i for i,label in enumerate(parts[:-1]) if topic(label)]
    if matched:
        for label in parts[matched[-1]+1:-1]:
            condition=bool(re.search(r'\d',label) or re.match(r'\s*(?:vilkår|krav|forbehold|betingelser|unntak|begrensninger|målgruppe|eligibility|conditions|requirements|exceptions|limitations)\b',label,re.I))
            if terms(label) and not topic(label) and not condition:return 0,'none'
    direct=score(text)
    if direct:return direct,'lexical'
    if critical:return 0,'none'
    semantic=score(text,aliases=True) if alias_allowed else 0
    if semantic:return semantic,'service_alias'
    inflected=score(text,inflected=True)
    if inflected:return inflected,'inflection'
    # Generic prose may inherit only a local, textually documented topic.
    # Neither a matching URL nor "Du/You + form" supplies that evidence.
    if not document_heading or not topic(document_heading):return 0,'none'
    if re.search(r'\d|\b(?:gratis|pris\w*|gebyr\w*|kr|kroner|frist\w*)\b',text,re.I):return 0,'none'
    contact=r'\b(?:kontakt\w*|contact|henvend\w*|telefon\w*)\b'
    requested=(procedural_text(leaf) if re.search(r'\b(?:søk\w*|hvordan|korleis|apply|how)\b',question,re.I)
        else bool(re.search(contact,leaf,re.I)) if re.search(contact,question,re.I) else False)
    if not requested or len(leaf.split())<3:return 0,'none'
    if any(terms(label) and not topic(label) for label in parts[:-1]):return 0,'none'
    return 1,'document_topic_and_action'


def _previous_content_relevance(
    question,text,municipality=None,*,url=None,
    document_heading=None,document_title=None,scope_text=None
):
    match,basis=_original_content_relevance(
        question,text,municipality,url=url,
        document_heading=document_heading,
        document_title=document_title,
        scope_text=scope_text
    )

    if match:
        return match,basis

    if contextual_application_procedure(
        question,text,municipality,document_heading,scope_text
    ):
        return 1,'document_topic_and_action'

    return 0,'none'


def content_relevance(
    question,text,municipality=None,*,url=None,
    document_heading=None,document_title=None,scope_text=None
):

    if not overview_subject_supported(question,text,municipality):
        return 0,'none'
    from .research import FEE_INTENT
    from .question_router import service_families,service_alias_text

    result=_previous_content_relevance(
        question,text,municipality,url=url,
        document_heading=document_heading,
        document_title=document_title,scope_text=scope_text
    )

    if result[0]:
        return result

    if (
        municipality is None
        or not document_heading
        or not has_service_location(text)
        or FEE_INTENT.search(question)
        or re.search(
            r'\d|\b(?:ikke|ikkje|not|frist|rettighet|regel|'
            r'vilk\u00e5r|hvordan\s+s\u00f8ker)\w*\b',
            question,re.I
        )
    ):
        return result

    leaf=text.rsplit(' | ',1)[-1]

    if scope_text not in (None,leaf):
        return result

    title=re.sub(
        r'\baktivitetstilbud(?=\s+for\s+'
        r'(?:personer|mennesker)\s+med\s+'
        r'(?:demens|kognitiv svikt)\b)',
        'dagaktivitetstilbud',
        document_heading,flags=re.I
    )

    wanted=service_families(service_alias_text(question))
    available=service_families(service_alias_text(title))

    if len(wanted)==1 and wanted==available:
        return 1,'document_topic_and_action'

    return result



def monetary_subject_matches(question, approval, municipality=None):
    """All nomination paths need reviewed subject labels for monetary units.

    A paragraph's own fact entity is authoritative, never document tags or an
    unrelated heading. This is a narrow fail-closed lexical guard, not universal
    semantic verification. Historical typed units have a separate field parser.
    """
    from .question_router import CALENDAR_WORDS
    from .research import FEE_INTENT
    intent={'nå','dag','dagens','gjeldende','current','today','latest','hvorfor','bruk','bruke','få','får',
        'dette','denne','som','ved','med','uten','etter','før','about','tilbud','tilbudet',
        'hjelp','meg','oss','mer','oppdatert','gjelder','regelen','reglene','regler','vilkår',
        'neste','forrige','fjor','vår','våren','høst','høsten','måned','måneden','år','året','par','school','year','years','month',
        'last','this','next','two','three','trinn','plass','hel','halv','heltidsplass','deltidsplass',
        'sammenlign','sammenlikn','compare','andre','other','kilder','sources'}
    subjects=set(query_terms(FEE_INTENT.sub(' ',question),municipality))-intent-CALENDAR_WORDS
    for p in approval.excerpts:
        if not re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\b(?:kr\.?|NOK)\s*\d|\bgratis\b',p.text,re.I):continue
        if p.fact_scope:entity=p.fact_scope[0].replace('-',' ').replace('_',' ')
        elif approval.review_scope=='transient_html_service_excerpts':entity=p.text
        else:return False
        labels=query_terms(entity,municipality,limit=256)
        if not all(any(term==w or min(len(term),len(w))>=5 and (term.startswith(w) or w.startswith(term))
                for w in labels) for term in subjects):return False
    return True


def catalog_matches(question, approvals, municipality=None):
    # Whole reviewed excerpts are searchable locally, without a service keyword
    # registration. Never truncate the evidence or bypass authority/conflict gates.
    scored=[(a,relevance(question,' '.join((*a.keywords,*(p.text for p in a.excerpts))),municipality))
        for a in approvals if monetary_subject_matches(question,a,municipality)]
    strongest=max((score for _,score in scored),default=0)
    return [a for a,score in scored if score>0 and score==strongest]


@dataclass(frozen=True)
class DiscoveryProfile:
    """Explicit transient discovery permission, NOT content/fact approval.

    There is deliberately no default active profile and no CLI/environment
    blanket enablement. Owner and independent review must precede injection.
    Generic HTML admission and external transfers require separate permissions.
    """
    host: str
    reviewed_on: str
    expires_on: str
    owner_evidence_sha256: str
    independent_review_sha256: str
    sitemap_urls: tuple = ()
    maximum_pages: int = 5
    maximum_depth: int = 2

    def __post_init__(self):
        from .live_research import safe_url
        safe_url('https://'+self.host+'/',{self.host})
        if (type(self.maximum_pages) is not int or not 1<=self.maximum_pages<=5
                or type(self.maximum_depth) is not int or not 0<=self.maximum_depth<=2
                or type(self.sitemap_urls) is not tuple or len(self.sitemap_urls)>1
                or any(not re.fullmatch('[0-9a-f]{64}',v) for v in
                    (self.owner_evidence_sha256,self.independent_review_sha256))
                or not date.fromisoformat(self.reviewed_on)<=date.fromisoformat(self.expires_on)):
            raise ValueError('Bounded independently reviewed discovery permission required')
        for url in self.sitemap_urls:safe_url(url,{self.host})

    def current(self):
        return date.fromisoformat(self.reviewed_on)<=date.today()<=date.fromisoformat(self.expires_on)


def sitemap_candidates(raw, host):
    """Only a bounded urlset; indexes, entities and external expansion refuse.

    Returned locations are untrusted request-local candidates, never facts or
    safe log values. No URL from this function is fetched automatically.
    """
    from .live_research import safe_url
    from .research import ResearchError
    if type(raw) is not bytes or len(raw)>512*1024:raise ResearchError('research_source_limit')
    try:
        text=raw.decode('utf-8-sig',errors='strict')
        if (re.search(r'<!\s*(?:DOCTYPE|ENTITY)|[\x00-\x08\x0b\x0c\x0e-\x1f]',text,re.I)
                or re.search(r'<\?xml\b[^>]*encoding\s*=\s*[\x27\"](?!utf-8[\x27\"])',text,re.I)):
            raise ValueError()
        root=ElementTree.fromstring(text)
        ns='{http://www.sitemaps.org/schemas/sitemap/0.9}'
        if root.tag not in ('urlset',ns+'urlset') or len(root)>256:raise ValueError()
        result=[];nodes=0
        for row in root:
            if row.tag not in ('url',ns+'url') or len(row)>4:raise ValueError()
            locations=[]
            for field in row:
                nodes+=1
                if nodes>1024 or len(field) or field.tag not in tuple(ns+k for k in ('loc','lastmod','changefreq','priority'))+('loc','lastmod','changefreq','priority'):
                    raise ValueError()
                if field.tag in ('loc',ns+'loc'):locations.append(field.text or '')
            if len(locations)!=1:raise ValueError()
            url=locations[0].strip()
            try:safe_url(url,{host})
            except (ValueError,ResearchError):continue
            if url not in result:result.append(url)
        return tuple(result)
    except (UnicodeError,ValueError,ElementTree.ParseError,RecursionError):
        raise ResearchError('research_source_invalid') from None


def discover_candidates(session, question, municipality, profile, *, authorized):
    """Bounded request-local graph, with no required service/category match.

    Search snippets, sitemap entries and extracted HTML are never returned as
    evidence. Exact-source review still applies after discovery. In particular
    this does not activate the legacy typed automatic HTML admission path.
    """
    from .live_research import ServiceHTML,safe_url
    from .research import ResearchError
    if not isinstance(profile,DiscoveryProfile) or profile.host!=municipality.official_host:
        raise ResearchError('research_source_invalid')
    def check():
        session.check()
        if not authorized() or not profile.current():raise ResearchError('research_permission_revoked')
    check();host=profile.host;session.site(host);check()
    queue=[('https://'+host+'/',0,'html')]+[(url,0,'sitemap') for url in profile.sitemap_urls]
    seen=set();candidates=[];pages=0
    while queue and pages<profile.maximum_pages and session.requests<8:
        check();url,depth,kind=queue.pop(0)
        if url in seen:continue
        seen.add(url);safe_url(url,{host});check()
        raw,_,_=session.get(url,**({'document_kind':'sitemap'} if kind=='sitemap' else {}));pages+=1
        try:
            check()
            if kind=='sitemap':links=[(value,unquote(urlsplit(value).path)) for value in sitemap_candidates(raw,host)]
            else:
                parsed=ServiceHTML.parse(raw)
                links=list(parsed.links)
        finally:del raw
        ranked=[]
        for href,label in links[:256]:
            target=urljoin(url,href).split('#',1)[0]
            try:safe_url(target,{host})
            except (ValueError,ResearchError):continue
            score=relevance(question,label+' '+unquote(urlsplit(target).path),municipality)
            if not score:continue
            # Binary formats require a reviewed parser; candidate discovery is
            # not support for PDF/Office evidence, active content or archives.
            unsupported=bool(re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|zip|exe|js|png|jpe?g)$',urlsplit(target).path,re.I))
            ranked.append((score,target,unsupported))
        for score,target,unsupported in sorted(set(ranked),key=lambda item:(-item[0],item[1]))[:16]:
            if target not in candidates:candidates.append(target)
            if not unsupported and depth<profile.maximum_depth and target not in seen:
                queue.append((target,depth+1,'html'))
        session.diagnose('candidate_discovery_only',url,candidates=len(ranked),admitted_excerpts=0)
        if len(candidates)>64:candidates=candidates[:64]
        queue=queue[:16]
    check();session.diagnose('candidate_review_required',evaluated_pages=pages,
        pending_candidates=len(queue),admitted_excerpts=0)
    return tuple(candidates)


def candidate_digest(url):
    """The only candidate identifier suitable for retained diagnostics."""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def _small_public_sitemap_locations(raw,host):
    """Bounded URL-only sitemap discovery, never source facts or instructions.

    Official urlsets and one bounded index level may nominate same-host URLs.
    No DTD/entities, compressed formats, alternate encodings or external hosts.
    """
    from .live_research import safe_url
    from .research import ResearchError
    if type(raw) is not bytes or len(raw)>512*1024:raise ResearchError('research_source_limit')
    try:
        text=raw.decode('utf-8-sig',errors='strict')
        if (re.search(r'<!\s*(?:DOCTYPE|ENTITY)|[\x00-\x08\x0b\x0c\x0e-\x1f]',text,re.I)
                or re.search(r'<\?xml\b[^>]*encoding\s*=\s*[\x27\"](?!utf-8[\x27\"])',text,re.I)):
            raise ValueError()
        root=ElementTree.fromstring(text);ns='{http://www.sitemaps.org/schemas/sitemap/0.9}'
        kind='index' if root.tag in ('sitemapindex',ns+'sitemapindex') else 'urlset' if root.tag in ('urlset',ns+'urlset') else None
        if kind is None or len(root)>(16 if kind=='index' else 4096):raise ValueError()
        result=[]
        for row in root:
            if row.tag not in (('sitemap',ns+'sitemap') if kind=='index' else ('url',ns+'url')) or len(row)>4:raise ValueError()
            locations=[]
            for field in row:
                if len(field) or field.tag not in tuple(ns+k for k in ('loc','lastmod','changefreq','priority'))+('loc','lastmod','changefreq','priority'):raise ValueError()
                if field.tag in ('loc',ns+'loc'):locations.append(field.text or '')
            if len(locations)!=1:raise ValueError()
            url=locations[0].strip()
            try:safe_url(url,{host})
            except (ValueError,ResearchError):continue
            if url not in result:result.append(url)
        return kind,tuple(result)
    except (UnicodeError,ValueError,ElementTree.ParseError,RecursionError):
        raise ResearchError('research_source_invalid') from None


@dataclass(frozen=True)
class ReviewedSearchQuery:
    """Separate, expiring permission to send this non-personal query externally.

    This object must come from an owner-reviewed query admission process, never
    from the user's boolean or a search result. No such process/provider is
    activated by default. Raw chat wording is not passed to the transport.
    """
    text: str
    endpoint: str
    reviewed_on: str
    expires_on: str
    approval_sha256: str

    def current(self):
        return date.fromisoformat(self.reviewed_on)<=date.today()<=date.fromisoformat(self.expires_on)

    def __post_init__(self):
        from .retrieval import _validate_url
        from .chat import validate_message
        _validate_url(self.endpoint)
        validate_message(self.text)
        if (not 1<=len(self.text)<=80 or re.search(r'[^\w -]',self.text)
                or not re.fullmatch('[0-9a-f]{64}',self.approval_sha256) or not self.current()):
            raise ValueError('Exact expiring reviewed query transfer permission required')


@dataclass(frozen=True)
class PublicQueryPolicy:
    """Owner-reviewed public vocabulary projection, never raw chat forwarding.

    One expiring corpus/policy approval can cover many queries without a
    per-service code rule or per-question human grant. The vocabulary itself
    must already be reviewed non-personal data; unknown HTML cannot issue it.
    No production policy is installed by constructing this type in tests.
    """
    endpoint: str
    words: tuple
    reviewed_on: str
    expires_on: str
    owner_evidence_sha256: str
    corpus_review_sha256: str

    def __post_init__(self):
        from .live_research import safe_url
        from .chat import _screening_text
        safe_url(self.endpoint,{urlsplit(self.endpoint).hostname})
        if (type(self.words) is not tuple or not 1<=len(self.words)<=4096
                or len(set(self.words))!=len(self.words)
                or any(type(w) is not str or w!=w.casefold() or _screening_text(w)!=w
                    or not re.fullmatch(r'[^\W\d_][^\W\d_ -]{1,39}',w) for w in self.words)
                or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h)
                    for h in (self.owner_evidence_sha256,self.corpus_review_sha256))
                or not date.fromisoformat(self.reviewed_on)<=date.fromisoformat(self.expires_on)):
            raise ValueError('Reviewed public query corpus and policy required')

    def current(self):
        return date.fromisoformat(self.reviewed_on)<=date.today()<=date.fromisoformat(self.expires_on)

    def project(self,question):
        from .chat import validate_message
        from .research import ResearchError
        validate_message(question)
        if not self.current():raise ResearchError('research_permission_revoked')
        terms=query_terms(question)
        # Emit only EXACT approved vocabulary entries. No unmatched token,
        # original sentence, history, name or private identifier is appended.
        chosen=[word for word in self.words if any(relevance(term,word)>0 for term in terms)]
        chosen=sorted(chosen,key=lambda word:(-relevance(question,word),word))[:6]
        text=''
        for word in chosen:
            trial=(text+' '+word).strip()
            if len(trial)<=80:text=trial
        if not text:raise ResearchError('research_search_not_approved')
        proof=hashlib.sha256(json.dumps(dict(endpoint=self.endpoint,words=self.words,
            reviewed_on=self.reviewed_on,expires_on=self.expires_on,owner=self.owner_evidence_sha256,
            corpus=self.corpus_review_sha256),sort_keys=True).encode()).hexdigest()
        return ReviewedSearchQuery(text,self.endpoint,self.reviewed_on,self.expires_on,proof)


_SEARCH_USAGE=WeakKeyDictionary()
_SEARCH_USAGE_LOCK=RLock()


class SearchCallBudget:
    """Request-owned, no-refund reservations with separate billing permission.

    Units are a reviewed provider cost bound, not measured billing. Vendor
    account limits and a current price/terms decision are still required. Even
    a zero-cost claim never grants permission to call a metered provider.
    """
    def __init__(self,*,maximum_calls=0,per_call_cost_units=None,maximum_cost_units=0,
                 billing_authorized=lambda:False):
        from .run_control import current_run
        if (type(maximum_calls) is not int or not 0<=maximum_calls<=2
                or type(maximum_cost_units) is not int or not 0<=maximum_cost_units<=1000000
                or per_call_cost_units is not None and (type(per_call_cost_units) is not int
                    or not 0<=per_call_cost_units<=1000000) or not callable(billing_authorized)):
            raise ValueError('Explicit finite reviewed search budget required')
        self.owner=current_run();self._token=object()
        self.limits=(maximum_calls,per_call_cost_units,maximum_cost_units)
        self.billing_authorized=billing_authorized
        self._configuration=(self.owner,self.limits,billing_authorized)

    def _entries(self):
        with _SEARCH_USAGE_LOCK:
            value=_SEARCH_USAGE.get(self.owner) if self.owner is not None else None
            return value[2] if value is not None and value[0] is self._token else ()

    @property
    def calls(self):return len(self._entries())

    @property
    def cost_units(self):return sum(entry[2] for entry in self._entries())

    @property
    def events(self):
        return [dict(endpoint_sha256=e[0],query_sha256=e[1],call=i+1,reserved_cost_units=e[2])
            for i,e in enumerate(self._entries())]

    def check(self):
        from .run_control import current_run
        from .research import ResearchError
        if (self._configuration!=(self.owner,self.limits,self.billing_authorized) or self.owner is None
                or current_run() is not self.owner or self.owner.finished or self.owner.stopped
                or self.billing_authorized() is not True or self.limits[1] is None):
            raise ResearchError('research_search_not_approved')
        self.owner.admit_tool('reviewed_search_budget')

    def reserve(self,endpoint,query):
        from .research import ResearchError
        self.check()
        with _SEARCH_USAGE_LOCK:
            self.check();calls,fee,total=self.limits
            value=_SEARCH_USAGE.get(self.owner)
            if value is not None and (value[0] is not self._token or value[1]!=self.limits):
                # One accepted budget identity for the ENTIRE request, shared
                # by provider fallback. A new object cannot reset consumption.
                raise ResearchError('research_search_not_approved')
            entries=value[2] if value is not None else ()
            if len(entries)>=calls or sum(e[2] for e in entries)+fee>total:
                raise ResearchError('research_source_limit')
            _SEARCH_USAGE[self.owner]=(self._token,self.limits,
                (*entries,(candidate_digest(endpoint),candidate_digest(query),fee)))


@dataclass(frozen=True)
class SearchJSONContract:
    """Reviewed response layout and transient input right, not fact authority."""
    endpoint: str
    result_path: tuple
    url_key: str
    reviewed_on: str
    expires_on: str
    input_review_sha256: str

    def __post_init__(self):
        from .live_research import safe_url
        safe_url(self.endpoint,{urlsplit(self.endpoint).hostname})
        keys=(*self.result_path,self.url_key) if type(self.result_path) is tuple else ()
        if (not 1<=len(keys)<=5 or not 1<=len(self.result_path)<=4
                or any(type(k) is not str or not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]{0,39}',k) for k in keys)
                or not isinstance(self.input_review_sha256,str) or not re.fullmatch('[0-9a-f]{64}',self.input_review_sha256)
                or not date.fromisoformat(self.reviewed_on)<=date.fromisoformat(self.expires_on)):
            raise ValueError('Bounded reviewed JSON candidate contract required')

    def current(self):
        return date.fromisoformat(self.reviewed_on)<=date.today()<=date.fromisoformat(self.expires_on)


class JSONCandidateAdapter:
    """Generic JSON search response adapter; does not implement network I/O.

    A reviewed pinned HTTPS receiver must enforce request/response limits,
    credential privacy, endpoint approval and no redirects. Query/billing gates
    are enforced by CandidateSearchProvider before this adapter is invoked.
    """
    def __init__(self,contract,receiver):
        if not isinstance(contract,SearchJSONContract) or not callable(receiver):
            raise ValueError('Reviewed contract and receiver required')
        self.contract,self.receiver=contract,receiver

    def __call__(self,endpoint,query,*,timeout_seconds,max_bytes):
        from .research import ResearchError
        contract,receiver=self.contract,self.receiver
        def check():
            if (self.contract is not contract or self.receiver is not receiver or not contract.current()
                    or endpoint!=contract.endpoint):raise ResearchError('research_search_not_approved')
        check()
        response=receiver(endpoint,query,timeout_seconds=timeout_seconds,max_bytes=max_bytes)
        check()
        if (type(response) is not dict or set(response)!={'status','content_type','body'}
                or type(response['status']) is not int or response['status']!=200
                or response['content_type']!='application/json' or type(response['body']) is not bytes
                or not 0<len(response['body'])<=min(max_bytes,65536)):
            raise ResearchError('research_source_invalid')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError()
                result[key]=value
            return result
        def invalid(_):raise ValueError()
        try:
            value=json.loads(response['body'].decode('utf-8',errors='strict'),object_pairs_hook=unique,parse_constant=invalid)
            for key in contract.result_path:
                if type(value) is not dict:raise ValueError()
                value=value[key]
            if type(value) is not list or len(value)>16:raise ValueError()
            if any(type(item) is not dict or type(item.get(contract.url_key)) is not str
                    or len(item[contract.url_key])>2048 for item in value):raise ValueError()
            return tuple(item[contract.url_key] for item in value)
        except (ValueError,KeyError,TypeError,RecursionError):
            raise ResearchError('research_source_invalid') from None


class CandidateSearchProvider:
    """Provider-neutral port, not a shipped live search service.

    The injected owner-reviewed transport must enforce endpoint TLS/DNS/SSRF,
    terms and resource limits. It receives only the reviewed query and returns
    bounded URLs, never evidence/snippets. No keys or paid provider are selected
    implicitly. A concrete provider still needs credentials, approval and proof.
    """
    def __init__(self, endpoint, transport):
        from .live_research import safe_url
        safe_url(endpoint,{urlsplit(endpoint).hostname})
        if not callable(transport):raise ValueError('Reviewed transport required')
        self.endpoint,self.transport=endpoint,transport

    def candidates(self, query, *, authorized, budget=None):
        from .live_research import safe_url
        from .research import ResearchError
        from .run_control import bounded_tool_call,current_run
        endpoint=self.endpoint;transport=self.transport;owner=current_run()
        def check():
            if (owner is None or current_run() is not owner or owner.finished or owner.stopped
                    or not authorized() or not isinstance(query,ReviewedSearchQuery) or not query.current()
                    or query.endpoint!=endpoint or self.endpoint!=endpoint or self.transport is not transport):
                raise ResearchError('research_permission_revoked')
            if not isinstance(budget,SearchCallBudget):raise ResearchError('research_search_not_approved')
            budget.check()
            owner.admit_tool('candidate_search')
        check()
        budget.reserve(endpoint,query.text)
        def send():
            check()
            result=transport(endpoint,query.text,timeout_seconds=min(8.,owner.remaining()),max_bytes=65536)
            check()
            if type(result) not in (tuple,list) or len(result)>16:raise ResearchError('research_source_invalid')
            urls=[]
            for url in result:
                try:safe_url(url,{urlsplit(url).hostname})
                except (ResearchError,ValueError,TypeError):continue
                if url not in urls:urls.append(url)
            return tuple(urls)
        try:return bounded_tool_call(send,timeout_seconds=min(10.,owner.remaining()))
        except (OSError,ValueError) as error:
            if isinstance(error,ResearchError):raise
            raise ResearchError('research_unavailable') from None


def public_page_actions(raw,entry,source_url):
    from urllib.parse import urljoin,urlsplit,parse_qs

    contacts,forms=_public_page_actions_base(
        raw,entry,source_url
    )

    if not forms or len(forms)>=3:
        return contacts,forms

    has_health_form=False

    for row in forms:
        parts=urlsplit(row['url'])

        if (
            parts.scheme=='https'
            and parts.hostname==entry.official_host
            and parts.path.casefold()=='/handlers/skjema.ashx'
            and parse_qs(parts.query).get('skjemaid')
            and re.fullmatch(
                r's\u00f8k om helse-?\s+og\s+omsorgstjenester',
                row['label'].strip(),re.I
            )
        ):
            has_health_form=True
            break

    if not has_health_form:
        return contacts,forms

    for href in official_href_candidates(raw):
        target=urljoin(source_url,href).split('#',1)[0]

        try:
            parts=urlsplit(target)

            valid=(
                parts.scheme=='https'
                and parts.hostname==entry.official_host
                and not parts.username
                and not parts.password
                and not parts.port
                and not parts.query
                and target!=source_url
                and parts.path.rstrip('/').endswith(
                    '/slik-soker-du-om-helse-og-omsorgstjenester'
                )
            )
        except ValueError:
            continue

        if valid:
            return contacts,tuple(forms)+(dict(
                url=target,
                label='Kommunens s\u00f8knadsveiledning',
                source_url=source_url,
                kind='guidance'
            ),)

    return contacts,forms


def application_navigation_notice(question,documents,links):
    form_links=[
        dict(link,application_actions=[
            row for row in link.get('application_actions',())
            if row.get('kind')!='guidance'
        ])
        for link in links
    ]

    original_notice=_application_navigation_notice_base(
        question,documents,form_links
    )

    if not original_notice:
        return ""

    return (
        "Slik g\u00e5r du videre\n"
        "1. \u00c5pne kommunens s\u00f8knadsskjema nedenfor.\n"
        "2. Fyll ut skjemaet og f\u00f8lg kommunens instruksjoner.\n"
        "3. Kontakt kommunen dersom du trenger hjelp.\n\n"
        "Jeg har funnet kommunens s\u00f8knadsskjema, "
        "men ikke bekreftet alle s\u00f8knadsvilk\u00e5rene."
    )



def service_metadata_only(text):
    leaf=text.rsplit(" | ",1)[-1].strip()

    return bool(re.fullmatch(
        r'(?:publisert(?:\s*/\s*sist endret)?|'
        r'sist endret|oppdatert|last updated|published)'
        r'\s*:?\s*\d[\d./:\s-]*',
        leaf,re.I
    ))



def public_sitemap_locations(raw,host):
    """Bounded URL discovery, never a source of factual claims."""

    from xml.etree import ElementTree as ET
    from urllib.parse import urlsplit
    from .research import ResearchError
    from .internet_research import public_url

    if type(raw) is not bytes or len(raw)>1536*1024:
        raise ResearchError('research_source_limit')

    if len(raw)<=512*1024:
        return _small_public_sitemap_locations(raw,host)

    try:
        decoded=raw.decode('utf-8-sig',errors='strict')
    except UnicodeError:
        raise ResearchError('research_source_invalid') from None

    upper=decoded.upper()

    if '<!DOCTYPE' in upper or '<!ENTITY' in upper:
        raise ResearchError('research_source_invalid')

    try:
        root=ET.fromstring(decoded)
    except (ET.ParseError,ValueError):
        raise ResearchError('research_source_invalid') from None

    ns='{http://www.sitemaps.org/schemas/sitemap/0.9}'

    if root.tag in (ns+'urlset','urlset'):
        kind='urlset'
        child_tag='url'

    elif root.tag in (ns+'sitemapindex','sitemapindex'):
        kind='index'
        child_tag='sitemap'

    else:
        raise ResearchError('research_source_invalid')

    prefix=ns if root.tag.startswith(ns) else ''

    if len(root)>10000:
        raise ResearchError('research_source_limit')

    locations={}

    for child in root:
        if child.tag!=prefix+child_tag:
            raise ResearchError('research_source_invalid')

        locs=child.findall(prefix+'loc')

        if len(locs)!=1 or len(locs[0]):
            raise ResearchError('research_source_invalid')

        target=(locs[0].text or '').strip()

        if not target or len(target)>2048:
            continue

        try:
            parts=urlsplit(target)

            if (
                parts.scheme!='https'
                or parts.hostname!=host
                or parts.username
                or parts.password
                or parts.port
                or parts.fragment
                or parts.query
            ):
                continue

            public_url(target)

        except (ValueError,ResearchError):
            continue

        locations[target]=None

    return kind,tuple(locations)




def explicit_overview_subject(question):
    """Separate a requested institution from generic question framing."""
    match=re.match(
        r'^\s*(?:hva slags|hvilke)\s+'
        r'(?:tilbud|aktiviteter|tjenester)\s+'
        r'(?:har|tilbyr|gir)\s+(.+?)\s*[?!.]*$',
        question,re.I
    )
    return match[1].strip() if match else None


def overview_subject_supported(question,text,municipality=None):
    from .question_router import service_alias_text

    subject=explicit_overview_subject(question)

    if not subject:
        return True

    wanted=query_terms(
        service_alias_text(subject),municipality,limit=64
    )

    available=query_terms(
        service_alias_text(text),municipality,limit=256
    )

    def variants(word):
        result={word}

        for suffix in ('ene','en','et','er','e','a','n','s'):
            if word.endswith(suffix) and len(word)-len(suffix)>=5:
                result.add(word[:-len(suffix)])

        return result

    return bool(wanted) and any(
        variants(a)&variants(b)
        for a in wanted
        for b in available
    )



def overview_statement_heading(question,text,municipality):
    from .research import FEE_INTENT
    from .internet_research import public_unit

    if municipality is None or not explicit_overview_subject(question):
        return False

    if FEE_INTENT.search(question) or FEE_INTENT.search(text):
        return False

    if re.search(
        r'\d|\b(?:gratis|frist\w*|regel\w*|rettighet\w*|'
        r'vilk\u00e5r\w*|gebyr\w*|pris\w*)\b',
        question+' '+text,re.I
    ):
        return False

    return bool(
        len(text.split())>=8
        and text.rstrip().endswith('.')
        and re.search(
            r'\b(?:er|har|tilbyr|omfatter|gir|best\u00e5r av|'
            r'arrangerer|underviser|skal s\u00f8rge for)\b',
            text,re.I
        )
        and overview_subject_supported(question,text,municipality)
        and public_unit(text)
    )
