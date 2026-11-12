"""Opt-in local general-chat quality evidence; no catalog, cloud, tools or paid calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from unittest.mock import patch

from hamar_agent import chat
from hamar_agent.ollama_provider import OllamaConfig, _local_post
from hamar_agent.provider_registry import configured_ollama_models
from hamar_agent.run_control import RunPolicy, active_workers, current_run
from hamar_agent.web import WebApplication


# Fixed non-personal evaluation prompts, never runtime answer substitutions.
CASES = (
    {'id':'sfo-short','message':'sfo?','expectation':'Norwegian municipal school-care meaning or useful clarification; no invented airport meaning.',
     'terms':['skolefritidsordning'],'wrong':['oslo','vestbanen']},
    {'id':'sfo-meaning','message':'Hva betyr SFO?','expectation':'Explain skolefritidsordning in municipal context; qualify ambiguity rather than invent.',
     'terms':['skolefritidsordning'],'wrong':['oslo','vestbanen']},
    {'id':'ppt-meaning','message':'Hva er PPT?','expectation':'Municipal pedagogisk-psykologisk tjeneste or useful contextual clarification.',
     'terms':['pedagogisk','psykologisk'],'wrong':[]},
    {'id':'sfo-application','message':'Hvordan søker jeg SFO-plass?','expectation':'Useful general guidance/referral; no invented local procedure, deadline, price or verified-source claim.',
     'terms':['sfo'],'wrong':['oslo lufthavn','vestbanen']},
    {'id':'short-price','message':'pris?','expectation':'Ask what service/item is meant; do not invent a price.', 'terms':[],'wrong':[]},
    {'id':'short-help','message':'hjelp?','expectation':'Welcoming Norwegian clarification, no invented user situation.', 'terms':[],'wrong':[]},
    {'id':'ambiguous-ms','message':'Hva betyr MS?','expectation':'Ask context or clearly qualify multiple possible meanings; do not assert one unique meaning.', 'terms':[],'wrong':[]},
    {'id':'ambiguous-pt','message':'Hva betyr PT?','expectation':'Ask context or clearly qualify possible meanings; no arbitrary definitive expansion.', 'terms':[],'wrong':[]},
    {'id':'nonmunicipal-science','message':'Forklar fotosyntese kort.','expectation':'Accurate brief Norwegian explanation of plants using light; do not force a municipal topic.',
     'terms':['lys'],'wrong':[]},
    {'id':'nonmunicipal-api','message':'Hva betyr API i programmering?','expectation':'Programming interface between software systems, not a municipal invention.',
     'terms':['program'],'wrong':[]},
    {'id':'airport-context','message':'SFO?','history':[
        {'role':'user','content':'Samtalen gjelder flyplasskoder i USA.'},
        {'role':'assistant','content':'Vi snakker om flyplasskoder i USA.'}],
     'expectation':'Use the supplied aviation context: San Francisco, not school care or Oslo.',
     'terms':['san francisco'],'wrong':['oslo','vestbanen']},
    {'id':'presentation-context','message':'PPT?','history':[
        {'role':'user','content':'Jeg lager en PowerPoint-presentasjon.'},
        {'role':'assistant','content':'Vi snakker om presentasjonsfiler.'}],
     'expectation':'Use the supplied presentation context: PowerPoint, not an unqualified municipal expansion.',
     'terms':['powerpoint'],'wrong':[]},
    {'id':'municipal-transfer-bpa','message':'Hva er BPA i kommunal sammenheng?',
     'expectation':'Brukerstyrt personlig assistanse, or acknowledge uncertainty and ask useful clarification.',
     'terms':['brukerstyrt','assistanse'],'wrong':[]},
)
ADDITIONAL_CASES = (
    {'id':'first-turn-presentation','message':'Hva betyr PPT i en PowerPoint-presentasjon?',
     'expectation':'Use explicit first-turn presentation context; not municipal terminology.', 'terms':['powerpoint'],'wrong':[]},
    {'id':'first-turn-airport','message':'Hva er SFO som flyplasskode i USA?',
     'expectation':'San Francisco with explicit first-turn aviation context, not Oslo or school care.', 'terms':['san francisco'],'wrong':['oslo','vestbanen']},
    {'id':'municipal-followup','message':'SFO?','history':[
        {'role':'user','content':'Jeg trenger informasjon om kommunens tilbud til barn etter skoletid.'},
        {'role':'assistant','content':'Vi snakker om tjenester for skolebarn.'}],
     'expectation':'Use the municipal school context; correct school-care meaning or useful non-invented clarification.', 'terms':['skolefritidsordning'],'wrong':['oslo','vestbanen']},
    {'id':'unseen-ambiguous-ab','message':'Hva betyr AB?',
     'expectation':'Ask useful clarification or qualify genuinely known meanings; no invented unique expansion.', 'terms':[],'wrong':[]},
)


def observations(case, text):
    """Lexical observations only; independent rubric review determines answer quality."""
    normalized = re.sub(r'\s+', ' ', text.casefold())
    return {'reference_terms_present':bool(case['terms']) and all(t in normalized for t in case['terms']),
            'known_wrong_terms':[t for t in case['wrong'] if t in normalized],
            'clarification_signal':'?' in text and bool(re.search(r'mener|hvilk|sammenheng|tenker|hva|kan du',normalized)),
            'limitation':'Term presence is not semantic correctness, usefulness or a factual-grounding measurement.'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):return None


def runtime(model):
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def get(path):
        with opener.open(Request('http://127.0.0.1:11434'+path,headers={'Accept':'application/json'}),timeout=2) as response:
            raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Local metadata exceeded bound')
        return json.loads(raw)
    version=get('/api/version').get('version')
    selected=next((m for m in get('/api/tags').get('models',[]) if m.get('name')==model),None)
    if selected is None or model not in configured_ollama_models():raise ValueError('Configured local model is not installed/allowed')
    return {'provider':'ollama','model':model,'digest':selected.get('digest'),'version':version,
            'temperature':0,'seed':0,'num_predict':512,'metadata_only':True}


def evaluate(output, *, model, system=None, cases=CASES):
    """Actual existing /api/chat route and local adapter, one bounded call per case."""
    transport_rows=[];run_rows=[]
    def factory(provider,selected):
        if (provider,selected)!=('ollama',model):raise AssertionError('Only the selected local model is allowed')
        def transport(url,headers,body,timeout,limit):
            if url!='http://127.0.0.1:11434/api/chat':raise AssertionError('Nonlocal endpoint forbidden')
            record={'attempts':1,'completed_http_responses':0,'run':current_run()};transport_rows.append(record)
            sent=json.loads(body)['messages'][0]['content']
            record['effective_instructions']=sent
            record['instructions_sha256']=hashlib.sha256(sent.encode('utf-8')).hexdigest()
            record['reference_present']=chat._REFERENCE_HEADER in sent
            raw=_local_post(url,headers,body,timeout,limit);record['completed_http_responses']=1
            response=json.loads(raw)
            record['usage']={k:response.get(k) for k in ('prompt_eval_count','eval_count')}
            return raw
        return chat.ChatOllamaClient(OllamaConfig(model=model,num_predict=512,timeout_seconds=60),transport=transport)
    backend=chat.ChatBackend(choices_factory=lambda provider:[{'provider':'ollama','model':model,'available':True}],
        client_factory=factory,paid_authorized=False,web_authorized=False,advanced_authorized=False)
    backend.policy=lambda:RunPolicy(output_tokens=512,input_bytes=12000,seconds=60,max_calls=1)
    app=WebApplication(chat_backend=backend);rows=[]
    generate=backend.generate
    def measured_generate(request,context):
        run_rows.append(current_run())
        return generate(request,context)
    with patch.object(backend,'instructions',(lambda context:system) if system is not None else backend.instructions), \
            patch.object(backend,'managed_reply',(lambda context:None) if system is not None else backend.managed_reply), \
            patch.object(backend,'generate',side_effect=measured_generate):
        for case in cases:
            token=app._new_page_token();state=app.sessions[token].chat
            history=tuple(dict(m) for m in case.get('history',()))
            state.messages=history;state.turns=len(history)//2
            state.display=tuple({'role':m['role'],'text':m['content']} for m in history)
            if history:state.selection=('ollama',model,False)
            headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000','Content-Type':'application/json','X-Hamar-Token':token}
            request={'message':case['message'],'provider':'ollama','model':model,'web_search':False,'revision':state.revision}
            before=len(transport_rows);before_runs=len(run_rows);start=time.perf_counter()
            response=app.dispatch('POST','/api/chat',headers,json.dumps(request).encode('utf-8'))
            elapsed=(time.perf_counter()-start)*1000;payload=json.loads(response.body)
            calls=transport_rows[before:];text=payload.get('reply',{}).get('text','')
            row={'case':case,'http_status':response.status,'text':text,'response':payload,'latency_ms':round(elapsed,3),
                 'response_origin':'ollama' if calls else 'local_source_safety_referral' if response.status==200 else 'error_without_model_call',
                 'transport_attempts':len(calls),'completed_http_responses':sum(c['completed_http_responses'] for c in calls),
                 'provider_reported_usage':[c.get('usage') for c in calls],
                 'effective_instructions':[{'text':c['effective_instructions'],'sha256':c['instructions_sha256'],
                                            'reference_present':c['reference_present']} for c in calls],
                 'instruction_plan':{'terms':backend.instruction_plan(json.dumps({'messages':[*history,{'role':'user','content':case['message']}]}))[1],
                                     'reason':backend.instruction_plan(json.dumps({'messages':[*history,{'role':'user','content':case['message']}]}))[2],
                                     'baseline_override':system is not None},
                 'budget_audits':[run.snapshot() for run in run_rows[before_runs:]],'observations':observations(case,text)}
            deadline=time.monotonic()+2
            while active_workers() and time.monotonic()<deadline:time.sleep(.005)
            row['remaining_workers']=active_workers()
            with (output/(case['id']+'.json')).open('x',encoding='utf-8') as stream:json.dump(row,stream,ensure_ascii=False,indent=2)
            rows.append(row);print(json.dumps({'case':case['id'],'http_status':response.status,'calls':len(calls),'latency_ms':row['latency_ms']},ensure_ascii=False),flush=True)
            if active_workers() or payload.get('error_code') in ('provider_unavailable','provider_timeout','run_deadline_exceeded'):
                break  # Abandonment is not remote cancellation; do not add more work.
    return rows


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-local-llm',action='store_true')
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--model',default='llama3.2:3b')
    parser.add_argument('--suite',choices=('primary','additional'),default='primary')
    parser.add_argument('--prompt-file',type=Path,help='Project/output JSON with system string; omitted uses current production instructions')
    parser.add_argument('--output',type=Path,required=True,help='New exclusive directory under project/output')
    args=parser.parse_args(argv)
    if not args.enable_local_llm and not args.check_only:parser.error('Explicit --enable-local-llm required')
    root=Path.cwd().resolve();output=args.output.resolve()
    if not output.is_relative_to(root/'output'):parser.error('Evidence must stay under project/output')
    system=None;cases=CASES if args.suite=='primary' else ADDITIONAL_CASES
    if args.prompt_file:
        path=args.prompt_file.resolve()
        if not path.is_relative_to(root/'output'):parser.error('Prompt fixture must stay under project/output')
        system=json.loads(path.read_text(encoding='utf-8'))['system']
        if not isinstance(system,str) or not 1<=len(system.encode('utf-8'))<=4000:parser.error('Invalid prompt fixture')
    output.mkdir(parents=True,exist_ok=False)
    original=socket.socket.connect
    def local_only(sock,address):
        if address[:2]!=('127.0.0.1',11434):raise AssertionError('External/paid network forbidden')
        return original(sock,address)
    with patch.object(socket.socket,'connect',local_only):
        try:metadata=runtime(args.model)
        except (OSError,ValueError,KeyError,TypeError):
            with (output/'summary.json').open('x',encoding='utf-8') as stream:json.dump({'available':False,'calls':0,'paid_calls':0,'web_searches':0},stream)
            print('Configured local Ollama unavailable; no inference performed.');return 3
        with (output/'runtime.json').open('x',encoding='utf-8') as stream:json.dump(metadata,stream,indent=2)
        if args.check_only:print(json.dumps(metadata,indent=2));return 0
        rows=evaluate(output,model=args.model,system=system,cases=cases)
    record={'method':'Existing general-chat API: actual local Ollama and explicitly labelled zero-call municipal source-safety referrals; fixed synthetic prompts/history',
        'runtime':metadata,'suite':args.suite,'case_count':len(cases),'executed':len(rows),'completed':sum(r['http_status']==200 for r in rows),
        'transport_attempts':sum(r['transport_attempts'] for r in rows),'paid_calls':0,'web_searches':0,
        'system':system if system is not None else chat.SYSTEM,
        'system_sha256':hashlib.sha256((system if system is not None else chat.SYSTEM).encode('utf-8')).hexdigest(),
        'context_system_sha256':hashlib.sha256((system if system is not None else chat.CONTEXT_SYSTEM).encode('utf-8')).hexdigest(),
        'dataset_sha256':hashlib.sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest(),
        'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('hamar_agent/chat.py','hamar_agent/web.py','harness/chat_quality_eval.py')},
        'quality_review':'Required: correctness/usefulness/clarification/unsupported claims, from actual raw texts. HTTP success and lexical terms alone are not answer quality.',
        'limits':'One run per prompt/seed/model, small curated dataset; no population accuracy or municipal factual verification claim'}
    with (output/'summary.json').open('x',encoding='utf-8') as stream:json.dump(record,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:record[k] for k in ('executed','completed','transport_attempts','paid_calls','web_searches')},indent=2),flush=True)
    return 0 if len(rows)==len(cases) and all(r['http_status']==200 for r in rows) else 1


if __name__=='__main__':raise SystemExit(main())
