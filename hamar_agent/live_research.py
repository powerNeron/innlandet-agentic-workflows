"""Bounded, opt-in municipal HTML research. No browser, scripts or raw HTML storage.

This is distinct from the historical full-document/non-personal input contract.
Filtering is conservative screening, not a general anonymization guarantee.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import ipaddress
import json
import re
import socket
from threading import Lock
import time
from types import MappingProxyType
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
import uuid

from .chat import validate_message, _screening_text
from .html_extract import privacy_check, ExtractionError
from .research import (ResearchApproval, ResearchBinding, ResearchError, ResearchExcerpt,
                       ResearchService, load_research_policy, municipal_question,validate_supplementary_site,FEE_INTENT,school_overview)
from .retrieval import _pinned_public_connection, _validate_url
from .robots_policy import robots_interval
from .run_control import bounded_tool_call, current_run

AGENT = 'HamarKommuneAgent/0.3'
PERIOD_TOKEN=r'20\d{2}(?:-\d{2}-\d{2}|\s*[/–-]\s*(?:20)?\d{2})?'
MONTHS=('januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember')
DATE_TOKEN=r'(?:20\d{2}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.20\d{2}|\d{1,2}\.?\s+(?:'+'|'.join(MONTHS)+r')\s+20\d{2})'
SERVICES = {
    'kulturskole': (('kulturskol', 'musikk-og-kulturskol'), 'kultur'),
    'sfo': (('sfo', 'skolefritidsordning'), 'oppvekst'),
    'barnehage': (('barnehag',), 'oppvekst'),
    'vann': (('drikkevann', 'vann', 'avløp', 'avlop'), 'teknisk'),
    'parkering': (('parkering', 'parkerings'), 'teknisk'),
    'byggesak': (('byggesak', 'bygge', 'byggesøknad'), 'bolig'),
    'bibliotek': (('bibliotek',), 'kultur'),
    'renovasjon': (('renovasjon', 'avfall'), 'teknisk'),
    'kommuneplan': (('kommuneplan',), 'politikk'),
    'skole': (('skole','grunnskol','barneskol','ungdomsskol'), 'oppvekst'),
    'helse': (('helse','helsetjenest','omsorg','folkehelse'), 'helse'),
    'miljo': (('miljø','miljo','luftkvalitet'), 'miljo'),
}
SERVICES['kommuneplan']=(('kommuneplan','planer','politikk'), 'politikk')
CONTACT = re.compile(r'\b(?:kontaktperson|saksbehandler|ansatt\w*|rektor|styrer|telefon|mobil|e-post|epost|'
                     r'fotograf|foto|forfatter|skrevet av|publisert av|organiseres av|kontakt|contact|staff|'
                     r'koordinator|veileder|ordfører|minister|postadresse|besøksadresse|personvern)\b', re.I)
FORBIDDEN_PATH = re.compile(r'(?:kontakt|ansatt|innlogging|login|logg-inn|minside|min-side|postliste|personvern|'
                            r'personer|politiker|abonner|unsubscribe|logout|slett|delete)', re.I)
PRICE = FEE_INTENT
SAFE_CAPITALS=frozenset(('pris prisen priser satser sats gebyr gebyret gebyrer betaling foreldrebetaling '
    'maksimalpris maksimalprisen redusert soskenmoderasjon søskenmoderasjon elevavgift semesteravgift '
    'årsavgift heltidsplass deltidsplass plass skoleåret skoleår barnehageåret barnehageår kommunen kommunale '
    'barn barnets eleven elever du det dette den de for fra i ved når hvis dersom alle tilbudet tilbud '
    'sfo ppt nav nok kr kroner norge innlandet utdanningsdirektoratet regjeringen frå '
    'mandag tirsdag onsdag torsdag fredag lørdag søndag januar februar mars april mai juni juli august '
    'september oktober november desember søk slik slik søker om gratis åpningstider åpningstid '
    'fiktiv fiktivt kilde tjenester lenke til velkommen frist fristen søknad søknadsfrist innen '
    'opptak oppstart åpent stenger åpner klokken løpende send kulturskolen barnehagen barnehager '
    'skolen skoler grunnskole skolefritidsordning skolefritidsordningen helsetjenester '
    'folkehelse luftkvalitet miljø planer politikk bygge byggesøknad kultur aktivitet fritid idrett '
    'oppvekst bolig eiendom utbygging by næring teknisk sosial familie barn ungdom skole kommunal kommunens '
    'hva hvor hvordan har koster vedtekter hel halv en tur kostpris plasstyper oppsigelse endre '
    'enkeltdag sfo-plass sfo-priser sfo-tilbud').split()) | frozenset(SERVICES)
SERVICE_WORDS=SAFE_CAPITALS | frozenset((
    'og er av på med uten som et ei eller også bare kun kan skal må bør ikke til etter før '
    'enn har ha få får gis gir gjelder gjeldende være blir bli vært gjelder dersom når '
    'per pr måned måneden måneder månedspris månedspriser dag dager dagplass uke uken uker '
    'år året årene årlig time timer timene minutter trinn årstrinn hele både kommer tillegg '
    'barnet barna barnets behov særskilte plassen plassene plassens opphold oppholdet åpningstiden '
    'morgenåpning ettermiddag ferie ferien ferier feriefridager oppstartsdato skoledagen skoletid '
    'skolestart skolestartere skoledagens skolens eleven elev elever elevene elevens tilbys '
    'søker søke søknaden søknader søknadene skjema søknadsskjema elektronisk digitalt '
    'redusere redusert inntekt inntekten inntekter husholdning husholdningen ordningen '
    'betales betale betalt kost tur kostpris kostpenger gratisplass maksimal egenandel '
    'har rett rettigheter del deltid heltid nytt nye hvert samme dette disse noen alle '
    'ukentlig daglig forvaltning satsene beløp beløpet justeres januar juli august desember '
    'informasjon opplysninger tjenesten tjenestene tjeneste kommunen oppdatert kontrollert '
    'ikke oppgitt fastsatt vedtatt fra fram frem og med til og med begrenset '
    'forrige neste nå er i gjelder kjent hjelp deg videre tilbud for eleven naturlig kretsløp '
).split())


def service_topics(text):
    found={key for key,(words,_) in SERVICES.items()
           if any(re.search(r'(?<!\w)'+re.escape(word)+r'\w*',text,re.I) for word in words)}
    if found & {'sfo','kulturskole'}:found.discard('skole')
    return found


def service_topic(question):
    text=question.casefold()
    for key,(words,_) in SERVICES.items():
        if any(re.search(r'(?<!\w)'+re.escape(word)+r'\w*',text) for word in words):return key
    return None


def safe_url(url, hosts, *, search=False):
    if not isinstance(url,str) or len(url)>2048 or not url.isascii() or re.search(r'[\s\\\x00-\x1f\x7f]',url):
        raise ResearchError('research_source_invalid')
    parts=urlsplit(url)
    try:_validate_url('https://'+parts.netloc+'/')
    except ValueError:raise ResearchError('research_source_invalid') from None
    if (parts.scheme!='https' or parts.netloc not in hosts or parts.username or parts.password
            or parts.fragment or parts.port is not None or not parts.path.startswith('/')
            or parts.netloc.endswith(('.local','.internal','.localhost','.lan','.home','.home.arpa'))):
        raise ResearchError('research_source_invalid')
    decoded=unquote(unquote(parts.path))
    if ('\\' in decoded or any(part in ('.','..') for part in decoded.split('/'))
            or re.search(r'%(?:2f|5c|2e)',parts.path,re.I) or FORBIDDEN_PATH.search(decoded)):
        raise ResearchError('research_source_invalid')
    if parts.query:
        if not search:raise ResearchError('research_source_invalid')
        pairs=parse_qsl(parts.query,keep_blank_values=True,max_num_fields=4)
        if (not pairs or any(k.casefold() not in ('q','query','search','searchtext','searchstring','sok','søk')
                or len(v)>80 or re.search(r'[^\w -]',v) for k,v in pairs)):
            raise ResearchError('research_source_invalid')
    return url


def safe_text(text, municipality=None,*,minimum=16):
    text=' '.join(text.split())
    screened=_screening_text(text)
    if not minimum<=len(text)<=900 or CONTACT.search(screened):return None
    try:privacy_check(text);validate_message(text,reply=True)
    except ValueError:return None
    if municipality:
        for name in (municipality.name,*municipality.aliases):
            screened=re.sub(r'(?<!\w)'+re.escape(_screening_text(name))+r'(?!\w)','kommunen',screened,flags=re.I)
    # Closed reviewed service vocabulary: reject unknown capitalized tokens even
    # at sentence start, across lowercase particles or default-ignorable tricks.
    words=re.findall(r"[^\W_]+(?:['’-][^\W_]+)*",screened)
    if any(any(c.isupper() for c in word) and word.casefold() not in SAFE_CAPITALS for word in words):
        return None
    # Unknown lower-case words can be names too. Admit only this closed reviewed
    # service vocabulary (plus exact municipality aliases removed above), never
    # treat casing as evidence that a unit is non-personal.
    for word in words:
        if any(part and not part.isdecimal() and part.casefold() not in SERVICE_WORDS
               for part in re.split(r"['’-]",word)):
            return None
    return text


# Automatic source admission is restricted to complete public field forms.
# Calendar/service words alone do not approve arbitrary narrative or identities.
_FIELD_SERVICE=r'(?:skolefritidsordningen|skolefritidsordning|kulturskolen|kulturskole|barnehagen|barnehager|barnehage|drikkevann|vann og avløp|vann|avløp|parkering|byggesak|bibliotek|renovasjon|kommuneplan|grunnskole|skolen|skole|helsetjenester|folkehelse|helse|omsorg|luftkvalitet|miljø|miljo|planer|politikk|sfo)'
_FIELD_GRADE=r'[1-7]\.?(?:\s*[-–]\s*[1-7]\.?)?\s*trinn'
_FIELD_PLACE=r'(?:hel|halv)\s+plass'
_FIELD_NUMBER=r'\d{1,7}(?:[ .]\d{3})*(?:,\d{1,2})?'
_FIELD_MONEY=rf'(?:kr\.?\s*{_FIELD_NUMBER}(?:,-)?|{_FIELD_NUMBER}\s*(?:kroner|kr\.?|,-(?:\s*kroner)?))'
_FIELD_UNIT=r'(?:per|pr\.?)\s+(?:måned|år|dag|uke|time|plass|barn|elev|semester)'
_FIELD_PERIOD=rf'(?:fra|frå|til|f\.o\.m\.?|t\.o\.m\.?)\s+{DATE_TOKEN}'
_FIELD_PRICE_PREFIX=rf'(?:(?:pris(?:en|er)?|satser|gebyr(?:et|er)?|avgift(?:en|er)?|betaling)(?:\s+for)?(?:\s+{_FIELD_SERVICE})?(?:\s+{PERIOD_TOKEN})?|{_FIELD_SERVICE}(?:\s+{_FIELD_GRADE})?\s*:?\s*(?:{_FIELD_PLACE})?|{_FIELD_PLACE})'
_FIELD_FEE=re.compile(rf'(?:{_FIELD_PRICE_PREFIX}\s*(?:er|:|=)?\s*)?(?:{_FIELD_MONEY}|gratis)(?:\s+{_FIELD_UNIT})?(?:\s+{_FIELD_PERIOD}){{0,2}}[.]?',re.I)
_FIELD_FREE=re.compile(rf'gratis\s+{_FIELD_SERVICE}\s+{PERIOD_TOKEN}\s+for\s+(?:eleven|elever|barnet)[.]?',re.I)
_FIELD_DEADLINE=re.compile(rf'(?:søknadsfrist(?:en)?|frist(?:en)?)(?:\s+for\s+{_FIELD_SERVICE})?\s*(?:er|:)\s*{DATE_TOKEN}[.]?',re.I)
_FIELD_HOURS=re.compile(rf'(?:åpningstid(?:er)?(?:\s+for\s+{_FIELD_SERVICE})?\s*(?:er|:)|{_FIELD_SERVICE}\s+har\s+åpningstid)\s*(?:fra\s+)?(?:klokken\s+|kl\.?\s*)?\d{{1,2}}[.:]\d{{2}}\s*(?:til|[-–])\s*\d{{1,2}}[.:]\d{{2}}[.]?',re.I)
_FIELD_GENERAL=re.compile(rf'(?:{_FIELD_SERVICE}\s+er\s+et\s+tilbud\s+for\s+elever\s+før\s+og\s+etter\s+(?:skolen|skoletid)|vann\s+er\s+en\s+del\s+av\s+et\s+naturlig\s+kretsløp)[.]?',re.I)
_FIELD_HEADERS=frozenset(('tjenester','tilbud','kommunen','priser','satser','gebyrer','åpningstider',
    'åpningstid','plasstyper','enkeltdag','for alle','hel plass','halv plass','oppvekst',
    'barnehage og skole','kultur og aktivitet','helse og omsorg',
    'skolefritidsordningen: plasstyper, pris, åpningstider, ferie, redusert betaling og oppsigelse av plass'))


def public_service_unit(text,municipality=None):
    value=_screening_text(text).casefold()
    if municipality:
        for name in (municipality.name,*municipality.aliases):
            value=re.sub(r'(?<!\w)'+re.escape(_screening_text(name).casefold())+r'(?!\w)','kommunen',value)
    fields=[part.strip() for part in value.split('|')]
    if not fields or not all(fields):return False
    def header(part):
        part=part.rstrip(':. ').strip()
        if part in _FIELD_HEADERS:return True
        return bool(re.fullmatch(rf'{_FIELD_SERVICE}(?:\s+i\s+kommunen)?(?:\s*[-:]\s*{_FIELD_SERVICE})?',part)
            or re.fullmatch(rf'(?:priser?|satser|gebyrer?)(?:\s+for)?(?:\s+{_FIELD_SERVICE})?\s+{PERIOD_TOKEN}',part)
            or re.fullmatch(rf'(?:skoleår(?:et)?|barnehageår(?:et)?)\s+{PERIOD_TOKEN}',part)
            or re.fullmatch(rf'(?:{_FIELD_SERVICE}\s+)?(?:{_FIELD_PLACE}\s+)?(?:for\s+)?{_FIELD_GRADE}(?:\s*[-–]?\s*(?:sfo-plass\s+)?for\s+elever\s+med\s+særskilte\s+behov)?',part))
    return all(header(part) for part in fields[:-1]) and any(
        pattern.fullmatch(fields[-1]) for pattern in (_FIELD_FEE,_FIELD_FREE,_FIELD_DEADLINE,_FIELD_HOURS,_FIELD_GENERAL))


class ServiceHTML(HTMLParser):
    """Text/links only; execution, external assets, forms and contacts are inert."""
    SKIP={'script','style','noscript','iframe','object','embed','svg','template','footer','address','figcaption','aside'}
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.blocks=[];self.block_kinds=[];self.parts=[];self.links=[];self.anchor=None
        self.forms=[];self.form=None;self.published=None;self.updated=None;self.noindex=False
        self.main_roots=0;self.article_roots=0
        self.main_positions=set()
        self.article_positions=set()
        self.scope_positions={}
        self.table_header='';self.row_header=False
        self.nodes=0;self.extracted_bytes=0
        self.directory_links=[];self.directory_headings=[];self.directory_scopes={};self.directory_overflow=False
        self.directory_inherited=();self.directory_excluded=set();self.directory_heading_starts={}
        self.directory_rows={}

    def flush(self):
        if self.parts:
            text=' '.join(''.join(self.parts).split());self.parts=[]
            if any(tag=='tr' for tag,_ in self.stack):
                if self.row_header:
                    if len(text)>900:raise ResearchError('research_source_limit')
                    self.table_header=text
                elif self.table_header:text=self.table_header+' | '+text
            overflow=len(text)>900
            if overflow:text=''  # Never truncate a condition or a private-data signal into admissible evidence.
            self.extracted_bytes+=len(text.encode('utf-8'))
            if len(self.blocks)>=256 or self.extracted_bytes>65536:raise ResearchError('research_source_limit')
            self.blocks.append(text)
            kind=next((tag for tag,_ in reversed(self.stack) if tag in ('h1','h2','h3','h4','h5','h6','p','tr','li')),'')
            self.block_kinds.append('barrier:'+kind if overflow else kind)
            if re.fullmatch(r'h[1-6]',kind):
                level=int(kind[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]
                start=self.directory_heading_starts.pop(level,len(self.directory_links))
                for i in range(start,len(self.directory_links)):
                    href,label,eligible,context=self.directory_links[i]
                    if text!=label:self.directory_links[i]=(href,label,eligible,(*context,(level,None if overflow else text)))
                self.directory_headings.append((level,None if overflow else text))
            elif text and not self.anchor and kind in ('p','li','tr') and not any(
                    row['start']<len(self.directory_links) for row in self.directory_rows.values()):
                if not re.fullmatch(r'(?:publisert|sist endret|sist oppdatert|oppdatert)\s*[:.]?\s*'+DATE_TOKEN+r'\s*\.?',text,re.I):
                    # A standalone label/condition must not disappear between
                    # the category heading and its institution records.
                    self.directory_headings=[h for h in self.directory_headings if h[0]!=7]+[(7,None if overflow else text)]

    def active(self):
        return any(tag in ('main','article') or i in self.main_positions or i in self.article_positions for i,(tag,_) in enumerate(self.stack))

    def scope_event(self,kind):
        if len(self.blocks)>=256:raise ResearchError('research_source_limit')
        self.blocks.append('');self.block_kinds.append(kind)

    def handle_starttag(self,tag,attrs):
        self.nodes+=1
        if self.nodes>20000 or len(self.stack)>=64:raise ResearchError('research_source_limit')
        attrs=dict(attrs)
        role=(attrs.get('role') or '').strip().casefold()
        blocked=any(item[1] for item in self.stack) or tag in self.SKIP or 'hidden' in attrs or attrs.get('aria-hidden')=='true'
        blocked=blocked or bool(CONTACT.search(attrs.get('class','')+' '+attrs.get('id','')))
        active=self.active()
        if tag=='meta' and not self.scope_positions:
            name=(attrs.get('property') or attrs.get('name','')).casefold();value=attrs.get('content','')
            if name in ('robots','hamarkommuneagent') and re.search(r'\b(?:noindex|none)\b',value,re.I):self.noindex=True
            if name in ('article:published_time','datepublished','dc.date.issued'):self.published=value
            if name in ('article:modified_time','datemodified','dc.date.modified'):self.updated=value
        if tag=='time' and attrs.get('datetime') and not self.scope_positions:
            if attrs.get('itemprop','').casefold()=='datepublished':self.published=attrs['datetime']
            if attrs.get('itemprop','').casefold()=='datemodified':self.updated=attrs['datetime']
        if tag=='input' and attrs.get('type','').casefold()=='password':self.noindex=True
        if (tag=='main' or tag in ('div','section') and role=='main') and not blocked:
            self.main_roots+=1;self.main_positions.add(len(self.stack))
        article=tag=='article' or role=='article' and tag not in self.VOID
        if article and not blocked:
            self.article_roots+=1;self.article_positions.add(len(self.stack))
        semantic=tag if tag in ('article','section','table') else 'article' if article else 'section' if role in ('region','group','tabpanel') else None
        if semantic and not blocked and (active or article):
            self.flush();self.scope_event('scope_enter:'+semantic)
            self.scope_positions[len(self.stack)]=semantic
            self.directory_scopes[len(self.stack)]=(tuple(self.directory_headings),self.directory_inherited)
            self.directory_inherited=(*self.directory_inherited,*self.directory_headings);self.directory_headings=[]
        if tag=='table':self.table_header=''
        if tag=='tr':self.row_header=False
        if tag=='th':self.row_header=True
        if active and tag in ('p','li','tr','h1','h2','h3','h4','h5','h6'):self.flush()
        if active and re.fullmatch(r'h[1-6]',tag):
            level=int(tag[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]
            self.directory_heading_starts[level]=len(self.directory_links)
        if active and tag in ('p','li','tr','h1','h2','h3','h4','h5','h6') and not blocked:
            self.directory_rows[len(self.stack)]=dict(start=len(self.directory_links),text='',dirty=False)
        if role in ('navigation','banner','contentinfo','search') and tag not in self.VOID:
            self.directory_excluded.add(len(self.stack))
        if tag in ('td','th','br') and active and not blocked:self.parts.append(' | ')
        if active and not blocked and (tag=='sup' or attrs.get('aria-describedby')
                or re.search(r'(?:^|;)\s*vertical-align\s*:\s*super\b',attrs.get('style') or '',re.I)
                or tag=='a' and ((attrs.get('role') or '').casefold()=='doc-noteref'
                    or set((attrs.get('rel') or '').casefold().split()) & {'footnote','noteref'}
                    or re.search(r'^#(?:.*(?:foot|note|fn)|\d)',attrs.get('href') or '',re.I))):
            self.parts.append(' * ')  # Explicit unsupported-note marker; this unit is refused, never cited.
        if active and blocked and re.fullmatch(r'h[1-6]',tag):
            level=int(tag[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]+[(level,None)]
        if active and (blocked or tag=='sup' or attrs.get('aria-describedby')
                or re.search(r'(?:^|;)\s*vertical-align\s*:\s*super\b',attrs.get('style') or '',re.I)):
            for row in self.directory_rows.values():row['dirty']=True
        if tag=='a' and not blocked:
            eligible=active and bool(self.directory_rows) and not self.directory_excluded and not any(t in ('nav','header','form') for t,_ in self.stack)
            self.anchor=[attrs.get('href',''),[],(eligible,(*self.directory_inherited,*self.directory_headings))]
        if tag=='form' and not blocked:
            self.form={'action':attrs.get('action',''),'method':attrs.get('method','get').casefold(),'field':None}
        if tag=='input' and self.form is not None and attrs.get('type','text').casefold() in ('text','search'):
            if attrs.get('name','').casefold() in ('q','query','search','searchtext','searchstring','sok','søk'):
                self.form['field']=attrs['name']
        if tag not in self.VOID:self.stack.append((tag,blocked))

    def handle_endtag(self,tag):
        if tag in ('p','li','tr','h1','h2','h3','h4','h5','h6'):self.flush()
        if tag=='a' and self.anchor is not None:
            href,parts,context=self.anchor
            label=' '.join(''.join(parts).split())
            if self.active() and re.fullmatch(r'(?:\d{1,3}|[a-zA-Z*†‡])',label):self.parts.append(' * ')
            if len(self.links)<256:self.links.append((href,' '.join(''.join(parts).split())[:160]))
            if context[0]:
                if len(self.directory_links)>=256:self.directory_overflow=True
                else:self.directory_links.append((href,label,*context))
            self.anchor=None
        if tag=='form' and self.form is not None:
            if self.form['method']=='get' and self.form['field'] and len(self.forms)<2:self.forms.append(self.form)
            self.form=None
        if tag=='table':self.table_header=''
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                for position in sorted((p for p in self.directory_rows if p>=i),reverse=True):
                    row=self.directory_rows.pop(position);row_text=' '.join(row['text'].split())
                    for number in range(row['start'],len(self.directory_links)):
                        href,label,eligible,context=self.directory_links[number]
                        if row['dirty'] or row_text!=label:self.directory_links[number]=(href,label,False,context)
                closing=[position for position in self.scope_positions if position>=i]
                if closing:
                    self.flush()
                    for position in sorted(closing,reverse=True):
                        self.scope_event('scope_exit:'+self.scope_positions.pop(position))
                        local,self.directory_inherited=self.directory_scopes.pop(position);self.directory_headings=list(local)
                del self.stack[i:];self.main_positions={position for position in self.main_positions if position<i}
                self.article_positions={position for position in self.article_positions if position<i};break
        self.directory_excluded={position for position in self.directory_excluded if position<len(self.stack)}

    def handle_data(self,data):
        if any(item[1] for item in self.stack):return
        for row in self.directory_rows.values():
            if len(row['text'])+len(data)>300:row['dirty']=True
            elif not row['dirty']:row['text']+=data
        if self.anchor is not None:self.anchor[1].append(data)
        if (self.active()
                and not any(item[0] in ('nav','header','form') for item in self.stack)):
            if (any(item[0] in ('span','small') for item in self.stack)
                    and re.fullmatch(r'\s*\d{1,3}\s*',data)):
                self.parts.append(' * ')  # Unreviewed inline numeric annotation cannot become a price digit.
            self.parts.append(data)

    @classmethod
    def parse(cls,raw):
        if type(raw) is not bytes or len(raw)>512*1024:raise ResearchError('research_source_limit')
        parser=cls()
        try:parser.feed(raw.decode('utf-8-sig',errors='strict'));parser.close();parser.flush()
        except (UnicodeError,ValueError,RecursionError):raise ResearchError('research_source_invalid') from None
        if parser.scope_positions:raise ResearchError('research_source_invalid')
        if parser.noindex:raise ResearchError('research_source_invalid')
        if parser.main_roots>1 or not parser.main_roots and parser.article_roots>1:
            parser.blocks=[]  # Discovery may continue, but ambiguous bodies are never evidence.
        return parser


_SCHOOL_HEADINGS={
    'barneskoler':'barneskole','barneskolene':'barneskole','kommunale barneskoler':'barneskole',
    'ungdomsskoler':'ungdomsskole','ungdomsskolene':'ungdomsskole','kommunale ungdomsskoler':'ungdomsskole',
    'skoler':'skole','skolene':'skole','grunnskoler':'skole','grunnskolene':'skole',
    'skoler i kommunen':'skole','kommunale skoler':'skole',
}
_SCHOOL_NAV=frozenset((*_SCHOOL_HEADINGS,'skole','barnehage og skole','skole og utdanning','oppvekst og utdanning'))
_DIRECTORY_QUERY_WORDS=frozenset(('hva heter hvilke finnes kan du alle i kommunen kommune innlandet gi meg vis en liste '
    'oversikt over list opp og er det dette listen oversikten komplett fullstendig nå dag dagens oppdatert').split())


def school_directory_query_supported(question,municipality):
    text=_screening_text(question)
    for name in (municipality.name,*municipality.aliases):
        text=re.sub(r'(?<!\w)'+re.escape(name)+r'(?!\w)',' ',text,flags=re.I)
    words=re.findall(r'\w+',text.casefold())
    return all(word in _DIRECTORY_QUERY_WORDS or re.fullmatch(r'(?:barne|ungdoms|grunn)?skol(?:e|en|er|ene)',word)
               for word in words)


def school_directory(parsed,url,municipality,kind):
    """Typed institutional link fields only; never relax ordinary text/privacy admission.

    The categorical heading and same-host institution URL are mandatory. A school
    name is not a person narrative. Unknown types/contexts are omitted, and every
    result is explicitly partial; neither HTML structure nor an SFO list proves
    that the municipality's primary-school population has been exhausted.
    """
    if parsed.directory_overflow:raise ResearchError('research_source_limit')
    if (municipality is None or urlsplit(url).query or not parsed.blocks
            or parsed.main_roots>1 or not parsed.main_roots and parsed.article_roots!=1):return ()
    records={}
    for href,label,active,headings in parsed.directory_links:
        if not active:continue
        category=None;unknown=False
        for _,heading in headings:
            if heading is None:unknown=True;continue
            text=' '.join(heading.casefold().strip(' :').split())
            text=re.sub(r'\s+i\s+'+re.escape(municipality.name.casefold())+r'$', '',text)
            # Nearest heading is authoritative; unknown/private/closed/contact
            # subsections cannot inherit a preceding primary-school category.
            if text in _SCHOOL_HEADINGS:category=_SCHOOL_HEADINGS[text]
            elif text not in _SCHOOL_NAV|{'tjenester','oppvekst'}:unknown=True
        if unknown or category is None:continue
        if (not 6<=len(label)<=100 or _screening_text(label)!=label
                or CONTACT.search(label) or re.search(r'[*†‡\d_<>\[\]{}:/\\]',label)):continue
        if not re.fullmatch(r"[^\W\d_]+(?:['’-][^\W\d_]+)*(?: [^\W\d_]+(?:['’-][^\W\d_]+)*){0,5} (?:skole|barneskole|ungdomsskole|oppvekstsenter)",label,re.I):continue
        if re.search(r'\b(?:ignore|ignorer|system|assistant|instruks\w*|instruction\w*|prompt|override|hemmelig\w*|secret\w*|returner)\b',label,re.I):continue
        named_type=re.search(r'\b(barneskole|ungdomsskole)$',label,re.I)
        if named_type:
            if category!='skole' and category!=named_type[1].casefold():continue
            category=named_type[1].casefold()
        if kind!='skole' and category!=kind:continue
        try:privacy_check(label);validate_message(label,reply=True)
        except ValueError:continue
        target=urljoin(url,href)
        try:safe_url(target,{municipality.official_host})
        except (ResearchError,ValueError):continue
        path=unquote(urlsplit(target).path).strip('/').casefold().split('/')
        if not any(part in ('skole','skoler','barneskoler','grunnskoler','ungdomsskoler') for part in path[:-1]):continue
        slug=re.sub(r"['’]",'',label.casefold()).replace(' ','-')
        short=re.sub(r'-(?:barne|ungdoms)?skole$','',slug)
        if path[-1] not in (slug,short):continue
        previous=records.get(target)
        if previous is not None and previous!=(label,category):raise ResearchError('research_source_conflict')
        if any(name.casefold()==label.casefold() and link!=target for link,(name,_) in records.items()):
            raise ResearchError('research_source_conflict')
        records[target]=(label,category)
        if len(records)>40:raise ResearchError('research_source_limit')
    return tuple((label,target,category) for target,(label,category) in records.items())


class LiveTransport:
    """Same pinned TLS/robots/run controller as prepared transport, HTML opt-in."""
    def __init__(self,*,resolver=None,connection_factory=None,clock=None,sleep=None):
        self.resolver=resolver or socket.getaddrinfo
        self.connection_factory=connection_factory or _pinned_public_connection
        self.clock=clock or time.monotonic;self.sleep=sleep or time.sleep
        self.lock=Lock();self.next_start={}

    def get(self,url,session,*,robots=False):
        safe_url(url,session.hosts,search=not robots)
        def fetch():
            session.check()
            if session.requests>=8:raise ResearchError('research_source_limit')
            session.requests+=1
            host=urlsplit(url).hostname
            interval=2. if robots else max(2.,robots_interval(session.robots[host],url,AGENT))
            with self.lock:
                wait=max(0.,self.next_start.get(host,0.)-self.clock())
                if wait>=session.owner.remaining():raise ResearchError('research_unavailable')
                self.next_start[host]=self.clock()+wait+interval
            if wait:self.sleep(wait)
            session.check()
            addresses=self.resolver(host,443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)
            if not isinstance(addresses,(list,tuple)) or not 1<=len(addresses)<=8:raise ResearchError('research_source_invalid')
            for family,kind,proto,canonical,address in addresses:
                ip=ipaddress.ip_address(address[0])
                if (family not in (socket.AF_INET,socket.AF_INET6) or kind!=socket.SOCK_STREAM or address[1]!=443
                        or not ip.is_global or ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local
                        or ip.is_multicast or ip.is_unspecified or getattr(ip,'is_site_local',False)
                        or getattr(ip,'ipv4_mapped',None) is not None or getattr(ip,'sixtofour',None) is not None
                        or getattr(ip,'teredo',None) is not None or ip.version==6 and ip in ipaddress.ip_network('64:ff9b::/96')
                        or (family==socket.AF_INET)!=(ip.version==4)):
                    raise ResearchError('research_source_invalid')
            session.check()
            connection=self.connection_factory(host,addresses[0][4][0],min(8.,session.owner.remaining()))
            limit=65536 if robots else 512*1024
            try:
                session.check()
                path=urlsplit(url).path+('?' + urlsplit(url).query if urlsplit(url).query else '')
                connection.request('GET',path,headers={'User-Agent':AGENT,'Accept':'text/plain' if robots else 'text/html',
                    'Accept-Encoding':'identity','Connection':'close'})
                response=connection.getresponse();headers=response.headers
                if (response.status!=200 or len(headers.get_all('Content-Type',[]))!=1
                        or headers.get_content_type() not in (('text/plain',) if robots else ('text/html',))
                        or len(headers.get_params())>2
                        or len(headers.get_all('Content-Encoding',[]))>1
                        or headers.get_content_charset('utf-8').casefold() not in ('utf-8','utf8')
                        or headers.get('Content-Encoding','identity').casefold()!='identity'
                        or headers.get('Location') or headers.get('WWW-Authenticate')
                        or re.search(r'\b(?:noindex|none)\b',headers.get('X-Robots-Tag',''),re.I)
                        or sum(len(k)+len(v) for k,v in headers.items())>8192):
                    raise ResearchError('research_source_invalid')
                lengths=headers.get_all('Content-Length',[]);transfer=headers.get_all('Transfer-Encoding',[])
                if (len(lengths)>1 or lengths and (not lengths[0].isdigit() or int(lengths[0])>limit)
                        or transfer and (transfer!=['chunked'] or lengths)):
                    raise ResearchError('research_source_invalid')
                parts=[];total=0
                while True:
                    session.check()
                    block=response.read(min(4096,limit+1-total))
                    if not block:break
                    total+=len(block);session.received+=len(block)
                    if total>limit or session.received>1024*1024:raise ResearchError('research_source_limit')
                    parts.append(block)
                if lengths and total!=int(lengths[0]):raise ResearchError('research_source_invalid')
                raw=b''.join(parts);observed=datetime.now(timezone.utc).isoformat()
                record=dict(url=url,request_id=session.request_id,retrieved_at=observed,bytes=total,
                    raw_sha256=hashlib.sha256(raw).hexdigest(),status=200,role='robots' if robots else 'html')
                session.observe(record)
                return raw,record,headers.get('Last-Modified')
            finally:connection.close()
        try:return bounded_tool_call(fetch,timeout_seconds=min(10.,session.owner.remaining()))
        except ResearchError:raise
        except (OSError,ValueError,TypeError,IndexError,HTTPException,UnicodeError) as error:
            session.observe(dict(url=url,request_id=session.request_id,role='transport_failure',
                error_type=type(error).__name__,winerror=getattr(error,'winerror',None)))
            raise ResearchError('research_unavailable') from None


class LiveSession:
    def __init__(self,service,owner,request_id,started,authorized,hosts):
        self.service,self.owner,self.request_id,self.started=service,owner,request_id,started
        self.authorized=authorized;self.revision=service.revision
        self.registry=service.municipalities;self.registry_hash=self.registry.fingerprint()
        self.hosts=frozenset(hosts);self.requests=0;self.received=0;self.trace=[];self.robots={};self.diagnostics=[]

    def observe(self,record):
        # Unadmitted navigation paths can contain personal identifiers. Keep only
        # reviewed host + URL digest in discovery logs, never labels/body/path text.
        item=dict(record);url=item.pop('url')
        item.update(official_host=urlsplit(url).hostname,url_sha256=hashlib.sha256(url.encode()).hexdigest())
        self.trace.append(item)

    def diagnose(self,stage,url=None,**counts):
        if len(self.diagnostics)>=24:return
        item=dict(stage=stage,**counts)
        if url:item.update(official_host=urlsplit(url).hostname,url_sha256=hashlib.sha256(url.encode()).hexdigest())
        self.diagnostics.append(item)

    def check(self):
        with self.service.lock:
            if (current_run() is not self.owner or self.owner.finished or self.owner.stopped
                    or not self.authorized() or not self.service.live_enabled or self.service.revoked
                    or self.service.revision!=self.revision or self.service.municipalities is not self.registry
                    or self.registry.fingerprint()!=self.registry_hash
                    or any(not m.current() for m in self.registry.entries.values())):
                raise ResearchError('research_permission_revoked')
            self.owner.admit_tool('live_source_binding')

    def get(self,url,*,robots=False):
        self.check()
        try:
            raw,record,modified=self.service.transport.get(url,self,robots=robots)
            self.check()
            if (type(raw) is not bytes or type(record) is not dict or record.get('url')!=url
                    or len(raw)>(65536 if robots else 512*1024) or self.received>1024*1024 or self.requests>8
                    or record.get('request_id')!=self.request_id or type(record.get('status')) is not int
                    or record['status']!=200 or record.get('role')!=('robots' if robots else 'html')
                    or type(record.get('bytes')) is not int or record['bytes']!=len(raw)
                    or record.get('raw_sha256')!=hashlib.sha256(raw).hexdigest()):
                raise ResearchError('research_source_invalid')
            try:
                observed=datetime.fromisoformat(record['retrieved_at'])
                if observed.tzinfo is None or not self.started<=observed<=datetime.now(timezone.utc):raise ValueError()
            except (KeyError,ValueError,TypeError):raise ResearchError('research_source_invalid') from None
            return raw,dict(record),modified
        except ResearchError as error:
            error.source_diagnostics=tuple(self.trace+self.diagnostics)
            raise

    def site(self,host):
        if host not in self.robots:
            raw,record,_=self.get('https://'+host+'/robots.txt',robots=True)
            # Decode/validate even an empty policy; malformed data is not permission.
            try:interval=robots_interval(raw,'https://'+host+'/',AGENT)
            except ValueError:raise ResearchError('research_source_invalid') from None
            self.robots[host]=raw
            with self.service.transport.lock:
                transport=self.service.transport
                transport.next_start[host]=max(transport.next_start.get(host,0.),transport.clock()+interval)


def source_date(value,observed):
    if not value:return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            if date.fromisoformat(value)>observed.date():raise ValueError()
            return value
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None or parsed>observed:raise ValueError()
        return parsed.isoformat()
    except (ValueError,TypeError):raise ResearchError('research_source_invalid') from None


def effective_periods(text):
    # Literal price/rule periods only, never the HTTP or publication timestamp.
    return tuple(dict.fromkeys(m.group(1) for m in re.finditer(
        r'\b(?:\w*pris\w*|satser|\w*gebyr\w*|\w*avgift\w*|\w*betal\w*|gratis|gjelder|gjeldende|skoleår\w*|barnehageår\w*)'
        r'[^.\n]{0,35}?\b('+PERIOD_TOKEN+r')\b',text,re.I)))


def fee_periods(text):
    """Bind periods to monetary clauses, not unrelated school/application dates."""
    periods=[]
    for clause in re.split(r';|\n|\.(?=\s+[A-ZÆØÅ])',text):
        if not re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\bgratis\b',clause,re.I):continue
        found=re.findall(r'\b(?:\w*pris\w*|satser|\w*gebyr\w*|\w*avgift\w*|\w*betal\w*|gratis)'
            r'[^;.\n]{0,60}?\b('+PERIOD_TOKEN+r')\b',clause,re.I)
        if not found:return ()  # An undated amount is not made current by another clause.
        periods.extend(found)
    return tuple(dict.fromkeys(periods))


def fee_period_matches(period,question):
    requested=re.search(r'\b'+PERIOD_TOKEN+r'\b',question)
    clean=lambda value:re.sub(r'\s+','',value)
    if requested and re.search(r'[/–-]',requested[0]) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',requested[0]):
        return clean(period)==clean(requested[0])
    year=requested[0][:4] if requested else str(date.today().year)
    # A spanning school year is not automatically valid throughout its end year.
    return period[:4]==year


def supports_question(text,question):
    def grades(value):
        result=set()
        for match in re.finditer(r'\b([1-7])\.?(?:\s*[-–]\s*([1-7])\.?)?\s*trinn\b',value,re.I):
            first=int(match[1]);last=int(match[2] or match[1]);result.update(range(first,last+1))
        return result
    requested=grades(question)
    scoped=[grades(part) for part in text.split('|') if grades(part)]
    eligible=set.intersection(*scoped) if scoped else set()
    if scoped and not eligible:return False
    if requested and not requested.issubset(eligible):return False
    for place in ('hel','halv'):
        if re.search(r'\b'+place+r'\s+plass\b',question,re.I) and not re.search(r'\b'+place+r'\s+plass\b',text,re.I):return False
    fee_intent=bool(PRICE.search(question))
    if fee_intent or re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\bgratis\b',text,re.I):
        periods=fee_periods(text)
        if not periods or not all(fee_period_matches(p,question) for p in periods):return False
        requested=re.search(r'\b'+DATE_TOKEN+r'\b',question,re.I)
        asof=literal_date(requested[0]) if requested else date.today()
        for match in re.finditer(r'\b(fra|frå|til|f\.o\.m\.?|t\.o\.m\.?)\s+('+DATE_TOKEN+r')\b',text,re.I):
            try:value=literal_date(match[2])
            except ValueError:return False
            starts=match[1].casefold().startswith('f')
            if starts and value>asof or not starts and value<asof:return False
        if fee_intent:return True
    if re.search(r'\b(?:\w*frist\w*|når.*søke)\b',question,re.I):
        if not re.search(r'\b(?:\w*frist\w*|innen|løpende opptak)\b',text,re.I):return False
        dates=[]
        for value in re.findall(r'\b'+DATE_TOKEN+r'\b',text,re.I):
            try:dates.append(literal_date(value))
            except ValueError:return False
        return bool(dates and any(value>=date.today() for value in dates) or re.search(r'\bløpende opptak\b',text,re.I))
    if re.search(r'\b(?:åpningstid\w*|åpner|stenger|åpent)\b',question,re.I):
        return bool(re.search(r'\b(?:åpningstid\w*|åpent|åpner|stenger)\b',text,re.I)
                    and re.search(r'\b\d{1,2}[.:]\d{2}\b',text))
    if re.search(r'\bhvordan\s+søker\b',question,re.I):
        return bool(re.search(r'\b(?:søknad\w*|søk|send|skjema)\b',text,re.I))
    return True


def literal_date(value):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return date.fromisoformat(value)
    dotted=re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(20\d{2})',value)
    if dotted:return date(int(dotted[3]),int(dotted[2]),int(dotted[1]))
    words=re.fullmatch(r'(\d{1,2})\.?\s+(\w+)\s+(20\d{2})',value,re.I)
    if words and words[2].casefold() in MONTHS:
        return date(int(words[3]),MONTHS.index(words[2].casefold())+1,int(words[1]))
    raise ValueError('Explicit complete source date required')


@dataclass(frozen=True)
class LiveApproval(ResearchApproval):
    raw_response_sha256: str = ''
    retrieved_at: str = ''
    published_at: str | None = None
    updated_at: str | None = None
    last_modified: str | None = None
    effective_periods: tuple = ()
    directory_kind: str | None = None
    directory_items: tuple = ()

    def __post_init__(self):
        # Deliberately do not assert full-document absence of personal data.
        if (self.content_type!='text/html' or self.review_scope!='transient_html_service_excerpts'
                or self.non_personal_input_reviewed is not False or not self.reuse_reviewed
                or not re.fullmatch('[a-z][a-z0-9-]{1,79}',self.source_id)
                or not 1<=len(self.excerpts)<=3 or any(not isinstance(p,ResearchExcerpt) for p in self.excerpts)
                or not re.fullmatch('[0-9a-f]{64}',self.raw_response_sha256)
                or not re.fullmatch('[0-9a-f]{64}',self.robots_sha256)
                or self.authority_tier not in (1,2,3) or not self.current()):
            raise ValueError('Invalid transient HTML excerpt provenance')
        _validate_url(self.url)  # Query pages are discovery, never final evidence.
        observed=datetime.fromisoformat(self.retrieved_at)
        if observed.tzinfo is None or observed>datetime.now(timezone.utc):raise ValueError('Invalid observation date')
        if self.directory_kind is not None:
            if (self.directory_kind not in ('barneskole','ungdomsskole','skole') or not 1<=len(self.directory_items)<=40
                    or len(self.excerpts)!=1):raise ValueError('Bounded whole school directory required')
        elif self.directory_items:raise ValueError('Directory type required')

    @property
    def raw_sha256(self):return self.raw_response_sha256

    @property
    def text_sha256(self):return hashlib.sha256(self.body).hexdigest()


class LiveBinding(ResearchBinding):
    def __init__(self,private,session,approvals,observations,municipality,municipal):
        self.live_session=session
        super().__init__(private,session.owner,private.revision,approvals,session.request_id,observations,
            session.authorized,municipality,municipal)
        self.receipts_fingerprint=self._receipts_hash()
        self.trace_fingerprint=self._trace_hash()

    def _trace_hash(self):
        session=self.live_session
        return hashlib.sha256(json.dumps([session.trace,session.diagnostics,session.requests,session.received],sort_keys=True).encode()).hexdigest()

    def assert_publishable(self):
        session=self.live_session
        with session.service.lock:
            session.check()
            if self.trace_fingerprint!=self._trace_hash():raise ResearchError('research_source_invalid')
            for approval in self.approvals:
                if approval.external_processing_reviewed and not session.service.external_allowed(approval):
                    raise ResearchError('research_external_not_approved')
            super().assert_publishable()

    @contextmanager
    def publication_guard(self):
        with self.live_session.service.lock,super().publication_guard():yield

    def receipt(self):
        value=super().receipt();session=self.live_session
        return {**value,'observation_method':'bounded_https_transient_html; real origin only when transport succeeds',
            'received_bytes':session.received,'http_requests':session.requests,
            'discovery_receipts':list(session.trace),'discovery_diagnostics':list(session.diagnostics),
            'input_boundary':'transient_html_service_excerpts',
            'raw_html_retained':False,'privacy_scope':'Conservative filtering; not a general anonymity proof'}


class LiveResearchService(ResearchService):
    automatic_municipal=True
    observation_method='opt_in_bounded_live_html; no source cache'

    @classmethod
    def from_reviewed_policy(cls,path,*,enabled=False,transport=None,external_policy=None):
        municipalities,approvals,details=load_research_policy(path,details=True)
        if municipalities is None or len(municipalities.entries)!=46:
            raise ValueError('Live municipal discovery requires the complete reviewed roster')
        return cls(municipalities,approvals=approvals,enabled=enabled,transport=transport,
                   authorities=details['public_authorities'],external_policy=external_policy,
                   supplementary_sites=details.get('supplementary_sites',()))

    def __init__(self,municipalities,*,approvals=(),enabled=False,transport=None,authorities=(),external_policy=None,
                 supplementary_sites=(),reviewed_fetcher=None,discoverer=None):
        super().__init__(approvals,municipalities=municipalities)
        self.live_enabled=enabled is True;self.transport=transport or LiveTransport()
        self.authorities=tuple(MappingProxyType(dict(a)) for a in authorities)
        self.supplementary_sites=tuple(MappingProxyType(validate_supplementary_site(s)) for s in supplementary_sites)
        self.external_policy=external_policy  # No CLI/environment blanket cloud permission.
        self.municipal_authorized=lambda:self.configured()
        self.observation_method=type(self).observation_method
        # General cross-topic discovery uses the same reviewed catalog. Only
        # exact full-response non-personal text approvals enter this transport;
        # dynamic HTML still has its separate narrow typed admission profiles.
        from .retrieval import PreparedPublicTransport
        prepared=reviewed_fetcher or PreparedPublicTransport(dict(self.approvals),
            authorized=lambda:self.configured(),input_authorized=lambda:self.configured())
        self.reviewed_sources=ResearchService(approvals,fetcher=prepared,municipalities=municipalities,
            municipal_authorized=lambda:self.configured(),discoverer=discoverer,
            external_authorized=lambda a:self.external_policy is None or self.external_allowed(a))

    def configured(self):
        return bool(self.live_enabled and not self.revoked and self.municipalities is not None
                    and self.municipalities.entries and all(m.current() for m in self.municipalities.entries.values()))

    def external_allowed(self,approval):
        return bool(self.external_policy and self.external_policy(approval.url,approval.text_sha256))

    def context_terms(self,question):
        validate_message(question)
        topic=service_topic(question)
        return [topic] if topic else []

    def _discover(self,session,host,topic,municipality,question,tier,*,start_url=None,max_requests=6,max_depth=2):
        first_request=session.requests
        session.site(host)
        queue=[(start_url or 'https://'+host+'/',0)];seen=set();selected=[]
        words=SERVICES.get(topic,((topic,),''))[0]
        overview=school_overview(question) if topic=='skole' and tier==1 else None
        def relevant(text):return any(word in text.casefold() for word in words)
        while queue and session.requests<8 and session.requests-first_request<max_requests and len(selected)<2:
            url,depth=queue.pop(0)
            if url in seen:continue
            seen.add(url);raw,record,modified=session.get(url)
            session.check()
            try:parsed=ServiceHTML.parse(raw)
            except ResearchError as error:
                session.diagnose('parser_rejected',url,error_code=error.code)
                raise
            finally:del raw
            try:
                metadata_depth=0
                for block,kind in zip(parsed.blocks,parsed.block_kinds):
                    if kind.startswith('scope_enter:'):metadata_depth+=1;continue
                    if kind.startswith('scope_exit:'):metadata_depth-=1;continue
                    found=re.match(r'^(?:sist\s+endret|sist\s+oppdatert|oppdatert)\s*[:.]?\s*('+DATE_TOKEN+r')\b',block,re.I)
                    if found:
                        value=literal_date(found[1]).isoformat()
                        if parsed.updated is None and metadata_depth==0:parsed.updated=value
                    found=re.match(r'^publisert\s*[:.]?\s*('+DATE_TOKEN+r')\b',block,re.I)
                    if found:
                        value=literal_date(found[1]).isoformat()
                        if parsed.published is None and metadata_depth==0:parsed.published=value
            except ValueError:
                session.diagnose('publisher_date_rejected',url)
                raise ResearchError('research_source_invalid') from None
            path_topic=topic if relevant(unquote(urlsplit(url).path)) else None
            active_topic=path_topic;headings=[];group=None;group_unknown=False;excerpts=[];rejections={};contexts=[]
            inherited=();inherited_groups=();inherited_unknown=False
            def reject(reason):rejections[reason]=rejections.get(reason,0)+1
            for block,kind in zip(parsed.blocks,parsed.block_kinds):
                if kind.startswith('scope_enter:'):
                    contexts.append((active_topic,list(headings),group,group_unknown,inherited,inherited_groups,inherited_unknown))
                    inherited=(*inherited,*headings)
                    inherited_groups=(*inherited_groups,*((group,) if group else ()))
                    inherited_unknown=inherited_unknown or group_unknown
                    headings=[];group=None;group_unknown=False
                    continue
                if kind.startswith('scope_exit:'):
                    if not contexts:raise ResearchError('research_source_invalid')
                    active_topic,headings,group,group_unknown,inherited,inherited_groups,inherited_unknown=contexts.pop()
                    continue
                if kind.startswith('barrier:'):
                    lost_kind=kind.split(':',1)[1]
                    if lost_kind in ('h1','h2','h3','h4','h5','h6'):
                        level=int(lost_kind[1]);headings=[h for h in headings if h[0]<level]
                        headings.append((level,None,frozenset()))
                    group=None;group_unknown=True
                    reject('discarded_scope_barrier');continue
                if not block:continue  # Formatting whitespace is not a lost condition.
                if re.fullmatch(r'(?:publisert(?:\s*/\s*sist\s+endret)?|sist\s+endret|sist\s+oppdatert|oppdatert)'
                        r'\s*[:.]?\s*'+DATE_TOKEN+r'\s*\.?',block,re.I):
                    # Known publisher metadata is neither service evidence nor
                    # an unknown eligibility label. Combined labels stay unknown
                    # as to published-versus-updated; never infer their meaning.
                    reject('publisher_metadata_not_evidence');continue
                mentioned=service_topics(block)
                if kind in ('h1','h2','h3','h4','h5','h6'):
                    level=int(kind[1]);headings=[h for h in headings if h[0]<level];group=None;group_unknown=False
                    if safe_text(block,municipality,minimum=1) is None:
                        active_topic=None;headings.append((level,None,frozenset()))
                        reject('heading_screened');continue
                    headings.append((level,block,frozenset(mentioned)))
                    active_topic=path_topic
                    for _,_,topics in (*inherited,*headings):
                        if topics:active_topic=next(iter(topics)) if len(topics)==1 else None
                    continue
                if inherited_unknown or any(label is None for _,label,_ in (*inherited,*headings)):
                    reject('heading_scope_unknown');continue
                # Short grade/place labels scope following list rows but cannot
                # establish freshness. Only explicit price-section headings do.
                if (block.endswith(':') or re.match(r'^(?:[1-7]\.?\s*[-–]\s*)?[1-7]\.?\s*trinn\b',block,re.I)
                        or block.casefold() in ('enkeltdag','for alle','hel plass','halv plass')):
                    group=None;group_unknown=True
                    grade_label=re.fullmatch(r'(?:(?:hel|halv)\s+plass\s+)?(?:[1-7]\.?\s*[-–]\s*)?[1-7]\.?\s*trinn\b[^:]{0,130}:?',block,re.I)
                    other_label=re.fullmatch(r'(?:enkeltdag|for alle|hel plass|halv plass)\s*:?',block,re.I)
                    if (len(block)<=180 and (grade_label or other_label) and (not mentioned or mentioned=={topic})
                            and safe_text(block,municipality,minimum=1)):
                        group=block;group_unknown=False
                    else:reject('group_scope_unknown')
                    continue
                if group_unknown:reject('group_scope_unknown');continue
                if mentioned and mentioned!={topic}:
                    group=None;group_unknown=True;reject('other_service');continue
                detail=PRICE.search(block) or re.search(r'\b(?:\w*frist\w*|innen|søknad\w*|åpningstid\w*|åpent|åpner|stenger)\b',block,re.I)
                monetary=bool(re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\bgratis\b',block,re.I))
                if monetary and active_topic==topic:
                    if any(not fee_period_matches(p,question) for p in re.findall(PERIOD_TOKEN,block)):
                        reject('unsupported_question_or_period');continue
                    detail=True
                # Every excerpt retains ALL active safe headings/group text,
                # including a single conditional heading and a self-dated row.
                # This applies to fees, deadlines, hours and general rules alike.
                # Existing size/privacy/period checks refuse an unsafe whole unit;
                # no convenient subset or inferred year replaces lost context.
                labels=[label for _,label,_ in (*inherited,*headings)]
                unit=' | '.join(dict.fromkeys(x for x in (*labels,*inherited_groups,group,block) if x))
                if re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',unit):
                    # No automatic footnote resolution/omission. A marked price
                    # or rule needs a whole separately reviewed conditional unit.
                    group=None;group_unknown=True;reject('unresolved_footnote');continue
                value=safe_text(unit,municipality)
                if value is None:
                    group=None;group_unknown=True;reject('text_or_privacy_screened');continue
                if not public_service_unit(value,municipality):
                    group=None;group_unknown=True;reject('unreviewed_public_field');continue
                if value and (mentioned=={topic} or active_topic==topic and detail):
                    if len(value.split())<5:reject('insufficient_text');continue
                    if not supports_question(value,question):reject('unsupported_question_or_period');continue
                    excerpts.append(value)
                else:reject('no_service_context')
            directory_items=()
            if overview:
                # Directory labels never enter the ordinary free-text allowlist.
                # Aggregate the complete admitted set on THIS page, never the
                # first three names or a navigation/contact/SFO substitute.
                directory_items=school_directory(parsed,url,municipality,overview)
                excerpts=[]
                if directory_items:
                    label={'barneskole':'Barneskoler','ungdomsskole':'Ungdomsskoler','skole':'Skoler'}[overview]
                    unit=' | '.join((label,*(name for name,_,_ in directory_items)))
                    if len(unit)>900:raise ResearchError('research_source_limit')
                    excerpts=[unit]
                else:reject('no_documented_school_directory')
            diagnostic=dict(depth=depth,main_roots=parsed.main_roots,article_roots=parsed.article_roots,
                blocks=len(parsed.blocks),links=len(parsed.links),forms=len(parsed.forms),
                retained_units=len(set(excerpts)),directory_items=len(directory_items),rejections=rejections)
            # Search-result snippets are navigation, never final citation evidence.
            if excerpts and not urlsplit(url).query:
                if modified:
                    try:
                        when=parsedate_to_datetime(modified)
                        if when.tzinfo is None or when>datetime.now(timezone.utc):raise ValueError()
                    except (ValueError,TypeError,OverflowError):raise ResearchError('research_source_invalid') from None
                key=(municipality.id if municipality else 'public')+'-live-'+hashlib.sha256(url.encode()).hexdigest()[:12]
                today=date.today().isoformat();observed=datetime.fromisoformat(record['retrieved_at'])
                paragraphs=tuple(ResearchExcerpt('p'+str(i+1),text) for i,text in enumerate(dict.fromkeys(excerpts)) if i<3)
                approval=LiveApproval(source_id=key,url=url,title=(municipality.name if municipality else
                    'Offentlig kilde' if tier==2 else 'Supplerende kilde')+' – '+topic,
                    keywords=(topic,),excerpts=paragraphs,reviewed_on=today,expires_on=today,
                    robots_sha256=hashlib.sha256(session.robots[host]).hexdigest(),reuse_reviewed=True,
                    non_personal_input_reviewed=False,external_processing_reviewed=False,content_type='text/html',
                    review_scope='transient_html_service_excerpts',authority_tier=tier,
                    municipality_id=municipality.id if municipality else None,category=SERVICES.get(topic,((), 'teknisk'))[1],
                    raw_response_sha256=record['raw_sha256'],retrieved_at=record['retrieved_at'],
                    published_at=source_date(parsed.published,observed),updated_at=source_date(parsed.updated,observed),
                    last_modified=modified,effective_periods=tuple(dict.fromkeys(p for text in excerpts
                        for p in (fee_periods(text) if PRICE.search(question) else effective_periods(text)))),
                    directory_kind=overview,directory_items=directory_items)
                selected.append((approval,record))
                if len(selected)>=2:break
            if depth>=max_depth:
                session.diagnose('page_evaluated',url,**diagnostic,stop='depth_limit');continue
            links=[]
            for href,label in parsed.links[:256]:
                if not relevant(label+' '+unquote(href)):reject('link_not_relevant');continue
                if not safe_text(label,municipality,minimum=1) and not (overview and label.casefold() in _SCHOOL_NAV):
                    reject('link_screened');continue
                if overview and re.search(r'\bsfo\b|skolefritidsordning',label,re.I):
                    reject('other_service');continue
                candidate=urljoin(url,href).split('#',1)[0]
                try:safe_url(candidate,session.hosts)
                except (ResearchError,ValueError):reject('link_url_rejected');continue
                if urlsplit(candidate).hostname!=host or re.search(r'\.(?:pdf|docx?|xlsx?|png|jpg|zip)$',urlsplit(candidate).path,re.I):
                    reject('link_host_or_format');continue
                score=(3*int(label.casefold() in _SCHOOL_HEADINGS) if overview else
                    3*int(bool(PRICE.search(label+' '+href))))+int(relevant(label))
                links.append((-score,candidate))
            # Newly found service/price links precede generic queued navigation;
            # repeated global menus cannot consume the bounded request budget.
            new_links=[(candidate,depth+1) for _,candidate in sorted(set(links))[:12] if candidate not in seen]
            queue=new_links+[item for item in queue if item[0] not in {url for url,_ in new_links}]
            if depth==0:
                for form in parsed.forms[:1]:
                    target=urljoin(url,form['action']);parts=urlsplit(target)
                    term={'barneskole':'barneskoler','ungdomsskole':'ungdomsskoler'}.get(overview,topic)
                    target=urlunsplit((parts.scheme,parts.netloc,parts.path or '/',urlencode({form['field']:term}),''))
                    if urlsplit(target).hostname!=host:continue
                    try:
                        safe_url(target,session.hosts,search=True)
                        robots_interval(session.robots[host],target,AGENT)
                    except (ResearchError,ValueError):continue
                    queue.append((target,1))
            session.diagnose('page_evaluated',url,**diagnostic,queued_candidates=len(queue))
        session.diagnose('discovery_complete',retained_pages=len(selected),requests=session.requests-first_request,
            pending_candidates=len(queue),request_limit_reached=bool(queue and (session.requests>=8 or session.requests-first_request>=max_requests)))
        return selected

    def prepare(self,question,*,provider,authorized,municipality_context=None,require_municipal=False):
        from .question_router import canonical_question
        question=canonical_question(question)
        validate_message(question);owner=current_run()
        if owner is None or not authorized() or not self.configured():raise ResearchError('research_unavailable')
        municipal=require_municipal or municipal_question(question)
        if self.approvals:
            revision,registry,catalog=self.revision,self.municipalities,self.approvals
            fingerprint=registry.fingerprint()
            selected=[]
            def still_authorized():
                return (authorized() and self.configured() and self.revision==revision
                    and self.municipalities is registry and registry.fingerprint()==fingerprint and self.approvals is catalog
                    and (provider!='openai' or self.external_policy is None
                        or all(self.external_allowed(a) for a in selected)))
            try:
                binding=self.reviewed_sources.prepare(question,provider=provider,authorized=still_authorized,
                    municipality_context=municipality_context,require_municipal=municipal)
                selected.extend(binding.approvals)
                if provider=='openai' and self.external_policy is not None and not all(self.external_allowed(a) for a in selected):
                    raise ResearchError('research_external_not_approved')
                binding.assert_publishable()
                return binding
            except ResearchError as error:
                if error.code not in ('research_no_official_sources','research_no_sources'):raise
        entry=self.municipalities.resolve(question,municipality_context) if municipal else None
        if municipal and entry is None:raise ResearchError('research_municipality_required')
        topic=service_topic(question)
        if topic is None:raise ResearchError('research_no_sources')
        if provider=='openai' and self.external_policy is None:raise ResearchError('research_external_not_approved')
        authorities=[a for a in self.authorities if date.fromisoformat(a['reviewed_on'])<=date.today()<=date.fromisoformat(a['expires_on'])]
        supplements=[s for s in self.supplementary_sites if date.fromisoformat(s['reviewed_on'])<=date.today()<=date.fromisoformat(s['expires_on'])]
        hosts=([entry.official_host] if entry else [])+[a['official_host'] for a in authorities]+[urlsplit(s['url']).hostname for s in supplements]
        request_id=uuid.uuid4().hex;started=datetime.now(timezone.utc)
        session=LiveSession(self,owner,request_id,started,authorized,hosts)
        try:return self._prepare_session(session,question,provider,entry,municipal,topic,authorities,supplements)
        except ResearchError as error:
            session.diagnose('request_refused',error_code=error.code)
            error.source_diagnostics=tuple(session.trace+session.diagnostics)
            raise

    def _prepare_session(self,session,question,provider,entry,municipal,topic,authorities,supplements):
        request_id,started=session.request_id,session.started
        if school_overview(question) and entry and not school_directory_query_supported(question,entry):
            # Names/type/place are the supported fields. Do not answer an
            # unsupported ownership/status/facility/period filter with all names.
            raise ResearchError('research_no_sources')
        selected=self._discover(session,entry.official_host,topic,entry,question,1) if entry else []
        # Supplements never substitute for absent municipal conditions.
        if municipal and not selected:raise ResearchError('research_no_official_sources')
        compare=bool(re.search(r'\b(?:sammenlign\w*|motstrid\w*|nasjonal\w*|statlig\w*)\b',question,re.I))
        if not municipal or compare:
            for authority in authorities[:2]:
                if session.requests>=8 or len(selected)>=4:break
                selected.extend(self._discover(session,authority['official_host'],topic,None,question,2,max_requests=3))
                if selected and not compare:break
        if not selected and not municipal:
            for site in supplements:
                if session.requests>6:break
                selected.extend(self._discover(session,urlsplit(site['url']).hostname,topic,None,question,3,
                    start_url=site['url'],max_depth=0,max_requests=2))
                if selected:break
        if not selected:raise ResearchError('research_no_sources')
        session.check();approvals=[];observations=[]
        for approval,record in selected[:4]:
            observed=datetime.fromisoformat(record['retrieved_at'])
            if (record['request_id']!=request_id or not started<=observed<=datetime.now(timezone.utc)
                    or record['url']!=approval.url or record['raw_sha256']!=approval.raw_sha256):
                raise ResearchError('research_source_invalid')
            if provider=='openai':
                if not self.external_allowed(approval):raise ResearchError('research_external_not_approved')
                from dataclasses import replace
                approval=replace(approval,external_processing_reviewed=True)
            approvals.append(approval)
            observations.append(dict(source_id=approval.source_id,url=approval.url,request_id=request_id,
                retrieved_at=approval.retrieved_at,published_at=approval.published_at,updated_at=approval.updated_at,
                last_modified=approval.last_modified,effective_periods=list(approval.effective_periods),
                raw_sha256=approval.raw_sha256,text_sha256=approval.text_sha256,bytes=record['bytes'],
                input_boundary=approval.review_scope,raw_content_type='text/html'))
        private=ResearchService(approvals,municipalities=self.municipalities)
        facts={}
        for approval in approvals:
            for excerpt in approval.excerpts:
                text=excerpt.text;periods=effective_periods(text)
                amounts=list(re.finditer(r'\b(\d[\d .,]*?)\s*(?:kr\b|kroner\b|,-)',text,re.I))
                if len(periods)==1 and len(amounts)==1:
                    prefix=' '.join(text[:amounts[0].start()].casefold().split())
                    if len(prefix)>=6:
                        # Heading-qualified units can exceed the old80-character
                        # prefix. Hash the entire bounded prefix; never omit the
                        # same-literal-scope conflict check because it is longer.
                        scope=(topic,hashlib.sha256(prefix.encode()).hexdigest(),periods[0],approval.municipality_id,'NOK')
                        facts.setdefault(scope,set()).add(amounts[0][1].replace(' ',''))
        if any(len(values)>1 for values in facts.values()):raise ResearchError('research_source_conflict')
        return LiveBinding(private,session,tuple(approvals),observations,entry,municipal)

    def verify(self,answer,binding):
        result=super().verify(answer,binding)
        result['source_checked_at']=max(r['retrieved_at'] for r in binding.observations)
        result['source_cautions']=['Nylig kildekontroll beviser ikke at opplysningene gjelder nå.']
        result['verification_scope']=('Exact request-bound filtered HTML excerpt; not factual truth, anonymity or human paragraph review'
            if isinstance(binding,LiveBinding) else 'Exact request-bound reviewed text; not factual truth or completeness')
        self._directory_notice(result,binding,append_text=True)
        if result.get('overview_complete') is False:
            result['verification_scope']='Exact request-bound official school-directory fields; not completeness, truth or general anonymity'
        return result

    @staticmethod
    def _directory_notice(value,binding,*,append_text=False):
        if any(getattr(a,'directory_kind',None) for a in binding.approvals):
            # One server-owned overlay for chat AND municipal search/answer.
            notice='Dette er dokumenterte oppføringer fra kilden. Kildekontrollen bekrefter ikke at listen er komplett.'
            value['overview_complete']=False;value['coverage']=notice
            value['source_cautions']=[*value.get('source_cautions',()),notice]
            if append_text:value['text']+='\n\n'+notice

    def portal_search(self,question,workflow,*,category=None):
        from .source_updates import BoundPortalResult
        binding=self.retrieve_for_query(question,provider=workflow.provider)
        binding.assert_publishable()
        results=[]
        for document in binding.index.documents.values():
            if category is not None and document.category!=category:continue
            results.append({**document.provenance(),'score':1.,'excerpt':document.source.paragraphs[0].text,
                'paragraph_ids':[p.id for p in document.source.paragraphs]})
        value=dict(query='',category=category,results=results,provider=workflow.provider,
            municipality_id=binding.municipality.id,official_menu_url='https://'+binding.municipality.official_host+'/',
            coverage='Fersk, avgrenset kildekontroll. Ikke fullstendig kommunal dekning.',
            source_observation=binding.receipt(),source_receipts=list(binding.observations))
        self._directory_notice(value,binding)
        return BoundPortalResult(value,binding)

    def portal_answer(self,question,workflow,*,category=None,prior_terms=(),prior_municipality=None):
        from .schemas import Source,Paragraph
        from .source_updates import BoundPortalResult
        from .search import validate_query_privacy
        validate_query_privacy(question);validate_message(question)
        topic=service_topic(question)
        if topic is None:topic=next((term for term in prior_terms if term in SERVICES),None)
        if topic is None:raise ResearchError('research_no_sources')
        if category is not None and SERVICES[topic][1]!=category:raise ResearchError('research_no_sources')
        effective=question if service_topic(question) else question+' '+topic
        binding=self.retrieve_for_query(effective,provider=workflow.provider,municipality_context=prior_municipality)
        paragraphs=[];citations=[]
        for document in binding.index.documents.values():
            for paragraph in document.source.paragraphs:
                key=document.source.id+':'+paragraph.id
                paragraphs.append(Paragraph(key,paragraph.text))
                citations.append({'paragraph_id':key,**document.provenance()})
        source=Source('portal-search-context','Kontrollerte kommunale tjenesteutdrag',tuple(paragraphs),False)
        view=workflow.for_snapshot(binding)
        result=view.run_context(source)
        data=json.loads(result.to_json())
        data['evidence_policy']='filtered_html_excerpt_verbatim'
        binding.assert_publishable()
        if result.verification.has_findings:raise ResearchError('research_claim_unsupported')
        value=dict(query='',answer_status='evidence_checked',result=data,citations=citations,
            municipality_id=binding.municipality.id,official_menu_url='https://'+binding.municipality.official_host+'/',
            is_follow_up=service_topic(question) is None and bool(prior_terms),
            message='Kildebasert utdrag. Kontroller at kildens periode passer spørsmålet.',
            coverage='Fersk, avgrenset kildekontroll. Ikke fullstendig kommunal dekning.',
            source_observation=binding.receipt(),source_receipts=list(binding.observations),
            source_checked_at=max(o['retrieved_at'] for o in binding.observations),
            source_cautions=['Nylig kildekontroll beviser ikke at opplysningene gjelder nå.'])
        self._directory_notice(value,binding)
        return BoundPortalResult(value,binding)
