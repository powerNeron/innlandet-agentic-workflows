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
                       ResearchService, load_research_policy, municipal_question,validate_supplementary_site,FEE_INTENT,school_overview,
                       PERIOD_TOKEN,MONTHS,DATE_TOKEN,literal_date,fee_periods,fee_period_matches)
from .retrieval import _pinned_public_connection, _validate_url
from .robots_policy import robots_interval
from .run_control import bounded_tool_call, current_run

AGENT = 'HamarKommuneAgent/0.3'
SERVICES = {
    'dagsenter': (('dagsenter','dagtilbud','aktivitetstilbud'), 'helse'),
    'hjemmehjelp': (('hjemmehjelp','hjemmetjeneste'), 'helse'),
    'transport': (('transport','skyss'), 'helse'),
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
    UI_ROLES=frozenset(('navigation','banner','contentinfo','search'))
    SEARCH_FIELDS=frozenset(('q','query','search','searchtext','searchstring','sok','søk'))
    SEARCH_UI_WORDS=frozenset(('search søk sok søke søkefelt søkeord søketekst nettsted nettstedet '
        'nettside nettsiden side siden på i etter innhold go finn menu main meny hovedmeny '
        'navigation navigasjon hovednavigasjon banner content info').split())
    PRINT_ATTRIBUTES=frozenset(('type','onclick','id','class','style','role','name','value','disabled','tabindex','title','aria-label','aria-description'))
    TEXT_ANNOTATIONS=frozenset(('title','aria-label','aria-description','aria-valuetext','aria-roledescription'))
    TEXT_REFERENCES=frozenset(('aria-labelledby','aria-describedby','aria-details','aria-errormessage','aria-controls','aria-owns'))
    STRUCTURE_LABEL=re.compile(r'(?:ingress|innleiing|innledning|introduksjon|intro|introduction|lead|'
        r'innhald|innhold|hovudinnhald|hovedinnhold|sideinnhold|artikkelinnhold|artikkeltekst|brødtekst|'
        r'artikkel|article|content|main content|body|body text)',re.I)
    FIELD_ROLES=frozenset(('textbox','searchbox','combobox','listbox','option','spinbutton','slider','checkbox','radio','switch'))
    READ_ONLY_ROLES=frozenset(('document','main','article','region','group','tabpanel','heading','paragraph',
        'list','listitem','table','rowgroup','row','columnheader','rowheader','cell','img','none','presentation',
        'navigation','banner','contentinfo','search','separator','note','status','alert','figure','definition','term'))
    UNSUPPORTED_STYLE=re.compile(r'vertical-align\s*:\s*super\b|\b(?:content|counter(?:-reset|-increment|-set)?|quotes)\s*:|url\s*\(',re.I)
    STATIC_TAGS=frozenset(('div','section','p','ul','ol','li','h1','h2','h3','h4','h5','h6','span',
        'strong','em','b','i','u','s','small','br','table','thead','tbody','tfoot','tr','th','td','caption',
        'dl','dt','dd','blockquote','a','img'))
    STATIC_ROLES={'div':{'group','region','tabpanel'},'section':{'group','region','tabpanel'},
        'ul':{'list'},'ol':{'list'},'li':{'listitem'},'a':{'link'},'table':{'table'},
        'thead':{'rowgroup'},'tbody':{'rowgroup'},'tfoot':{'rowgroup'},'tr':{'row'},
        'th':{'columnheader','rowheader','cell'},'td':{'cell'}}
    DIAGNOSTIC_ARIA=frozenset(('aria-hidden','aria-live','aria-atomic','aria-busy','aria-relevant','aria-expanded',
        'aria-required','aria-disabled','aria-selected','aria-checked','aria-pressed','aria-level','aria-modal',
        'aria-haspopup','aria-current'))|TEXT_ANNOTATIONS|TEXT_REFERENCES
    DIAGNOSTIC_TAGS=frozenset(('html','head','body','main','article','header','nav','section','div','aside','footer',
        'form','details','fieldset','button','input','textarea','select','option','label','p','ul','ol','li','span'))
    def __init__(self,*,public_layout=False,disclosures=None):
        super().__init__(convert_charrefs=True)
        self.public_layout=public_layout;self.content_titles=[];self.title_parts=[];self.title_overflow=False
        self.content_root_refusal=None
        self.scope_owner_ids={};self.next_owner_id=0;self.block_owners=[];self.topic_titles={};self.unit_contexts=[]
        self.article_owner_paths=[];self.heading_diagnostics=dict(seen=0,inactive=0,blocked=0)
        self.structure_nodes=[];self.control_diagnostics=[];self.layout_search_forms={};self.control_labels={};self.ui_positions={}
        self.annotations=[];self.metadata_diagnostics=[];self.node_metadata={};self.heading_ids={};self.id_counts={};self.id_nodes={}
        self.unit_decisions=[];self.control_references={};self.control_text={}
        self.disclosures=disclosures or {};self.collect_dom=public_layout and disclosures is None
        self.dom={};self.dom_positions={};self.dom_text=[];self.disclosure_ranges=[];self.disclosure_positions={}
        self.disclosure_diagnostics=[]
        self.wrapper_forms={};self.form_control_owners=set()
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

    def flush(self,*,kind=None):
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
            if len(self.blocks)>=(1024 if self.public_layout else 256) or self.extracted_bytes>65536:raise ResearchError('research_source_limit')
            self.blocks.append(text)
            kind=kind or next((tag for tag,_ in reversed(self.stack) if tag in ('h1','h2','h3','h4','h5','h6','p','tr','li','summary','legend')),
                'block' if self.public_layout else '')
            if self.public_layout and kind=='h1':
                label=None if overflow else text;self.content_titles.append(label)
                self.topic_titles.setdefault(self.owner_path(),[]).append((label,len(self.blocks)-1))
            self.block_kinds.append('barrier:'+kind if overflow else kind)
            self.block_owners.append(self.owner_path())
            if re.fullmatch(r'h[1-6]',kind):
                level=int(kind[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]
                start=self.directory_heading_starts.pop(level,len(self.directory_links))
                for i in range(start,len(self.directory_links)):
                    href,label,eligible,context=self.directory_links[i]
                    if text!=label:self.directory_links[i]=(href,label,eligible,(*context,(level,None if overflow else text)))
                self.directory_headings.append((level,None if overflow else text))
            elif kind in ('summary','legend'):
                self.directory_headings.append((0,None if overflow else text))
            elif text and not self.anchor and kind in ('p','li','tr') and not any(
                    row['start']<len(self.directory_links) for row in self.directory_rows.values()):
                if not re.fullmatch(r'(?:publisert|sist endret|sist oppdatert|oppdatert)\s*[:.]?\s*'+DATE_TOKEN+r'\s*\.?',text,re.I):
                    # A standalone label/condition must not disappear between
                    # the category heading and its institution records.
                    self.directory_headings=[h for h in self.directory_headings if h[0]!=7]+[(7,None if overflow else text)]

    def active(self):
        return any(tag in ('main','article') or i in self.main_positions or i in self.article_positions for i,(tag,_) in enumerate(self.stack))

    def owner_path(self):return tuple(self.scope_owner_ids[position] for position in sorted(self.scope_owner_ids))

    def form_text_allowed(self):
        return all(self.wrapper_forms.get(i,False) for i,(tag,_) in enumerate(self.stack) if tag=='form')

    def scope_event(self,kind):
        if len(self.blocks)>=(1024 if self.public_layout else 256):raise ResearchError('research_source_limit')
        self.blocks.append('');self.block_kinds.append(kind)
        self.block_owners.append(self.owner_path())

    def _search_ui_text(self,state,text):
        if state['chars']+len(text)>300:state['valid']=False;return
        state['chars']+=len(text);state['text'].append(text)

    def _search_ui_attributes(self,state,attrs):
        if self.UNSUPPORTED_STYLE.search(attrs.get('style','')):state['valid']=False
        for key in ('aria-label','title','placeholder','alt'):
            if attrs.get(key):self._search_ui_text(state,attrs[key])
        # Unknown accessible semantics/references can carry a condition. Do
        # not guess that an unhandled ARIA attribute is harmless decoration.
        if any(key.startswith('aria-') and key!='aria-label' for key in attrs):state['valid']=False
        if any(key in attrs for key in ('form','formaction','formmethod','formenctype','formtarget','formnovalidate','list')):state['valid']=False
        if attrs.get('role','').casefold() not in ('',*self.UI_ROLES,'none','presentation','img','group','region','searchbox','textbox','button'):state['valid']=False

    def _known_ui_words(self,parts):
        return all(word.strip(':?.') in self.SEARCH_UI_WORDS
            for word in _screening_text(' '.join(parts)).casefold().split())

    def _ui_metadata_known(self,attrs):
        state=dict(valid=True,chars=0,text=[])
        self._search_ui_attributes(state,attrs)
        return state['valid'] and self._known_ui_words(state['text'])

    def _search_ui_child(self,tag,attrs):
        for state in self.layout_search_forms.values():
            self._search_ui_attributes(state,attrs)
            if tag=='sup':state['valid']=False
            if tag=='input':
                kind=attrs.get('type','text').casefold()
                if kind=='hidden':continue  # State values are never evidence or diagnostics.
                if kind in ('search','text') and attrs.get('name','').casefold() in self.SEARCH_FIELDS:
                    state['queries']+=1
                    if attrs.get('value'):state['valid']=False  # Unreviewed prefilled query/user state.
                elif kind in ('button','submit'):
                    self._search_ui_text(state,attrs.get('value',''))
                    if attrs.get('name','').casefold() not in ('',*self.SEARCH_FIELDS):state['valid']=False
                else:state['valid']=False
            elif tag=='button':
                if attrs.get('type','submit').casefold() not in ('button','submit'):state['valid']=False
                if attrs.get('name','').casefold() not in ('',*self.SEARCH_FIELDS):state['valid']=False
            elif tag in ('form','textarea','select','option','datalist','output'):state['valid']=False

    def _finish_search_ui(self,position,*,explicit_close=False):
        state=self.layout_search_forms.pop(position)
        clean=bool(explicit_close and state['valid'] and 1<=state['queries']<=2
            and self._known_ui_words(state['text']))
        if not clean:self.form_control_owners.add(state['owner'])
        if state['event'] is not None:
            state['event'].update(layout_ui=clean,tainted=not clean,layout_search_status='clean' if clean else 'refused')

    @staticmethod
    def _control_action(labels):
        labels=[_screening_text(value).strip().casefold() for value in labels if value.strip()]
        kinds={'print':r'(?:skriv ut(?: (?:denne )?siden)?|print(?: this page)?)[.!]?',
            'share':r'(?:del(?: (?:denne )?siden)?|share(?: this page)?)[.!]?',
            'search':r'(?:søk|search)[.!]?'}
        return next((kind for kind,pattern in kinds.items() if labels and all(re.fullmatch(pattern,label) for label in labels)),'unknown')

    def _print_control_syntax(self,tag,attrs):
        """A closed read-only print action; a UI label alone grants nothing."""
        if tag not in ('button','input') or set(attrs)-self.PRINT_ATTRIBUTES:return False
        if attrs.get('role','').casefold() not in ('','button'):return False
        handler=attrs.get('onclick') or ''
        if not re.fullmatch(r'\s*(?:window\.)?print\(\)\s*;?\s*(?:return\s+false\s*;?)?\s*',handler):return False
        kind=attrs.get('type','submit' if tag=='button' else 'text').casefold()
        if kind not in ('button','submit'):return False
        if kind=='submit' and not re.search(r'\breturn\s+false\s*;?\s*$',handler):return False
        return not self.UNSUPPORTED_STYLE.search(attrs.get('style') or '')

    def _control_child(self,tag,attrs):
        for label in self.control_labels.values():
            if not label['deferred']:continue
            if tag not in ('span','i','b','strong','em','small','br'):label['structure']=False
            if set(attrs)-{'id','class','style','role','aria-hidden','aria-label','aria-description','title'}:label['structure']=False
            if attrs.get('role','').casefold() not in ('','none','presentation','img'):label['structure']=False
            if attrs.get('aria-hidden','false').casefold() not in ('true','false'):label['structure']=False
            if self.UNSUPPORTED_STYLE.search(attrs.get('style') or ''):label['structure']=False
            for key in ('aria-label','aria-description','title'):
                if attrs.get(key):label['labels'].append(attrs[key])

    def _finish_control(self,position,*,explicit_close=False):
        label=self.control_labels.pop(position)
        action='unknown' if label['overflow'] else self._control_action([*label['labels'],' '.join(label['parts'])])
        approved=bool(label['deferred'] and explicit_close and label['structure'] and action=='print')
        if label['deferred'] and not approved:self.form_control_owners.add(label['owner'])
        if label['event'] is not None:
            label['event'].update(ui_action=action,label_complete=explicit_close,nonqualifying_print=approved)
            if label['deferred']:label['event']['tainted']=not approved
            label['event']['label_words']=len(' '.join([*label['labels'],*label['parts']]).split())
            if not label['overflow']:self.control_text[label['event']['source_node']]=' '.join([*label['labels'],*label['parts']])

    @classmethod
    def structural_metadata(cls,tag,attrs):
        structural={key for key,values in (('aria-live',{'off','polite','assertive'}),
            ('aria-atomic',{'true','false'}),('aria-busy',{'false'}),('aria-hidden',{'false'})) if attrs.get(key) in values}
        relevant=attrs.get('aria-relevant','').split()
        if relevant and (relevant==['all'] or set(relevant)<={'additions','removals','text'}):structural.add('aria-relevant')
        if re.fullmatch(r'h[1-6]',tag) and attrs.get('aria-level')==tag[1]:structural.add('aria-level')
        if tag in ('main','article','section','div') and cls.STRUCTURE_LABEL.fullmatch(' '.join(attrs.get('aria-label','').split())):
            structural.add('aria-label')
        return structural

    def static_text_markup(self,node):
        """Closed inert markup vocabulary shared by wrapper and pane proofs."""
        tag=node['tag'];a=node['attrs']
        if tag not in self.STATIC_TAGS or node['ambiguous'] or not node['closed'] or node['stateful'] or node['forbidden']:return False
        if a.get('id') and self.id_counts.get(a['id'])!=1:return False
        if a.get('role','') not in {'','none','presentation'}|self.STATIC_ROLES.get(tag,set())|({'heading'} if re.fullmatch(r'h[1-6]',tag) else set()):return False
        allowed={'id','class','style','lang','dir','role','title','tabindex','contenteditable','hidden'}|self.DIAGNOSTIC_ARIA
        allowed|=({'href','target','rel'} if tag=='a' else {'colspan','rowspan','scope'} if tag in ('td','th')
            else {'src','alt','width','height','loading','decoding'} if tag=='img' else set())
        allowed|={'data-disclosure','data-collapse','data-accordion'} if tag=='div' else set()
        if set(a)-allowed:return False
        if 'contenteditable' in a and a['contenteditable'].casefold()!='false':return False
        if any(key.startswith('data-') and value not in ('','true','collapse','accordion') for key,value in a.items()):return False
        if self.UNSUPPORTED_STYLE.search(a.get('style','')):return False
        if any(key in a and not re.fullmatch(r'[1-9][0-9]?',a[key]) for key in ('rowspan','colspan')):return False
        if 'scope' in a and a['scope'] not in ('row','col','rowgroup','colgroup'):return False
        if tag=='img' and (a.get('alt')!='' or any(a.get(k) for k in self.TEXT_ANNOTATIONS|self.TEXT_REFERENCES)):return False
        return True

    def inert_layout_container(self,node,caption=None):
        if node['tag'] not in ('div','h1','h2','h3','h4','h5','h6') or node['hidden'] or not self.static_text_markup(node):return False
        structural=self.structural_metadata(node['tag'],node['attrs'])
        normal=lambda value:' '.join(_screening_text(value).casefold().split())
        for key,value in node['attrs'].items():
            if key in self.TEXT_ANNOTATIONS and value.strip():
                if key not in structural and (caption is None or normal(value)!=normal(caption)):return False
            elif key in self.TEXT_REFERENCES:
                if value.strip():return False
            elif key.startswith('aria-') and key not in structural:return False
        return True

    def _start_metadata(self,position,tag,attrs,*,ambiguous=False):
        # Accessibility text may contain a condition absent from visible prose.
        # Keep it transient and require its complete representation in a unit;
        # neither an ARIA name nor a tooltip is permission to discard it.
        if tag=='title':
            for node in self.node_metadata.values():node['qualifies_title']=True
        structural=self.structural_metadata(tag,attrs);structure_label='aria-label' in structural
        literals=tuple((key,value) for key,value in attrs.items() if key in self.TEXT_ANNOTATIONS and value.strip()
            and not (key=='aria-label' and structure_label))
        # Empty IDREFs have no target. Announcement settings and a matching
        # native heading level describe the UI, never eligibility or facts.
        references=tuple((key,value) for key,value in attrs.items() if key in self.TEXT_REFERENCES and value.strip())
        if self.nodes in self.disclosures.get('panels',{}):
            structural.add('aria-hidden')
            # The proven controller label is retained as the panel's summary.
            if attrs.get('aria-labelledby')==self.disclosures['panels'][self.nodes]['button_id']:
                references=tuple(pair for pair in references if pair[0]!='aria-labelledby')
                structural.add('aria-labelledby')
        unknown_keys=tuple(key for key in attrs if key.startswith('aria-') and key not in self.TEXT_ANNOTATIONS|self.TEXT_REFERENCES|{'aria-hidden'}|structural)
        unknown=ambiguous or bool(unknown_keys)
        unknown=unknown or 'aria-hidden' in attrs and attrs['aria-hidden'].casefold()!='false' and 'aria-hidden' not in structural
        heading_id=attrs.get('id') if re.fullmatch(r'h[1-6]',tag) else None
        if literals or references or unknown or heading_id or any(key.startswith('aria-') or key=='title' for key in attrs):
            safe_states={'false','true','off','polite','assertive','additions','removals','text','all','additions text'}
            metadata=[dict(attribute=key if key in self.DIAGNOSTIC_ARIA else 'other',
                value_state=value.casefold() if value.casefold() in safe_states else 'other',
                has_value=bool(value),tokens=len(value.split())) for key,value in attrs.items()
                if key.startswith('aria-') or key=='title']
            self.node_metadata[position]=dict(start=len(self.blocks),literals=literals,references=references,
                unknown=unknown,heading_id=heading_id,owner=self.owner_path(),
                inline=any(t in ('p','li','tr','h1','h2','h3','h4','h5','h6') for t,_ in self.stack),
                qualifies_title=tag=='title' or any(t=='title' for t,_ in self.stack),
                diagnostic=dict(source_node=self.nodes,tag=tag if tag in self.DIAGNOSTIC_TAGS or re.fullmatch(r'h[1-6]|title',tag) else 'other',
                    attributes=metadata,duplicate_attributes=ambiguous,
                    structural_attributes=sorted(structural),
                    structure_label_class='layout' if structure_label else 'none',
                    empty_reference_attributes=sorted(key for key in self.TEXT_REFERENCES if key in attrs and not attrs[key].strip()),
                    unsupported_attributes=[key if key in self.DIAGNOSTIC_ARIA else 'other' for key in unknown_keys]))

    def _finish_metadata(self,position,*,explicit_close=False):
        node=self.node_metadata.pop(position)
        start=node['start'];end=max(start+int(node['inline']),len(self.blocks))
        if node['heading_id']:
            # Only one complete native heading can resolve a source reference.
            labels=[i for i in range(start,min(end,len(self.blocks)))
                if re.fullmatch(r'h[1-6]',self.block_kinds[i])]
            value=labels[0] if explicit_close and len(labels)==1 else None
            identifier=node['heading_id']
            self.heading_ids[identifier]=None if identifier in self.heading_ids else value
        evidence_check=bool(node['literals'] or node['references'] or node['unknown'])
        node['diagnostic'].update(block_start=start,block_end=end,owner=list(node['owner']),closed=explicit_close,
            requires_evidence_check=evidence_check or not explicit_close)
        if node['diagnostic']['attributes'] or node['diagnostic']['duplicate_attributes']:
            self.metadata_diagnostics.append(node['diagnostic'])
        if evidence_check or not explicit_close:
            node.update(end=end,unknown=node['unknown'] or not explicit_close)
            self.annotations.append(node)

    def annotation_rejection(self,components,component_indices,*,document_title=False):
        """First concrete, closed refusal reason; no attribute text or raw IDs."""
        normal=lambda value:' '.join(_screening_text(value).casefold().split())
        represented={normal(value) for value in components if value}
        for node in self.annotations:
            if not (document_title and node['qualifies_title']
                    or any(node['start']<=i<node['end'] for i in component_indices)):continue
            base=dict(source_node=node['diagnostic']['source_node'])
            if node['unknown']:
                return dict(base,reason='duplicate_attributes' if node['diagnostic']['duplicate_attributes'] else
                    'unclosed_annotation' if not node['diagnostic']['closed'] else 'unsupported_attribute_semantics')
            for attribute,value in node['literals']:
                if normal(value) not in represented:return dict(base,reason='unrepresented_attribute_text',attribute=attribute)
            for attribute,reference in node['references']:
                ids=reference.split()
                # Text equality cannot borrow a similarly named sibling heading.
                # Resolve to an actual complete heading in THIS unit's lineage.
                if not ids:return dict(base,reason='empty_reference',attribute=attribute)
                for identifier in ids:
                    count=self.id_counts.get(identifier,0)
                    target=self.id_nodes.get(identifier,{})
                    detail=dict(base,attribute=attribute,target_node=target.get('source_node'),target_tag=target.get('tag'),
                        target_block=self.heading_ids.get(identifier))
                    if count!=1:return dict(detail,reason='missing_reference_target' if not count else 'duplicate_reference_target')
                    if self.heading_ids.get(identifier) is None:return dict(detail,reason='target_is_not_complete_native_heading')
                    if self.heading_ids[identifier] not in component_indices:return dict(detail,reason='reference_outside_unit_context')
        return None

    def annotations_match(self,components,component_indices,*,document_title=False):
        return self.annotation_rejection(components,component_indices,document_title=document_title) is None

    def finalise_control_diagnostics(self):
        for event in self.control_diagnostics:
            relation=self.control_references.get(event['source_node'],{})
            targets=[]
            for identifier in relation.get('controls',())[:4]:
                target=self.id_nodes.get(identifier,{})
                targets.append(dict(source_node=target.get('source_node'),tag=target.get('tag'),owner=target.get('owner'),
                    unique=self.id_counts.get(identifier)==1,blocked=target.get('blocked'),
                    reciprocal_label=bool(relation.get('id') and relation['id'] in target.get('labelledby',()))))
            event['controlled_targets']=targets
        self.control_references.clear()

    def static_disclosure_plan(self):
        """Nominate complete static widgets, never facts or permission to fetch.

        Only a closed, non-submitting controller, at most four inert single-child
        wrappers, and the next sibling panel may use the existing details/summary
        source grouping. The same parser then
        reads the SAME bytes, lifting only that panel's own disclosure hiding.
        Unknown fields, conditions, omitted text and other controls keep their
        original barriers. Raw DOM/labels are transient and never diagnostics.
        """
        from .internet_research import public_unit
        buttons=[n for n in self.dom.values() if n['tag']=='button' and n['attrs'].get('aria-controls')]
        if len(buttons)>64:return {}
        targets={}
        for node in buttons:
            for identifier in node['attrs']['aria-controls'].split():targets[identifier]=targets.get(identifier,0)+1
        proposed={};diagnostics=[]
        normal=lambda text:' '.join(_screening_text(text).casefold().split())
        def text_in(node):
            return ''.join(data for _,data in self.dom_text[node['text_start']:node['text_end']])
        def panel_text(node):
            # Preserve block boundaries without splitting an inline identity
            # into independently screened fragments or gluing headings to prose.
            parts=[];current=None;buffer=[]
            for source,data in self.dom_text[node['text_start']:node['text_end']]:
                ancestor=source
                while ancestor!=node['source_node'] and self.dom[ancestor]['tag'] not in ('p','li','tr','summary','legend','h1','h2','h3','h4','h5','h6'):
                    ancestor=self.dom[ancestor]['parent']
                if current is not None and current!=ancestor:
                    text=' '.join(' '.join(buffer).split())
                    if text:parts.append(text)
                    buffer=[]
                current=ancestor;buffer.append(data)
            text=' '.join(' '.join(buffer).split())
            if text:parts.append(text)
            return ' | '.join(parts)
        def safe_data(key,value,identifier):
            if key == 'data-vfact-read':return value == ''
            if key in ('data-toggle','data-bs-toggle'):return value=='collapse'
            if key in ('data-target','data-bs-target'):return value=='#'+identifier
            return key in ('data-disclosure','data-collapse','data-accordion') and value in ('','true','collapse','accordion')
        def navigation_attrs(node):
            from urllib.parse import urlsplit
            a=node['attrs']
            if node['tag']!='a':return a
            if a.get('onclick','').strip()!='window.open(this.href); return false;':
                return a
            if 'data-id' in a and not re.fullmatch(r'[0-9]{1,20}',a['data-id']):
                return a
            href=a.get('href','')
            if not href or '\\' in href or any(ord(c)<32 or ord(c)==127 for c in href):
                return a
            try:
                u=urlsplit(href)
                safe=(
                    u.scheme=='https' and bool(u.hostname)
                    and not u.username and not u.password
                    and not any(c.isspace() for c in href)
                    or u.scheme=='tel'
                    and bool(re.fullmatch(r'\+?[0-9][0-9 ()-]{3,31}',u.path))
                    and not u.query and not u.fragment
                    or u.scheme=='mailto'
                    and bool(re.fullmatch(r'[^@\s?#]+@[^@\s?#]+',u.path))
                    and not u.query and not u.fragment
                )
            except ValueError:return a
            if not safe:return a
            return {k:v for k,v in a.items() if k not in ('onclick','data-id')}
        def fail(event,reason):event['reason']=reason
        for button in buttons:
            a=button['attrs'];number=button['source_node'];ids=a['aria-controls'].split()
            event=dict(control_node=number,status='refused');diagnostics.append(event)
            if not button['closed'] or button['ambiguous']:fail(event,'unclosed_or_ambiguous_button');continue
            if a.get('id') and self.id_counts.get(a['id'])!=1:fail(event,'ambiguous_button_identity');continue
            if not button['active'] or button['hidden'] or button['parent_blocked'] or button['forbidden'] or button['stateful']:
                fail(event,'excluded_button_ancestry');continue
            if a.get('type')!='button' or a.get('aria-expanded') not in ('true','false') or len(ids)!=1:
                fail(event,'not_single_static_disclosure');continue
            identifier=ids[0];target_id=self.id_nodes.get(identifier,{}).get('source_node');panel=self.dom.get(target_id)
            event['panel_node']=target_id
            if self.id_counts.get(identifier)!=1 or targets.get(identifier)!=1 or panel is None:
                fail(event,'missing_or_ambiguous_panel');continue
            if not panel['closed'] or panel['ambiguous']:fail(event,'unclosed_or_ambiguous_panel');continue
            event.update(panel_own_hidden=panel['hidden'],panel_parent_blocked=panel['parent_blocked'],
                panel_excluded=panel['forbidden'])
            if panel['tag'] not in ('div','section') or panel['parent_blocked'] or panel['forbidden'] or panel['stateful']:
                fail(event,'excluded_panel_ancestry');continue
            if button['owner']!=panel['owner']:fail(event,'cross_owner_relation');continue
            root=button;wrappers=[]
            parent=self.dom.get(button['parent'])
            while parent and parent['source_node']!=panel['parent'] and len(wrappers)<4:
                if (parent['tag'] not in ('div','h1','h2','h3','h4','h5','h6')
                        or parent['children']!=[root['source_node']] or parent['text']):break
                wrappers.append(parent);root=parent;parent=self.dom.get(parent['parent'])
            if not parent or parent['tag']!='div' or parent['source_node']!=panel['parent'] or not parent['closed']:
                fail(event,'not_closed_sibling_group');continue
            siblings=parent['children'];position=siblings.index(root['source_node'])
            if position+1>=len(siblings) or siblings[position+1]!=target_id or button['end']>=target_id:
                fail(event,'panel_not_next_sibling');continue
            allowed={'id','type','class','style','role','title','aria-label','aria-description','aria-controls','aria-expanded','tabindex'}
            if a.get('role','') not in ('','button') or any(key not in allowed and not safe_data(key,value,identifier) for key,value in a.items()):
                fail(event,'unknown_button_semantics');continue
            if self.UNSUPPORTED_STYLE.search(a.get('style','')):
                fail(event,'unsupported_button_note');continue
            descendants=[n for n in self.dom.values() if number<n['source_node']<=button['end']]
            if any(n['tag'] not in ('span','i','b','strong','em','small','br') or n['ambiguous']
                    or set(n['attrs'])-{'id','class','style','role','aria-hidden','title','aria-label','aria-description'}
                    or n['attrs'].get('role','') not in ('','none','presentation','img')
                    or self.UNSUPPORTED_STYLE.search(n['attrs'].get('style','')) for n in descendants):
                fail(event,'unsupported_button_children');continue
            caption=' '.join(text_in(button).split())
            if (not caption or len(caption)>200 or not public_unit(caption)
                    or re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',caption)):
                fail(event,'unreviewable_button_label');continue
            labels=[value for n in (button,*descendants) for key,value in n['attrs'].items()
                if key in self.TEXT_ANNOTATIONS and value.strip()]
            if any(normal(value)!=normal(caption) for value in labels):fail(event,'unrepresented_button_annotation');continue
            if any(not self.inert_layout_container(wrapper,caption) for wrapper in wrappers):
                fail(event,'unresolved_heading_wrapper');continue
            full=caption+' | '+panel_text(panel)
            event['source_screen_passed']=not (len(full)>900 or not public_unit(full) or re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',full))
            if len(full)>900 or (not event['source_screen_passed'] and not panel['hidden']):
                fail(event,'unreviewable_complete_panel');continue
            subtree=[n for n in self.dom.values() if target_id<=n['source_node']<=panel['end']]
            unsafe=None
            for node in subtree:
                attrs=navigation_attrs(node);tag=node['tag']
                checked=dict(node,attrs=attrs)
                if not self.static_text_markup(checked):unsafe='non_inert_panel_markup';break
                if tag in self.SKIP|{'form','input','textarea','select','option','label','datalist','output','button','sup'} or node['forbidden']:
                    unsafe='interactive_or_omitted_panel_content';break
                if node is not panel and node['hidden'] and (text_in(node).strip() or any(attrs.get(key) for key in self.TEXT_ANNOTATIONS)):
                    unsafe='unrelated_hidden_panel_content';break
                if any(key.startswith('on') or key.startswith('data-') or key in ('form','formaction') for key in attrs):
                    unsafe='dynamic_panel_content';break
                for key,value in attrs.items():
                    if key in self.TEXT_REFERENCES and not value.strip():continue
                    if key in self.TEXT_ANNOTATIONS and value.strip():
                        if key not in self.structural_metadata(tag,attrs) and normal(value)!=normal(text_in(node)):unsafe='unrepresented_panel_annotation'
                    elif key in self.TEXT_REFERENCES and value.strip():
                        binding=node is panel and key=='aria-labelledby' and a.get('id') and value==a['id']
                        if not binding:unsafe='unresolved_panel_reference'
                    elif key.startswith('aria-'):
                        valid=key in self.structural_metadata(tag,attrs) or key=='aria-hidden' and node is panel and value=='true'
                        if not valid:unsafe='unknown_panel_aria'
                if unsafe:break
            if unsafe:fail(event,unsafe);continue
            proposed[number]=dict(panel=target_id,group=parent['source_node'],root=root['source_node'],label=caption,
                button_id=a.get('id',''),event=event)
        # A dedicated group may contain several pairs. Unrelated human text,
        # fields or unmatched controls outside those pairs cannot disappear.
        def inert_group_node(node):
            attrs = node['attrs']
            if node['tag']=='div' and 'data-id' in attrs:
                token=attrs['data-id']
                if (not isinstance(token,str)
                        or not re.fullmatch(r'[A-Za-z0-9_.:-]{0,80}',token)
                        or '..' in token
                        or ':' in token):
                    return False
                node=dict(node,attrs={
                    key:value for key,value in attrs.items()
                    if key!='data-id'
                })
            return self.inert_layout_container(node)
        for group in {p['group'] for p in proposed.values()}:
            members=[(number,p) for number,p in proposed.items() if p['group']==group]
            spans=[(p['root'],self.dom[p['root']]['end']) for _,p in members]+[(p['panel'],self.dom[p['panel']]['end']) for _,p in members]
            covered=lambda n:any(start<=n<=end for start,end in spans)
            node=self.dom[group]
            # Empty sibling wrappers can carry conditions too. Every uncovered
            # node must be inert; absence of visible text grants nothing.
            unsafe_attributes=any(group<=n['source_node']<=node['end'] and not covered(n['source_node'])
                and not inert_group_node(n) for n in self.dom.values())
            extra_text=any(group<=n<=node['end'] and not covered(n) and data.strip() for n,data in self.dom_text)
            extra_controls=any(group<n['source_node']<=node['end'] and not covered(n['source_node'])
                and n['tag'] not in ('div',) for n in self.dom.values())
            if node['ambiguous'] or unsafe_attributes or extra_text or extra_controls:
                for number,p in members:fail(p['event'],'unresolved_group_semantics' if unsafe_attributes else 'unrelated_group_content');proposed.pop(number)
        self.disclosure_diagnostics=diagnostics
        for p in proposed.values():
            event=p['event']
            event['structure_candidate']=True
            if event['source_screen_passed']:
                event.update(status='accepted',reason='complete_static_disclosure')
            else:
                event.update(status='refused',reason='complete_panel_content_refused')
        return dict(buttons=frozenset(proposed),panels={p['panel']:dict(label=p['label'],button_id=p['button_id'],control_node=number)
            for number,p in proposed.items()
            if p['event']['source_screen_passed']}) if any(
                p['event']['source_screen_passed'] for p in proposed.values()) else {}

    def disclosure_units(self):
        """One complete bounded pane, never a procedure stripped of conditions."""
        units={};components={}
        for panel in self.disclosure_ranges:
            indices=tuple(i for i in range(panel['start'],panel['end'])
                if self.blocks[i] or self.block_kinds[i].startswith('barrier:'))
            leaves=[i for i in indices if self.block_kinds[i] in ('p','li','tr','block')]
            if not leaves:continue
            anchor=leaves[-1]
            text=' | '.join(self.blocks[i] if not self.block_kinds[i].startswith('barrier:') else ' * ' for i in indices)
            units[anchor]=dict(text=text,indices=indices,owner=panel['owner'],source_node=panel['source_node'])
            components.update((i,anchor) for i in indices if i!=anchor)
        return units,components

    def handle_starttag(self,tag,attrs):
        self.nodes+=1
        if self.nodes>20000 or len(self.stack)>=64:raise ResearchError('research_source_limit')
        ambiguous=len(attrs)!=len({key for key,_ in attrs})
        attrs={key:value if value is not None else '' for key,value in attrs}
        if self.public_layout:
            # Apply the same undefined-IDREF semantics to metadata, footnote,
            # directory and control gates. Preserve the original ambiguity flag.
            for key in self.TEXT_REFERENCES:
                if key in attrs and not attrs[key].strip():attrs[key]=''
            if attrs.get('id'):
                self.id_counts[attrs['id']]=self.id_counts.get(attrs['id'],0)+1
                self.id_nodes[attrs['id']]=dict(source_node=self.nodes,
                    tag=tag if tag in self.DIAGNOSTIC_TAGS or re.fullmatch(r'h[1-6]',tag) else 'other')
            self._search_ui_child(tag,attrs);self._control_child(tag,attrs)
            if ambiguous:
                for state in self.layout_search_forms.values():state['valid']=False
                for label in self.control_labels.values():label['structure']=False
        role=(attrs.get('role') or '').strip().casefold()
        role_tokens=tuple(role.split())
        native_button_role=role_tokens==('button',) and (tag=='button' or tag=='input' and attrs.get('type') in ('button','submit','reset'))
        opaque_role=bool(role_tokens and not native_button_role
            and any(token in self.FIELD_ROLES or token not in self.READ_ONLY_ROLES for token in role_tokens))
        own_stateful=bool(self.public_layout and ('contenteditable' in attrs and attrs['contenteditable'].casefold()!='false'
            or opaque_role))
        if own_stateful and not (tag=='input' and len(role_tokens)<=1 and role in ('','searchbox','textbox')):
            for state in self.layout_search_forms.values():state['valid']=False
            for label in self.control_labels.values():label['structure']=False
        parent_blocked=any(item[1] for item in self.stack)
        own_hidden='hidden' in attrs or attrs.get('aria-hidden')=='true'
        disclosure_panel=self.nodes in self.disclosures.get('panels',{})
        disclosure_control=self.nodes in self.disclosures.get('buttons',())
        blocked=parent_blocked or tag in self.SKIP or own_hidden and not disclosure_panel
        blocked=blocked or bool(CONTACT.search(attrs.get('class','')+' '+attrs.get('id','')))
        active=self.active()
        if self.collect_dom:
            parent=self.dom_positions.get(len(self.stack)-1)
            self.dom[self.nodes]=dict(source_node=self.nodes,tag=tag,attrs=attrs,parent=parent,children=[],text=False,
                end=self.nodes,closed=tag in self.VOID,ambiguous=ambiguous,parent_blocked=parent_blocked,
                text_start=len(self.dom_text),text_end=len(self.dom_text),
                owner=self.owner_path(),active=active,hidden=own_hidden,
                stateful=own_stateful or bool(parent is not None and self.dom[parent]['stateful']),
                forbidden=bool(tag in self.SKIP or CONTACT.search(attrs.get('class','')+' '+attrs.get('id',''))
                    or tag=='nav' or role in self.UI_ROLES or tag=='header' and not active))
            if parent is not None:self.dom[parent]['children'].append(self.nodes)
        control=tag in ('input','textarea','select','option','datalist','output','button','label') or own_stateful
        if self.public_layout:
            blocked=blocked or tag=='nav' or role in self.UI_ROLES or tag=='header' and not active
            owner=self.owner_path();parent_blocked=any(item[1] for item in self.stack)
            ui_ancestor=bool(self.ui_positions)
            metadata_known=not ambiguous and all(self.ui_positions.values())
            if ui_ancestor and not self.layout_search_forms and tag in ('p','label','legend','summary'):
                # A text/field label outside the closed search form has not
                # been shown to be navigation rather than a service condition.
                for position in self.ui_positions:self.ui_positions[position]=False
                metadata_known=False
            # A role nominates a layout widget, not a permission to omit
            # unknown service conditions. Validate its whole closed form.
            layout_candidate=(tag=='form' and active and not owner and role in self.UI_ROLES
                and not ui_ancestor and not parent_blocked and not self.layout_search_forms)
            layout_ui=False
            tainted=False;blocked_before_control=bool(blocked)
            print_syntax=active and not self.layout_search_forms and metadata_known and self._print_control_syntax(tag,attrs)
            print_labels=[attrs[key] for key in ('aria-label','aria-description','title') if attrs.get(key)]
            if tag=='input' and attrs.get('value'):print_labels.append(attrs['value'])
            passive_input=bool(tag=='input' and print_syntax and self._control_action(print_labels)=='print')
            defer_print=False
            # A form enclosing a content root is a page wrapper. A new form
            # inside already-active content is an interactive UI, never prose.
            if tag=='form' and active:
                if layout_candidate:
                    self.layout_search_forms[len(self.stack)]=dict(owner=owner,valid=metadata_known and attrs.get('method','get').casefold()=='get',
                        queries=0,chars=0,text=[],event=None)
                    self._search_ui_attributes(self.layout_search_forms[len(self.stack)],attrs)
                elif (not parent_blocked or ui_ancestor) and not self.layout_search_forms:
                    self.form_control_owners.add(owner);tainted=True
                blocked=True
            if control:
                if active and (not parent_blocked or ui_ancestor) and not self.layout_search_forms and not (tag=='input' and attrs.get('type','').casefold()=='hidden'):
                    if disclosure_control:pass  # Closed whole-widget proof, not a general button exception.
                    elif tag=='button' and print_syntax:defer_print=True
                    elif not passive_input:self.form_control_owners.add(owner);tainted=True
                blocked=True  # No values, labels, selected options or user text.
            event=None
            if (control or tag=='form') and len(self.control_diagnostics)<64:
                input_type=(attrs.get('type') or '').casefold()
                self.control_diagnostics.append(dict(tag=tag if tag in self.DIAGNOSTIC_TAGS or re.fullmatch(r'h[1-6]',tag) else 'other',active=active,owner=list(owner),tainted=tainted,
                    source_node=self.nodes,duplicate_attributes=ambiguous,
                    expanded_state=attrs.get('aria-expanded') if attrs.get('aria-expanded') in ('true','false') else 'other' if 'aria-expanded' in attrs else 'absent',
                    controls_reference=bool(attrs.get('aria-controls')),labelledby_reference=bool(attrs.get('aria-labelledby')),
                    inside_heading=next((t for t,_ in reversed(self.stack) if re.fullmatch(r'h[1-6]',t)),None),
                    event_handler_present=any(key.startswith('on') for key in attrs),
                    static_disclosure=disclosure_control,
                    role=role if role in self.UI_ROLES else 'other' if role else 'none',layout_ui=layout_ui,
                    input_type=input_type if input_type in ('hidden','text','search','checkbox','radio','button','submit','reset','password','email','number') else 'other' if input_type else 'none',
                    parent_blocked=parent_blocked,blocked_before_control=blocked_before_control,
                    typed_parent=any(t in ('p','li','tr','h1','h2','h3','h4','h5','h6') for t,_ in self.stack),
                    ancestors=[t if t in self.DIAGNOSTIC_TAGS else 'other' for t,_ in self.stack[-8:]]))
                event=self.control_diagnostics[-1]
                if tag in ('button','input'):
                    # Recognize only closed generic UI phrases. Unknown labels,
                    # JavaScript and user field values never leave this parser.
                    labels=[attrs[k] for k in ('aria-label','aria-description','title') if attrs.get(k)]
                    if tag=='input' and input_type in ('button','submit') and attrs.get('value'):labels.append(attrs['value'])
                    event.update(ui_action=self._control_action(labels),associated_description=bool(attrs.get('aria-describedby') or attrs.get('aria-labelledby')),
                        pure_print_handler=bool(re.fullmatch(r'\s*(?:window\.)?print\(\)\s*;?\s*(?:return\s+false\s*;?)?\s*',attrs.get('onclick') or '',re.I)))
                    event['nonqualifying_print']=passive_input
                if layout_candidate:self.layout_search_forms[len(self.stack)]['event']=self.control_diagnostics[-1]
            if tag=='button' and (event is not None or defer_print):
                if event is not None:event['label_complete']=False
                self.control_labels[len(self.stack)]=dict(event=event,labels=print_labels,parts=[],chars=0,overflow=False,
                    deferred=defer_print,owner=owner,structure=True)
            if tag not in self.VOID and (ui_ancestor or tag=='nav' or role in self.UI_ROLES):
                self.ui_positions[len(self.stack)]=self._ui_metadata_known(attrs)
            if tag=='form' and not active and not blocked:self.wrapper_forms[len(self.stack)]=False
            if event is not None:
                self.control_references[self.nodes]=dict(controls=tuple(attrs.get('aria-controls','').split()),id=attrs.get('id'))
                event['unknown_attribute_count']=len(set(attrs)-self.PRINT_ATTRIBUTES-self.DIAGNOSTIC_ARIA-
                    {'placeholder','aria-expanded','aria-controls','aria-labelledby','aria-describedby','aria-hidden'})
            if re.fullmatch(r'h[1-6]',tag):
                self.heading_diagnostics['seen']+=1
                if not active:self.heading_diagnostics['inactive']+=1
                if blocked:self.heading_diagnostics['blocked']+=1
            if (tag in ('h1','h2','h3','h4','h5','h6','p','li') or role=='heading'
                    or 'articlebody' in (attrs.get('itemprop') or '').casefold().split()) and len(self.structure_nodes)<48:
                safe_tags=self.DIAGNOSTIC_TAGS
                self.structure_nodes.append(dict(tag=tag if tag in safe_tags or re.fullmatch(r'h[1-6]',tag) else 'other',
                    active=active,blocked=bool(blocked),role_heading=role=='heading',
                    inside_form=any(t=='form' for t,_ in self.stack),inside_nav=any(t=='nav' for t,_ in self.stack),
                    wrapper_form_allowed=self.form_text_allowed(),
                    article_body='articlebody' in (attrs.get('itemprop') or '').casefold().split(),
                    ancestors=[t if t in safe_tags else 'other' for t,_ in self.stack[-8:]]))
        if tag=='meta' and not self.scope_positions:
            name=(attrs.get('property') or attrs.get('name','')).casefold();value=attrs.get('content','')
            if name in ('robots','hamarkommuneagent') and re.search(r'\b(?:noindex|none)\b',value,re.I):self.noindex=True
            if name in ('article:published_time','datepublished','dc.date.issued'):self.published=value
            if name in ('article:modified_time','datemodified','dc.date.modified'):self.updated=value
        if tag=='time' and attrs.get('datetime') and not self.scope_positions:
            if attrs.get('itemprop','').casefold()=='datepublished':self.published=attrs['datetime']
            if attrs.get('itemprop','').casefold()=='datemodified':self.updated=attrs['datetime']
        if tag=='input' and attrs.get('type','').casefold()=='password':self.noindex=True
        content_id=(attrs.get('id') or '').casefold().replace('_','-')
        content_classes=set((attrs.get('class') or '').casefold().split())
        marked_content=(content_id in ('main','main-content','content-main','maincontent','page-content',
            'pagecontent','content','article-content','articlecontent')
            or re.search(r'(?:^|-)main-?content$',content_id)
            or bool(content_classes & {'main-content','maincontent','page-content','pagecontent',
                'article-content','article__content'}))
        is_main=(tag=='main' or tag in ('div','section') and (role=='main' or self.public_layout
            and marked_content))
        if is_main and not blocked:
            if not self.public_layout or not self.main_positions:self.main_roots+=1
            self.main_positions.add(len(self.stack))
        article=tag=='article' or role=='article' and tag not in self.VOID
        if article and not blocked:
            self.article_roots+=1;self.article_positions.add(len(self.stack))
        if self.public_layout and (is_main or article) and not blocked:
            for position in self.wrapper_forms:self.wrapper_forms[position]=True
        # Native disclosure/form groups isolate their headings and conditions
        # just like articles/ARIA groups; sibling groups cannot lend a price year.
        typed_parent=any(t in ('p','li','tr','h1','h2','h3','h4','h5','h6') for t,_ in self.stack)
        if self.public_layout and active and typed_parent and (control or tag=='form') and not (defer_print or passive_input or disclosure_control):
            self.parts.append(' * ')  # Omitted interactive material cannot silently qualify this unit.
        semantic='details' if disclosure_panel else tag if tag in ('article','section','table','details','fieldset') else 'article' if article else 'section' if role in ('region','group','tabpanel') else 'div' if self.public_layout and tag=='div' and not typed_parent else None
        if semantic and not blocked and (active or article):
            self.flush()
            if self.public_layout and semantic in ('article','section','table','details','fieldset'):
                self.next_owner_id+=1;self.scope_owner_ids[len(self.stack)]=self.next_owner_id
                if article:self.article_owner_paths.append(self.owner_path())
            self.scope_event('scope_enter:'+semantic)
            self.scope_positions[len(self.stack)]=semantic
            self.directory_scopes[len(self.stack)]=(tuple(self.directory_headings),self.directory_inherited)
            self.directory_inherited=(*self.directory_inherited,*self.directory_headings);self.directory_headings=[]
            if disclosure_panel:
                self.disclosure_positions[len(self.stack)]=dict(start=len(self.blocks),owner=self.owner_path(),source_node=self.nodes)
                self.parts.append(self.disclosures['panels'][self.nodes]['label']);self.flush(kind='summary')
        if tag=='table':self.table_header=''
        if tag=='tr':self.row_header=False
        if tag=='th':self.row_header=True
        if active and tag in ('p','li','tr','h1','h2','h3','h4','h5','h6','summary','legend'):self.flush()
        if self.public_layout and active and tag=='div' and not typed_parent:self.flush()
        if active and re.fullmatch(r'h[1-6]',tag):
            level=int(tag[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]
            self.directory_heading_starts[level]=len(self.directory_links)
        if active and tag in ('p','li','tr','h1','h2','h3','h4','h5','h6','summary','legend') and not blocked:
            self.directory_rows[len(self.stack)]=dict(start=len(self.directory_links),text='',dirty=False)
        if role in ('navigation','banner','contentinfo','search') and tag not in self.VOID:
            self.directory_excluded.add(len(self.stack))
        if tag in ('td','th','br') and active and not blocked:self.parts.append(' | ')
        # Images are never fetched or executed. A nonempty accessible annotation
        # can carry a mandatory note; preserve a refusal cue, never its raw text.
        image_annotation=tag=='img' and (any((attrs.get(name) or '').strip()
            for name in ('alt','aria-label','title','aria-labelledby','aria-describedby'))
            or role in ('doc-noteref','doc-footnote','note'))
        if active and (image_annotation or not blocked and (tag=='sup' or attrs.get('aria-describedby')
                or re.search(r'(?:^|;)\s*vertical-align\s*:\s*super\b',attrs.get('style') or '',re.I)
                or tag=='a' and ((attrs.get('role') or '').casefold()=='doc-noteref'
                    or set((attrs.get('rel') or '').casefold().split()) & {'footnote','noteref'}
                    or re.search(r'^#(?:.*(?:foot|note|fn)|\d)',attrs.get('href') or '',re.I)))):
            self.parts.append(' * ')  # Explicit unsupported-note marker; this unit is refused, never cited.
        if active and blocked and re.fullmatch(r'h[1-6]',tag):
            level=int(tag[1]);self.directory_headings=[h for h in self.directory_headings if h[0]<level]+[(level,None)]
        if active and (blocked or image_annotation or tag=='sup' or attrs.get('aria-describedby')
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
        if self.public_layout and attrs.get('id'):
            self.id_nodes[attrs['id']].update(owner=list(self.owner_path()),blocked=bool(blocked),
                labelledby=tuple(attrs.get('aria-labelledby','').split()))
        if self.public_layout and not blocked:
            self._start_metadata(len(self.stack),tag,attrs,ambiguous=ambiguous)
            if tag in self.VOID and len(self.stack) in self.node_metadata:
                self._finish_metadata(len(self.stack),explicit_close=True)
        if tag not in self.VOID:
            if self.collect_dom:self.dom_positions[len(self.stack)]=self.nodes
            self.stack.append((tag,blocked))

    def handle_endtag(self,tag):
        if tag in ('p','li','tr','h1','h2','h3','h4','h5','h6','summary','legend'):self.flush()
        if self.public_layout and tag=='div' and not any(t in ('p','li','tr','h1','h2','h3','h4','h5','h6') for t,_ in self.stack):self.flush()
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
                for position in list(self.control_labels):
                    if position>=i:
                        self._finish_control(position,explicit_close=position==i and tag=='button')
                for position in list(self.layout_search_forms):
                    if position>=i:self._finish_search_ui(position,explicit_close=position==i and tag=='form')
                for position in sorted((p for p in self.directory_rows if p>=i),reverse=True):
                    row=self.directory_rows.pop(position);row_text=' '.join(row['text'].split())
                    for number in range(row['start'],len(self.directory_links)):
                        href,label,eligible,context=self.directory_links[number]
                        if row['dirty'] or row_text!=label:self.directory_links[number]=(href,label,False,context)
                for position in list(self.disclosure_positions):
                    if position>=i:
                        self.flush();panel=self.disclosure_positions.pop(position)
                        panel.update(end=len(self.blocks),closed=position==i);self.disclosure_ranges.append(panel)
                closing=[position for position in self.scope_positions if position>=i]
                if closing:
                    self.flush()
                    for position in sorted(closing,reverse=True):
                        self.scope_event('scope_exit:'+self.scope_positions.pop(position))
                        self.scope_owner_ids.pop(position,None)
                        local,self.directory_inherited=self.directory_scopes.pop(position);self.directory_headings=list(local)
                for position in list(self.node_metadata):
                    if position>=i:self._finish_metadata(position,explicit_close=position==i)
                for position in list(self.dom_positions):
                    if position>=i:
                        self.dom[self.dom_positions.pop(position)].update(end=self.nodes,closed=position==i,text_end=len(self.dom_text))
                del self.stack[i:];self.main_positions={position for position in self.main_positions if position<i}
                self.article_positions={position for position in self.article_positions if position<i};break
        self.ui_positions={position:known for position,known in self.ui_positions.items() if position<len(self.stack)}
        self.wrapper_forms={position:value for position,value in self.wrapper_forms.items() if position<len(self.stack)}
        self.directory_excluded={position for position in self.directory_excluded if position<len(self.stack)}

    def handle_data(self,data):
        if self.collect_dom and self.stack and not any(tag in ('script','style','noscript','svg','template') for tag,_ in self.stack):
            node=self.dom_positions.get(len(self.stack)-1)
            if node is not None:
                self.dom_text.append((node,data))
                if data.strip():self.dom[node]['text']=True
        for label in self.control_labels.values():
            if label['chars']+len(data)>200:label['overflow']=True
            else:label['parts'].append(data);label['chars']+=len(data)
        if not any(tag in ('script','style') for tag,_ in self.stack):
            for state in self.layout_search_forms.values():self._search_ui_text(state,data)
        if any(item[1] for item in self.stack):return
        if self.public_layout and any(tag=='title' for tag,_ in self.stack):
            if sum(map(len,self.title_parts))+len(data)<=240:self.title_parts.append(data)
            else:self.title_overflow=True
        for row in self.directory_rows.values():
            if len(row['text'])+len(data)>300:row['dirty']=True
            elif not row['dirty']:row['text']+=data
        if self.anchor is not None:self.anchor[1].append(data)
        if (self.active()
                and not any(item[0] in (('nav',) if self.public_layout else ('nav','header','form')) for item in self.stack)
                and (not self.public_layout or self.form_text_allowed())):
            if (any(item[0] in ('span','small') for item in self.stack)
                    and re.fullmatch(r'\s*\d{1,3}\s*',data)):
                self.parts.append(' * ')  # Unreviewed inline numeric annotation cannot become a price digit.
            self.parts.append(data)

    @classmethod
    def parse(cls,raw,*,public_layout=False):
        parsed=cls._parse(
            raw,public_layout=public_layout,disclosures=None
        )

        if public_layout and parsed.form_control_owners:
            from .discovery import capture_static_section_proofs
            parsed.independent_section_proofs=(
                capture_static_section_proofs(raw,cls)
            )

        return parsed


    @classmethod
    def _parse(cls,raw,*,public_layout,disclosures):
        if type(raw) is not bytes or len(raw)>512*1024:raise ResearchError('research_source_limit')
        parser=cls(public_layout=public_layout,disclosures=disclosures)
        try:parser.feed(raw.decode('utf-8-sig',errors='strict'));parser.close();parser.flush()
        except (UnicodeError,ValueError,RecursionError):raise ResearchError('research_source_invalid') from None
        for position in list(parser.layout_search_forms):parser._finish_search_ui(position)
        for position in list(parser.control_labels):parser._finish_control(position)
        for position in list(parser.node_metadata):parser._finish_metadata(position)
        parser.annotations.sort(key=lambda node:node['diagnostic']['source_node'])
        parser.metadata_diagnostics.sort(key=lambda node:node['source_node'])
        parser.finalise_control_diagnostics()
        if parser.scope_positions:raise ResearchError('research_source_invalid')
        if parser.noindex:raise ResearchError('research_source_invalid')
        if parser.main_roots>1 or not parser.main_roots and parser.article_roots>1:
            parser.blocks=[]  # Discovery may continue, but ambiguous bodies are never evidence.
            parser.content_root_refusal='ambiguous_content_roots'
        elif not parser.main_roots and not parser.article_roots:parser.content_root_refusal='no_content_root'
        if public_layout and disclosures is None and not parser.content_root_refusal:
            plan=parser.static_disclosure_plan();diagnostics=parser.disclosure_diagnostics
            parser.dom.clear();parser.dom_text.clear();parser.dom_positions.clear()
            if plan:
                # Same parser, source limits and admission/verification gates;
                # the first pass only proves closed static DOM relationships.
                candidate=cls._parse(raw,public_layout=True,disclosures=plan)
                # A proof is not committed until every complete pane survives
                # the canonical whole-unit privacy/annotation/condition gate.
                # Otherwise retain the original controllers' barriers.
                from .internet_research import public_unit
                LiveResearchService.reviewed_html_units(candidate,None,unit_screen=public_unit)
                admitted={d['disclosure_source_node'] for d in candidate.unit_decisions if d.get('complete_panel')
                    and (d['emitted'] or d.get('first_refusal')=='duplicate_units') and d.get('context_state')!='rejected'}
                if set(plan['panels'])<=admitted:
                    parser=candidate
                    for event in diagnostics:
                        if event.get('structure_candidate'):
                            event['structure_applied']=True
                else:
                    for event in diagnostics:
                        if event['status']=='accepted':event.update(status='refused',reason='complete_panel_failed_source_gate')
                parser.disclosure_diagnostics=diagnostics
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

    def get(self,url,session,*,robots=False,document_kind='html'):
        if document_kind not in ('html','sitemap') or robots and document_kind!='html':
            raise ResearchError('research_source_invalid')
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
                expected_types=('text/plain',) if robots else ('application/xml','text/xml') if document_kind=='sitemap' else ('text/html',)
                connection.request('GET',path,headers={'User-Agent':AGENT,'Accept':', '.join(expected_types),
                    'Accept-Encoding':'identity','Connection':'close','Cache-Control':'no-cache','Pragma':'no-cache'})
                response=connection.getresponse();headers=response.headers
                if (response.status!=200 or len(headers.get_all('Content-Type',[]))!=1
                        or headers.get_content_type() not in expected_types
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
                    raw_sha256=hashlib.sha256(raw).hexdigest(),status=200,role='robots' if robots else document_kind)
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
        self.active_municipalities=service.active_municipalities
        self.reviewed_only=service.reviewed_only
        if self.active_municipalities is not None and any(m.official_host in hosts and m.id not in self.active_municipalities
                for m in self.registry.entries.values()):raise ResearchError('research_municipality_inactive')
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
                    or self.service.active_municipalities!=self.active_municipalities
                    or self.service.reviewed_only!=self.reviewed_only
                    or self.registry.fingerprint()!=self.registry_hash
                    or any(not m.current() for m in self.registry.entries.values())):
                raise ResearchError('research_permission_revoked')
            self.owner.admit_tool('live_source_binding')

    def get(self,url,*,robots=False,document_kind='html'):
        self.check()
        try:
            options={'robots':robots}
            if document_kind!='html':options['document_kind']=document_kind
            raw,record,modified=self.service.transport.get(url,self,**options)
            self.check()
            if (type(raw) is not bytes or type(record) is not dict or record.get('url')!=url
                    or len(raw)>(65536 if robots else 512*1024) or self.received>1024*1024 or self.requests>8
                    or record.get('request_id')!=self.request_id or type(record.get('status')) is not int
                    or record['status']!=200 or record.get('role')!=('robots' if robots else document_kind)
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


def procedural_text(text):
    """Shared grammatical signal, never evidence of the correct service alone."""
    return bool(re.search(r'\b(?:søknad\w*|søk(?:e[rs]?|jer|je|jast)?|send(?:e[rs]?|t|ing|ast)?|'
        r'skjema(?:et|er|ene)?|fyll(?:e|er)?\s+ut|apply|applications?|submit(?:s|ted|ting)?|forms?)\b',text,re.I))


def procedural_reference(text):
    """Ordinary application syntax can refer to an established article topic.

    This only recognizes grammatical references, never a service, fact or
    approval. The caller must still reject different objects, headings,
    conditions and unsafe source text before using the article context.
    """
    if not procedural_text(text):return False
    noun=r'(?:søknad(?:en|er|ene)?|skjema(?:et|er|ene)?|applications?|forms?)'
    determiner=r'(?:(?:en|ei|et|eit|din|ditt|den|det|the|your|an?)\s+)?'
    action=r'(?:send(?:es|t|ast)?|lever(?:es|ast)?|fyll(?:es|ast)?\s+ut|submit(?:ted)?|sent|completed)'
    passive=determiner+noun+r'\s+(?:(?:kan|skal|må|bør|blir|vert|is|are|must\s+be|can\s+be)\s+)?'+action
    imperative=r'(?:send|lever|fyll\s+ut|submit|complete)\s+(?:inn\s+)?'+determiner+noun
    infinitive=(r'for\s+å\s+søk(?:e|je)\s+plass\s+(?:kan|skal|må|bør)\s+'
        +determiner+noun+r'\s+'+action+r'|to\s+apply\s*,\s*'+imperative)
    # This fallback is only for an implicit reference to the article topic.
    # Match the complete instruction, not a prefix followed by an unknown
    # purpose, second predicate or condition. Explicit service descriptions
    # continue through ordinary lexical/topic matching instead.
    # A recipient is an institutional role, not an arbitrary phrase. Otherwise
    # "to obtain a permit" could masquerade as the name of a receiving office.
    # Compounds stay open (e.g. any office/department), without a service list.
    institution=(r'(?:[^\W\d_][\w-]*)?(?:kontor(?:et)?|administrasjon(?:en)?|'
        r'avdeling(?:en|a)?|etat(?:en)?|kommune(?:n)?|enhet(?:en|a)?|'
        r'office|department|administration|authority|agency|council|municipality)')
    possessor=r'(?:'+institution+r"(?:s|['’]s)\s+)?"
    recipient=r'(?:\s+(?:til|to)\s+'+determiner+possessor+institution+r')?'
    method=(r'(?:\s+(?:gjennom|via|med|through|using)\s+'+determiner+
        r'(?:(?:digitalt?|digitale|elektronisk|elektroniske|online)\s+){0,2}'
        r'(?:skjema(?:et|er|ene)?|søknadsskjema(?:et)?|nettportal(?:en)?|portal(?:en)?|forms?))?')
    purpose=(r'(?:\s+for\s+(?:(?:dette|denne)\s+(?:tilbudet|tjenesten|ordningen)|'
        r'å\s+søk(?:e|je)\s+plass))?')
    return bool(re.fullmatch(r'\s*(?:'+passive+'|'+imperative+'|'+infinitive+r')'
        r'(?:\s+(?:digitalt|elektronisk|online))?'+purpose+recipient+method+r'\s*[.!]?\s*',text,re.I))


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
    if re.search(r'\b(?:hvordan|korleis)\s+søk(?:er|jer|je|e)?\b|\bhow\b.{0,40}\bapply\b',question,re.I):
        parts=text.split(' | ')
        from .question_router import procedural_evidence

        return (
            procedural_text(parts[-1])
            or any(
                procedural_text(part)
                and procedural_evidence(part)
                and not part.rstrip().endswith('?')
                for part in parts[:-1]
            )
        )
    return True



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
    def __init__(self,private,session,approvals,observations,municipality,municipal,*,question=None):
        self.live_session=session
        super().__init__(private,session.owner,private.revision,approvals,session.request_id,observations,
            session.authorized,municipality,municipal,question=question)
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
    def from_reviewed_policy(cls,path,*,enabled=False,transport=None,external_policy=None,reviewed_only=False):
        municipalities,approvals,details=load_research_policy(path,details=True)
        if municipalities is None or len(municipalities.entries)!=46:
            raise ValueError('Live municipal discovery requires the complete reviewed roster')
        return cls(municipalities,approvals=approvals,enabled=enabled,transport=transport,
                   authorities=details['public_authorities'],external_policy=external_policy,
                   supplementary_sites=details.get('supplementary_sites',()),active_municipalities=details.get('active_municipalities'),
                   reviewed_only=reviewed_only)

    def __init__(self,municipalities,*,approvals=(),enabled=False,transport=None,authorities=(),external_policy=None,
                 supplementary_sites=(),reviewed_fetcher=None,discoverer=None,active_municipalities=None,reviewed_only=False,
                 discovery_profile=None):
        super().__init__(approvals,municipalities=municipalities,active_municipalities=active_municipalities)
        self.live_enabled=enabled is True;self.transport=transport or LiveTransport()
        if type(reviewed_only) is not bool:raise ValueError('Explicit reviewed-only boundary required')
        self.reviewed_only=reviewed_only
        self.discovery_profile=discovery_profile  # No default grant, CLI flag or inferred domain permission.
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
            external_authorized=lambda a:self.external_policy is None or self.external_allowed(a),
            active_municipalities=self.active_municipalities)

    def configured(self):
        return bool(self.live_enabled and not self.revoked and self.municipalities is not None
                    and self.municipalities.entries and all(m.current() for m in self.municipalities.entries.values()))

    def external_allowed(self,approval):
        return bool(self.external_policy and self.external_policy(approval.url,approval.text_sha256))

    def prepare_guidance(self,question,*,provider,authorized):
        # The real reviewed catalog has no public guidance entries today. A
        # public domain record alone never supplies an excerpt or transfer right.
        if not any(a.current() and a.authority_tier==2 and a.national_guidance_reviewed for a in self.approvals.values()):
            raise ResearchError('research_no_sources')
        revision,registry,catalog=self.revision,self.municipalities,self.approvals
        fingerprint=registry.fingerprint();active=self.active_municipalities
        reviewed=self.reviewed_sources
        def permitted():
            return (authorized() and self.configured() and self.revision==revision
                and self.municipalities is registry and registry.fingerprint()==fingerprint
                and self.approvals is catalog and self.active_municipalities==active
                and self.reviewed_sources is reviewed
                and dict(reviewed.approvals)==dict(catalog))
        return reviewed.prepare(question,provider=provider,authorized=permitted,evidence_scope='national_guidance')

    def context_terms(self,question):
        validate_message(question)
        topic=service_topic(question)
        if topic:return [topic]
        from .question_router import canonical_question
        words=set(re.findall(r'\w+',canonical_question(question).casefold()))
        return list(dict.fromkeys(word for a in self.approvals.values() if a.current()
            for word in a.keywords if words.intersection(re.findall(r'\w+',canonical_question(word).casefold()))))[:16]

    @staticmethod
    def reviewed_html_units(parsed,entry,*,unit_screen=None,diagnostics=None,allow_independent_sections=False,statement_heading_screen=None):
        """Whole context-bearing review units, never automatic approval.

        A reviewer approves the exact joined unit AND the full input snapshot.
        Sibling articles/sections restore their parent context; screened labels
        and scope barriers cannot silently disappear from a condition.
        """
        def screened(text):
            if unit_screen is not None:return unit_screen(text)
            # This is a review-candidate screen, not the typed automatic HTML
            # allowlist. Only an exact separately reviewed input/unit may be
            # admitted by _fetch_reviewed_html. Unknown words confer no trust.
            if not text or len(text)>900 or CONTACT.search(_screening_text(text)):return False
            try:privacy_check(text);validate_message(text,reply=True)
            except ValueError:return False
            return True
        def reject(reason):
            if diagnostics is not None:diagnostics[reason]=diagnostics.get(reason,0)+1
            if decision is not None and 'first_refusal' not in decision:decision['first_refusal']=reason
        def passed(stage):
            if diagnostics is not None:diagnostics[stage+'_passed']=diagnostics.get(stage+'_passed',0)+1
        public_layout=getattr(parsed,'public_layout',False)
        parsed.unit_contexts=[];parsed.unit_scope_text=[];parsed.unit_decisions=[];decision=None
        if diagnostics is not None:diagnostics.update(parsed_events=len(parsed.blocks),candidate_units=0,emitted_units=0)
        if public_layout:
            for event in parsed.control_diagnostics:
                text=parsed.control_text.get(event['source_node'])
                if text is not None:event['label_public_screen']=screened(text)
            parsed.control_text.clear()
        def document_context(owner,components,component_indices):
            # Metadata is separate nomination context, never injected before
            # relevance. A sibling article/section cannot donate its H1.
            candidates=None;from_title=False
            for size in range(len(owner),-1,-1):
                if owner[:size] in parsed.topic_titles:
                    candidates={}
                    for label,index in parsed.topic_titles[owner[:size]]:candidates.setdefault(label,set()).add(index)
                    break
            sole_article=(parsed.article_roots==1 and len(parsed.article_owner_paths)==1
                and owner==parsed.article_owner_paths[0])
            # One unambiguous article can use its fetched document title for
            # nomination. Never donate it to a sibling or an unlabelled child
            # section/group, or use it to supply a price year/condition.
            if candidates is None and (parsed.next_owner_id==0 or sole_article) and not parsed.title_overflow:
                title=' '.join(''.join(parsed.title_parts).split())
                if title:candidates={title:set()};from_title=True
            if candidates is None:return None
            if len(candidates)!=1:return False
            value,donors=next(iter(candidates.items()))
            if not value or not screened(value):return False
            refusal=parsed.annotation_rejection((*components,value),component_indices|donors,document_title=from_title)
            if refusal is not None:
                if decision is not None:decision['document_annotation_rejection']=refusal
                reject('unrepresented_document_context');return False
            if re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',value):return False
            return None if re.search(r'\d',value) else value
        headings=[];inherited=();group=None;contexts=[];units=[];seen_units=set()
        disclosure_units,disclosure_components=parsed.disclosure_units() if public_layout else ({},{})
        for index,(block,kind) in enumerate(zip(parsed.blocks,parsed.block_kinds)):
            decision=None
            if index in disclosure_components:
                if kind in ('p','li','tr','block'):
                    parsed.unit_decisions.append(dict(block_index=index,kind=kind,owner=list(parsed.block_owners[index]),
                        emitted=False,disclosure_component_of=disclosure_components[index]))
                continue
            aggregate=disclosure_units.get(index)
            if aggregate is not None:block=aggregate['text'];kind='p'
            if kind.startswith('scope_enter:'):
                contexts.append((list(headings),inherited,group))
                inherited=(*inherited,*headings,*(((-1,*group),) if group else ()))
                headings=[];group=None;continue
            if kind.startswith('scope_exit:'):
                if not contexts:raise ResearchError('research_source_invalid')
                headings,inherited,group=contexts.pop();continue
            if kind.startswith('barrier:'):
                reject('context_barriers')
                lost=kind.split(':',1)[1]
                if lost in ('h1','h2','h3','h4','h5','h6'):
                    level=int(lost[1]);headings=[h for h in headings if h[0]<level]
                    headings.append((level,None,index))
                else:
                    # A lost non-heading condition has unknown extent. Keep a
                    # barrier throughout this scope, including under headings.
                    headings.append((0,None,index))
                group=None;continue
            if not block:continue
            if kind in ('summary','legend'):
                # Native group labels qualify this whole scope, including
                # under child headings. They cannot be silently discarded.
                headings.append((0,block if screened(block) else None,index));continue
            if kind in ('h1','h2','h3','h4','h5','h6'):
                level=int(kind[1]);headings=[h for h in headings if h[0]<level]
                headings.append((level,block if screened(block) else None,index))
                group=None

                if (
                    public_layout
                    and statement_heading_screen is not None
                    and statement_heading_screen(block)
                ):
                    kind='p'
                else:
                    continue
            if kind not in (('p','li','tr','block') if public_layout else ('p','li','tr')):continue
            decision=dict(block_index=index,kind=kind,owner=list(parsed.block_owners[index]),emitted=False)
            parsed.unit_decisions.append(decision)
            if diagnostics is not None:diagnostics['candidate_units']+=1
            if public_layout and not re.search(r'\w|[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]',block):
                reject('empty_units');continue
            if kind=='block':
                # Unknown layout text is useful for general guidance, but may
                # not create a new automatic price/table interpretation.
                if re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\b(?:kr\.?|NOK)\s*\d|\bgratis\b',block,re.I):
                    reject('unsupported_block_price');headings.append((0,None,index));continue
                if len(block.split())<3:
                    group=(block,index) if screened(block) else None
                    if group is None:headings.append((0,None,index))
                    reject('short_unit_rejections');continue
            if block.endswith(':'):
                group=(block,index) if screened(block) else None
                if group is None:headings.append((0,None,index))
                continue
            labels=[label for _,label,_ in (*inherited,*headings)]
            if any(label is None for label in labels):reject('context_barriers');continue
            passed('heading_context')
            components=tuple(dict.fromkeys(x for x in (*labels,group[0] if group else None,block) if x))
            unit=' | '.join(components)
            component_indices={index,*(i for _,label,i in (*inherited,*headings) if label)}
            if group:component_indices.add(group[1])
            validation_components=components
            if aggregate is not None:
                component_indices.update(aggregate['indices'])
                validation_components=(*components,*(parsed.blocks[i] for i in aggregate['indices']))
                decision.update(disclosure_source_node=aggregate['source_node'],complete_panel=True)
            annotation_refusal=parsed.annotation_rejection(validation_components,component_indices) if public_layout else None
            tainted_owners=[list(owner) for owner in sorted(parsed.form_control_owners)
                if parsed.block_owners[index][:len(owner)]==owner or aggregate is not None
                    and owner[:len(aggregate['owner'])]==aggregate['owner']] if public_layout else []
            unit_safe=screened(unit)
            decision.update(component_blocks=sorted(component_indices),annotation_rejection=annotation_refusal,
                form_control_owners=tainted_owners,public_screen=unit_safe,word_count=len(unit.split()),
                note_marker=bool(re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',unit)))
            if annotation_refusal is not None:
                reject('unrepresented_annotations');continue
            passed('annotations')
            if (
                tainted_owners
                and allow_independent_sections
                and unit_safe
                and annotation_refusal is None
                and not re.search(
                    r'\d|[*\u2020\u2021]|\b(?:pris|gebyr|gratis|rettighet|frist)\w*\b',
                    unit,re.I
                )
            ):
                from .discovery import independent_static_section

                if independent_static_section(
                    parsed,index,component_indices
                ):
                    decision['independent_static_section']=True
                    tainted_owners=[]

            if tainted_owners:
                # Omitted interactive text may qualify any fact, including an
                # application procedure without a price, date or rule keyword.
                # Its extent is unknown: refuse this owner and descendants,
                # while independent sibling scopes keep their own context.
                reject('form_control_conditions');continue
            passed('form_control')
            # Footnote conditions cannot be inferred or dropped from a unit.
            if re.search(r'[*†‡¹²³⁴⁵⁶⁷⁸⁹⁰]|\[\s*(?:\d{1,3}|[a-zA-Z])\s*\]',unit):reject('note_rejections');continue
            passed('notes')
            if len(unit)>900:reject('overlong_units')
            if not unit_safe:reject('public_screen_rejections')
            elif len(unit.split())<5:reject('too_short_units')
            if unit_safe and len(unit.split())>=5:
                passed('public_screen')
                context=document_context(parsed.block_owners[index],components,component_indices) if public_layout else None
                decision['context_state']='rejected' if context is False else 'present' if context else 'none'
                if public_layout and (unit,context) in seen_units:reject('duplicate_units');continue
                seen_units.add((unit,context))
                units.append(unit)
                parsed.unit_contexts.append(context)
                parsed.unit_scope_text.append(aggregate['text'] if aggregate is not None else None)
                decision.update(emitted=True,context_state='rejected' if context is False else 'present' if context else 'none')
                if diagnostics is not None:diagnostics['emitted_units']+=1
        return tuple(units)

    def _fetch_reviewed_html(self,approval,session,*,max_bytes):
        """One approved URL/snapshot, same pinned transport; raw bytes die here."""
        session.check();entry=self.municipalities.entries[approval.municipality_id]
        self.require_active(entry)
        if not approval.current():raise ResearchError('research_source_expired')
        session.site(entry.official_host)
        if hashlib.sha256(session.robots[entry.official_host]).hexdigest()!=approval.robots_sha256:
            session.diagnose('reviewed_robots_changed',approval.url)
            raise ResearchError('research_source_invalid')
        raw,record,modified=session.get(approval.url)
        try:
            if hashlib.sha256(raw).hexdigest()!=approval.input_sha256:
                session.diagnose('reviewed_input_changed',approval.url)
                raise ResearchError('research_source_invalid')
            parsed=ServiceHTML.parse(raw)
            if ((approval.content_tag=='main' and parsed.main_roots!=1)
                    or (approval.content_tag=='article' and (parsed.main_roots or parsed.article_roots!=1))):
                raise ResearchError('research_source_invalid')
            units=self.reviewed_html_units(parsed,entry)
            if any(units.count(p.text)!=1 for p in approval.excerpts):
                raise ResearchError('research_source_invalid')
            for p in approval.excerpts:
                if any(m.id!=entry.id and any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',p.text,re.I)
                        for name in (m.name,*m.aliases)) for m in self.municipalities.entries.values()):
                    # An official host does not make another town's paragraph
                    # evidence for this municipality. Mixed geography needs a
                    # separately scoped comparison, not a silent substitution.
                    raise ResearchError('research_source_invalid')
            body=approval.body
            if len(body)>max_bytes:raise ResearchError('research_source_limit')
            now=datetime.now(timezone.utc)
            result=dict(source_id=approval.source_id,url=approval.url,request_id=session.request_id,
                body=body,robots=session.robots[entry.official_host],status=200,content_type='text/html',
                retrieved_at=record['retrieved_at'],input_sha256=approval.input_sha256,input_bytes=len(raw),
                publisher_published_on=source_date(parsed.published,now),updated_at=source_date(parsed.updated,now),
                published_at=None,last_modified=modified,
                effective_periods=list(dict.fromkeys(p for e in approval.excerpts for p in effective_periods(e.text))),
                discovery_receipts=list(session.trace))
        finally:del raw
        session.check();session.diagnose('exact_reviewed_units_checked',approval.url,admitted_excerpts=len(approval.excerpts))
        return result

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
                    else:
                        # A discarded condition has unknown extent. A child
                        # heading cannot erase it; only this scope's exit can.
                        headings.append((0,None,frozenset()))
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
                if kind in ('summary','legend'):
                    label=block if safe_text(block,municipality,minimum=1) is not None else None
                    headings.append((0,label,frozenset(mentioned)))
                    if label is None:reject('native_group_label_screened')
                    for _,_,topics in (*inherited,*headings):
                        if topics:active_topic=next(iter(topics)) if len(topics)==1 else None
                    continue
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

    def _discover_review_candidates(self,session,entry,question):
        """Topic-neutral discovery only; unreviewed prose is NEVER evidence.

        Use the existing pinned transport/robots/bounds for official navigation.
        Keep only host/digests/counts in diagnostics; no labels, paths, raw HTML,
        personal records or arbitrary prose cross into the model or its index.
        An exact reviewed catalog excerpt is required to answer new content types.
        """
        from .question_router import canonical_question
        from .search import validate_query_privacy
        validate_query_privacy(question)
        text=self.municipalities.strip_names(canonical_question(question)).casefold()
        stop=set(('hva hvilke hvor hvordan når hvem what which where how when who i in om for fra '
            'og and the en et til er is are kan can du you jeg vi do does fortell tell me beskriv '
            'describe finner finne kommunen kommunens kommunal kommunale kommune innlandet koster').split())
        terms=tuple(dict.fromkeys(w for w in re.findall(r'[^\W\d_][\w-]{2,39}',text)
            if w not in stop))[:8]
        # Unknown user words may be names. Relevance matching stays local;
        # only reviewed, non-personal catalog vocabulary may leave as search
        # parameters. An empty catalog therefore permits navigation, not a
        # remote free-text query built from the user's unreviewed wording.
        reviewed_words={word.casefold() for a in self.approvals.values() if a.current()
            and a.municipality_id==entry.id for word in a.keywords}
        search_terms=tuple(word for word in terms if word in reviewed_words)
        host=entry.official_host;session.site(host)
        queue=[('https://'+host+'/',0)];seen=set()
        while queue and session.requests<6:
            url,depth=queue.pop(0)
            if url in seen:continue
            seen.add(url);raw,_,_=session.get(url)
            try:parsed=ServiceHTML.parse(raw)
            finally:del raw
            candidates=[]
            if depth<2:
                for href,label in parsed.links[:256]:
                    if not terms or not any(term in (label+' '+unquote(href)).casefold() for term in terms):continue
                    candidate=urljoin(url,href).split('#',1)[0]
                    try:safe_url(candidate,session.hosts)
                    except (ResearchError,ValueError):continue
                    if urlsplit(candidate).hostname!=host:continue
                    if re.search(r'\.(?:pdf|docx?|xlsx?)$',urlsplit(candidate).path,re.I):
                        session.diagnose('document_requires_reviewed_parser',candidate,admitted_excerpts=0)
                        continue
                    if re.search(r'\.(?:png|jpg|zip)$',urlsplit(candidate).path,re.I):continue
                    candidates.append(candidate)
                if depth==0 and search_terms:
                    for form in parsed.forms[:1]:
                        parts=urlsplit(urljoin(url,form['action']))
                        target=urlunsplit((parts.scheme,parts.netloc,parts.path or '/',urlencode({form['field']:' '.join(search_terms)[:80]}),''))
                        try:
                            safe_url(target,session.hosts,search=True)
                            robots_interval(session.robots[host],target,AGENT)
                        except (ResearchError,ValueError):continue
                        if parts.hostname==host:candidates.append(target)
            queue.extend((candidate,depth+1) for candidate in sorted(set(candidates))[:8] if candidate not in seen)
            session.diagnose('review_candidates_only',url,candidates=len(candidates),admitted_excerpts=0)
            del parsed
        session.diagnose('review_required',evaluated_pages=len(seen),pending_candidates=len(queue),admitted_excerpts=0)

    def prepare(self,question,*,provider,authorized,municipality_context=None,require_municipal=False):
        from .question_router import canonical_question,QuestionRouter
        question=canonical_question(question)
        validate_message(question);owner=current_run()
        if owner is None or not authorized() or not self.configured():raise ResearchError('research_unavailable')
        municipal=require_municipal or QuestionRouter(municipalities=self.municipalities).route(question).municipal
        # Apply coverage BEFORE reviewed catalog selection/HTTP, including a
        # known place in a general query. The complete identity roster remains.
        entry=self.municipalities.resolve(question,municipality_context) if municipal else None
        if not municipal:
            try:entry=self.municipalities.resolve(question,municipality_context)
            except ResearchError as error:
                if error.code!='research_municipality_unknown':raise
        self.require_active(entry)
        if self.approvals:
            revision,registry,catalog=self.revision,self.municipalities,self.approvals
            fingerprint=registry.fingerprint();active=self.active_municipalities;reviewed_only=self.reviewed_only
            selected=[]
            def still_authorized():
                return (authorized() and self.configured() and self.revision==revision and self.reviewed_only==reviewed_only
                    and self.active_municipalities==active
                    and (entry is None or active is None or entry.id in active)
                    and self.municipalities is registry and registry.fingerprint()==fingerprint and self.approvals is catalog
                    and (provider!='openai' or self.external_policy is None
                        or all(self.external_allowed(a) for a in selected)))
            try:
                reviewed=self.reviewed_sources
                if any(a.content_type=='text/html' for a in catalog.values()):
                    sessions=[]
                    def fetch(source_id,*,request_id,timeout_seconds,max_bytes):
                        approval=catalog[source_id]
                        if not still_authorized():raise ResearchError('research_permission_revoked')
                        if approval.content_type!='text/html':
                            return self.reviewed_sources.fetcher(source_id,request_id=request_id,
                                timeout_seconds=timeout_seconds,max_bytes=max_bytes)
                        if not sessions:
                            sessions.append(LiveSession(self,owner,request_id,datetime.now(timezone.utc),
                                still_authorized,[entry.official_host]))
                        if sessions[0].request_id!=request_id:raise ResearchError('research_source_invalid')
                        try:return self._fetch_reviewed_html(approval,sessions[0],max_bytes=max_bytes)
                        except ResearchError as error:
                            sessions[0].diagnose('reviewed_source_refused',approval.url,error_code=error.code)
                            error.source_diagnostics=tuple(sessions[0].trace+sessions[0].diagnostics)
                            raise
                    reviewed=ResearchService(catalog.values(),fetcher=fetch,municipalities=registry,
                        municipal_authorized=still_authorized,discoverer=self.reviewed_sources.discoverer,
                        external_authorized=self.reviewed_sources.external_authorized,
                        active_municipalities=active)
                    reviewed.observation_method='exact_reviewed_html_or_plain_text; fresh request transport'
                binding=reviewed.prepare(question,provider=provider,authorized=still_authorized,
                    municipality_context=municipality_context,require_municipal=municipal)
                selected.extend(binding.approvals)
                if any(a.content_type=='text/html' and any(
                        re.search(r'\d[\d .,]*\s*(?:kr\b|kroner\b|,-)|\bgratis\b',p.text,re.I)
                        and not all(fee_period_matches(period,question) for period in fee_periods(p.text))
                        for p in a.excerpts) for a in selected):
                    raise ResearchError('research_period_unverified')
                if any(a.content_type=='text/html' and any(not supports_question(p.text,question) for p in a.excerpts)
                        for a in selected):raise ResearchError('research_source_invalid')
                if provider=='openai' and self.external_policy is not None and not all(self.external_allowed(a) for a in selected):
                    raise ResearchError('research_external_not_approved')
                binding.assert_publishable()
                return binding
            except ResearchError as error:
                if error.code not in ('research_no_official_sources','research_no_sources'):raise
        if self.reviewed_only:
            # Exact-source probes never broaden a missing/expired approval to
            # navigation, typed admission or another URL/domain.
            error=ResearchError('research_no_official_sources' if municipal else 'research_no_sources')
            error.source_status=dict(discovery='not_attempted',admitted_sources=0,
                catalog_entries=len(self.approvals),reason='no_matching_reviewed_source')
            profile=self.discovery_profile
            if profile is not None and entry is not None:
                from .discovery import discover_candidates
                session=LiveSession(self,owner,uuid.uuid4().hex,datetime.now(timezone.utc),authorized,[entry.official_host])
                discover_candidates(session,question,entry,profile,
                    authorized=lambda:authorized() and self.discovery_profile is profile)
                error.source_diagnostics=tuple(session.trace+session.diagnostics)
                error.source_status.update(discovery='candidates_only',reason='candidate_content_requires_review')
            raise error
        entry=self.municipalities.resolve(question,municipality_context) if municipal else None
        if municipal and entry is None:raise ResearchError('research_municipality_required')
        topic=service_topic(question)
        if topic is None:
            if entry is None:raise ResearchError('research_no_sources')
            session=LiveSession(self,owner,uuid.uuid4().hex,datetime.now(timezone.utc),authorized,[entry.official_host])
            try:
                self._discover_review_candidates(session,entry,question)
                raise ResearchError('research_no_official_sources')
            except ResearchError as error:
                session.diagnose('request_refused',error_code=error.code)
                error.source_diagnostics=tuple(session.trace+session.diagnostics)
                raise
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
        private=ResearchService(approvals,municipalities=self.municipalities,active_municipalities=self.active_municipalities)
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
        return LiveBinding(private,session,tuple(approvals),observations,entry,municipal,question=question)

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
        if (school_overview(binding.question or '') or any(getattr(a,'directory_kind',None) for a in binding.approvals)
                or re.search(r'\b(?:alle|list\w*|oversikt\w*|hvilk\w*)\b',binding.question or '',re.I)):
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
        from .question_router import context_ellipse,canonical_question
        from .chat import _FOLLOWUP
        from .research import price_followup
        city_only=bool(self.municipalities.resolve(question) and re.fullmatch(
            r'\s*(?:og|hva med)\s*(?:kommune)?\s*[?!.]?\s*',self.municipalities.strip_names(canonical_question(question)),re.I))
        inherit=topic is None and bool(prior_terms) and bool(context_ellipse(question)
            or _FOLLOWUP.fullmatch(canonical_question(question)) or price_followup(question) or city_only)
        if inherit:topic=next((term for term in prior_terms if term in SERVICES),None)
        if category is not None and topic is not None and SERVICES[topic][1]!=category:raise ResearchError('research_no_sources')
        effective=question+' '+' '.join(prior_terms) if inherit else question
        binding=self.retrieve_for_query(effective,provider=workflow.provider,municipality_context=prior_municipality)
        if category is not None and any(d.category!=category for d in binding.index.documents.values()):
            raise ResearchError('research_no_sources')
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
            is_follow_up=inherit,
            message='Kildebasert utdrag. Kontroller at kildens periode passer spørsmålet.',
            coverage='Fersk, avgrenset kildekontroll. Ikke fullstendig kommunal dekning.',
            source_observation=binding.receipt(),source_receipts=list(binding.observations),
            source_checked_at=max(o['retrieved_at'] for o in binding.observations),
            source_cautions=['Nylig kildekontroll beviser ikke at opplysningene gjelder nå.'])
        self._directory_notice(value,binding)
        return BoundPortalResult(value,binding)
