"""Fictional research observations and mocked providers; no external access."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import eval.test_chat as chat_tests
from hamar_agent.research import (ResearchApproval, ResearchExcerpt, ResearchService, information_need,
                                  Municipality,MunicipalityRegistry,ResearchError)
from hamar_agent.run_control import active_workers

ROBOTS=b'User-agent: *\nAllow: /\n'
FACT=('fictional-service','test-value','2026','fictional-area','units')


def approval(source_id='public-a',*,text='Fiktivt testtema: testverdien er 250 enheter.',value='250',scope=FACT,external=True):
    return ResearchApproval(source_id,'https://www.ssb.no/synthetic-offline-'+source_id+'/',
        'Fiktiv testkilde',('testtema',),(ResearchExcerpt('p1',text,scope,value),),
        date.today().isoformat(),(date.today()+timedelta(days=7)).isoformat(),
        hashlib.sha256(ROBOTS).hexdigest(),True,True,external)


def service_fixture(approvals=None,*,mutate=None,municipalities=None):
    approvals=tuple(approvals or [approval()]);registry={a.source_id:a for a in approvals};calls=[]
    def fetch(source_id,**kwargs):
        a=registry[source_id];calls.append(dict(source_id=source_id,**kwargs))
        value=dict(source_id=source_id,url=a.url,request_id=kwargs['request_id'],body=a.body,robots=ROBOTS,
            retrieved_at=datetime.now(timezone.utc).isoformat(),status=200,content_type='text/plain')
        if mutate:mutate(value)
        return value
    return ResearchService(approvals,fetcher=fetch,municipalities=municipalities,municipal_authorized=lambda:municipalities is not None),calls


def regional_fixture(*,mutate=None,public=False,conflict=False):
    """Fictional reviewed-policy data; these domains are NOT verified or activated."""
    today=date.today().isoformat();expiry=(date.today()+timedelta(days=7)).isoformat()
    roster_hash=hashlib.sha256(b'FICTIONAL_OFFLINE_ROSTER_NOT_OFFICIAL_VERIFICATION').hexdigest()
    registry=MunicipalityRegistry(tuple(Municipality(key,name,host,today,expiry,'Synthetic test-only registry',roster_hash,aliases)
        for key,name,host,aliases in (
            ('hamar','Hamar','www.hamar.kommune.no',()),
            ('gjovik','Gjøvik','www.gjovik.kommune.no',('gjovik',)),
            ('lillehammer','Lillehammer','www.lillehammer.kommune.no',()))))
    values=[]
    for entry in registry.entries.values():
        text=f'Fiktivt testutdrag om vann i {entry.name}. Testgebyret er 250 kroner.'
        values.append(replace(approval(entry.id+'-vann',text=text,scope=(*FACT[:3],entry.id,FACT[4])),
            url='https://'+entry.official_host+'/synthetic-offline-water/',keywords=('vann',),
            authority_tier=1,municipality_id=entry.id))
    if public:
        text='Fiktivt generelt testutdrag om vann. Testverdien er '+('300' if conflict else '250')+' kroner.'
        values.append(replace(approval('fylke-vann',text=text,value='300' if conflict else '250',scope=(*FACT[:3],'gjovik',FACT[4])),
            url='https://innlandetfylke.no/synthetic-offline-water/',keywords=('vann',),authority_tier=2))
        values.append(replace(approval('thirdparty-vann',text='Fiktiv generell forklaring om vann.',scope=(),value=''),
            url='https://example.org/synthetic-offline-water/',keywords=('vann',),authority_tier=3))
    return service_fixture(values,mutate=mutate,municipalities=registry)


class RegionalResearchTests(unittest.TestCase):
    client=chat_tests.ChatTests.client
    drain=chat_tests.ChatTests.drain
    headers=chat_tests.ChatTests.headers
    send=chat_tests.ChatTests.send
    reset=chat_tests.ChatTests.reset
    state=chat_tests.ChatTests.state

    def setUp(self):
        chat_tests.ChatTests.setUp(self)
        self.service,self.observations=regional_fixture()
        self.backend.research_service=self.service;self.backend.web_authorized=True
        def response():
            if not self.observations:return chat_tests.sdk_response('Syntetisk svar uten kilder.')
            source=self.service.approvals[self.observations[-1]['source_id']]
            # The model's choice is scripted, not a genuine quality measurement.
            return chat_tests.sdk_response(json.dumps(dict(source_id=source.source_id,paragraph_id='p1',quote=source.excerpts[0].text)))
        self.response_factory=response

    def test_multiple_municipalities_share_both_provider_rag_paths(self):
        for provider,model in (('ollama','llama3.2:3b'),('openai','approved-model')):
            for name,key in (('Gjøvik','gjovik'),('Lillehammer','lillehammer'),('Hamar','hamar')):
                with self.subTest(provider=provider,name=name):
                    self.reset();self.calls.clear();self.observations.clear()
                    self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                    response=self.send('Hva koster vann i '+name+'?',provider=provider,model=model,web_search=True)
                    self.assertEqual(response.status,200,response.body)
                    reply=json.loads(response.body)['reply']
                    self.assertEqual(reply['municipality_id'],key);self.assertEqual(reply['authority'],'official_municipal')
                    self.assertIn(name,reply['text']);self.assertEqual([o['source_id'] for o in self.observations],[key+'-vann'])
                    self.assertEqual(len(self.calls),1)
                    call=self.calls[0]
                    sent=json.dumps(call.get('payload',call.get('kwargs')),ensure_ascii=False)
                    self.assertIn(self.service.approvals[key+'-vann'].excerpts[0].text,sent)
                    if provider=='openai':self.assertNotIn('tools',call['kwargs'])

    def test_official_sources_first_and_supplements_expand_only_for_comparison(self):
        self.service,self.observations=regional_fixture(public=True)
        self.backend.research_service=self.service
        plan,entry,municipal=self.service.plan('Hva koster vann i Gjøvik?')
        self.assertEqual([p.authority_tier for p in plan],[1]);self.assertEqual(entry.id,'gjovik');self.assertTrue(municipal)
        plan,entry,municipal=self.service.plan('Sammenlign vann i Gjøvik med andre kilder.')
        self.assertEqual([p.authority_tier for p in plan],[1,2,3])
        self.assertEqual(self.send('Hva koster vann i Gjøvik?',web_search=True).status,200)
        self.assertEqual([o['source_id'] for o in self.observations],['gjovik-vann'])

    def test_supplement_cannot_replace_missing_official_source(self):
        original,calls=regional_fixture(public=True)
        supplements=[a for a in original.approvals.values() if a.authority_tier>1]
        self.backend.research_service=ResearchService(supplements,fetcher=original.fetcher,municipalities=original.municipalities)
        response=self.send('Hva koster vann i Gjøvik?',web_search=True)
        self.assertNotEqual(response.status,200,response.body)
        self.assertEqual(self.calls,[]);self.assertEqual(calls,[]);self.assertEqual(self.state()['messages'],[])

    def test_ambiguous_unknown_and_missing_municipality_are_not_hamar(self):
        for question in ('Hva koster vann i Gjøvik og Hamar?','Hva koster vann i Ukjentby kommune?',
                         'Hva koster vann?'):
            with self.subTest(question=question):
                self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                response=self.send(question,web_search=True)
                self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])
                if response.status==200:self.assertFalse(json.loads(response.body)['reply']['ai_generated'])

    def test_conflicts_outages_and_modified_content_refuse_without_fallback(self):
        self.service,self.observations=regional_fixture(public=True,conflict=True)
        self.backend.research_service=self.service
        response=self.send('Sammenlign vann i Gjøvik med andre kilder.',web_search=True)
        self.assertEqual(response.status,422,response.body)
        self.assertEqual(json.loads(response.body)['error_code'],'research_source_conflict')
        self.assertEqual(self.calls,[]);self.assertEqual(self.state()['messages'],[])
        self.assertEqual([o['source_id'] for o in self.observations],['gjovik-vann','fylke-vann','thirdparty-vann'])
        self.service.fetcher=lambda *a,**k:(_ for _ in ()).throw(TimeoutError('synthetic outage'))
        self.observations.clear()
        response=self.send('Hva koster vann i Gjøvik?',web_search=True)
        self.assertNotEqual(response.status,200);self.assertEqual(self.calls,[])

    def test_substantive_followups_keep_city_and_new_city_overrides_it(self):
        for question,key in (('Hva koster vann i Gjøvik?','gjovik'),('Hva koster det?','gjovik'),
                             ('Og prisen?','gjovik'),('Hva koster vann i Lillehammer?','lillehammer')):
            response=self.send(question,web_search=True)
            self.assertEqual(response.status,200,response.body)
            self.assertEqual(json.loads(response.body)['reply']['municipality_id'],key)
        self.assertEqual(len({r['request_id'] for r in self.observations}),4)

    def test_roster_aliases_dates_and_exact_hosts_are_enforced(self):
        registry=self.service.municipalities
        self.assertEqual(registry.resolve('Vann i gjovik kommune?').id,'gjovik')
        self.assertEqual(registry.resolve('Vann i Ｇｊøｖｉｋ?').id,'gjovik')
        with self.assertRaises(ResearchError):registry.resolve('Vann i Hamarøy kommune?')
        with self.assertRaises(ResearchError):registry.resolve('Vann i Hamar og Gjøvik?')
        with self.assertRaises(ResearchError):registry.resolve('Vann i Bergen sammenlignet med Hamar?')
        with self.assertRaises(ResearchError):registry.resolve('Hva koster vann i oslo?',context='hamar')
        source=self.service.approvals['gjovik-vann']
        with self.assertRaises(ValueError):ResearchService([replace(source,url='https://www.gjovik.kommune.no.evil.invalid/path/')],municipalities=registry)
        expired=replace(registry.entries['gjovik'],reviewed_on='2020-01-01',expires_on='2020-01-02')
        with self.assertRaises(ResearchError):MunicipalityRegistry([expired]).resolve('Vann i Gjøvik?')

    def test_city_only_followup_overrides_prior_city_and_survives_next_ellipsis(self):
        for provider,model in (('ollama','llama3.2:3b'),('openai','approved-model')):
            with self.subTest(provider=provider):
                self.reset();self.calls.clear();self.observations.clear()
                self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                for question,city in (('Hva koster vann i Gjøvik?','gjovik'),('Og Hamar?','hamar'),('Hva koster det?','hamar')):
                    response=self.send(question,provider=provider,model=model,web_search=True)
                    self.assertEqual(response.status,200,response.body)
                    self.assertEqual(json.loads(response.body)['reply']['municipality_id'],city)
                self.assertEqual([o['source_id'] for o in self.observations],['gjovik-vann','hamar-vann','hamar-vann'])
                self.assertEqual(len({o['request_id'] for o in self.observations}),3)

    def test_ambiguous_name_requires_region_and_manifest_is_bounded(self):
        import tempfile
        from pathlib import Path
        from dataclasses import asdict
        entry=replace(self.service.municipalities.entries['gjovik'],id='valer',name='Våler',aliases=(),requires_region=True)
        registry=MunicipalityRegistry([entry])
        with self.assertRaises(ResearchError):registry.resolve('Vann i Våler?')
        with self.assertRaises(ResearchError):registry.resolve('Vann i Våler i Østfold?')
        self.assertEqual(registry.resolve('Vann i Våler i Innlandet?').id,'valer')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic-roster.json'
            path.write_text(json.dumps({'region':'Innlandet','municipalities':[asdict(entry)]}),encoding='utf-8')
            self.assertEqual(MunicipalityRegistry.from_reviewed_file(path).resolve('Våler i Innlandet').id,'valer')
            path.write_text('{"region":"Innlandet","region":"other","municipalities":[]}',encoding='utf-8')
            with self.assertRaises(ValueError):MunicipalityRegistry.from_reviewed_file(path)
            path.write_bytes(b'x'*65537)
            with self.assertRaises(ValueError):MunicipalityRegistry.from_reviewed_file(path)

    def test_regional_checker_rejects_wrong_error_and_earlier_phase_publication(self):
        from copy import deepcopy
        from harness.research_eval import regional_response_contract
        outage=[dict(http_status=422,payload=dict(error_code='research_unavailable'))]
        self.assertTrue(regional_response_contract('outage',outage,self.service.approvals))
        for status,code in ((403,'chat_paid_disabled'),(500,'research_unavailable'),(422,'research_no_sources')):
            wrong=[dict(http_status=status,payload=dict(error_code=code))]
            self.assertFalse(regional_response_contract('outage',wrong,self.service.approvals))
        source=self.service.approvals['gjovik-vann']
        good=dict(http_status=200,payload=dict(reply=dict(response_origin='model',ai_generated=True,
            research_verified=True,municipality_id='gjovik',text=source.excerpts[0].text,
            citations=[dict(url=source.url,title=source.title)])))
        phases=[deepcopy(good) for _ in range(3)]
        self.assertTrue(regional_response_contract('followup',phases,self.service.approvals))
        phases[0]['payload']['reply']['municipality_id']='hamar'
        self.assertFalse(regional_response_contract('followup',phases,self.service.approvals))
        phases[0]=deepcopy(good);phases[1]['payload']['reply']['response_origin']='application_guidance'
        self.assertFalse(regional_response_contract('followup',phases,self.service.approvals))

    def test_third_party_model_selection_is_rejected_even_when_quote_is_exact(self):
        self.service,self.observations=regional_fixture(public=True)
        self.backend.research_service=self.service
        # Fixture model deliberately selects the last (third-party) observed source.
        response=self.send('Sammenlign vann i Gjøvik med andre kilder.',web_search=True)
        self.assertEqual(response.status,422,response.body)
        self.assertEqual(json.loads(response.body)['error_code'],'research_claim_unsupported')
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.observations),3)
        self.assertEqual(self.state()['messages'],[])

    def test_registry_and_index_mutations_invalidate_request_publication(self):
        from hamar_agent.run_control import run_scope
        from types import MappingProxyType
        with run_scope():
            binding=self.service.retrieve_for_query('Hva koster vann i Gjøvik?')
            binding.index.documents.clear()
            with self.assertRaises(ResearchError):binding.assert_publishable()
        with run_scope():
            binding=self.service.prepare('Hva koster vann i Gjøvik?',provider='ollama',authorized=lambda:True)
            self.service.municipalities.entries=MappingProxyType({})
            with self.assertRaises(ResearchError):binding.assert_publishable()

    def test_other_municipality_never_uses_legacy_hamar_portal(self):
        from hamar_agent.portal import PortalService
        portal=PortalService()
        for question in ('vann i Gjøvik','parkering i Lillehammer'):
            with self.subTest(question=question),self.assertRaises(ResearchError):portal.search(question)
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])

    def test_no_search_municipal_question_is_guidance_not_an_invented_local_price(self):
        for question in ('Hva koster vann i Gjøvik?','Hva koster vann i Lillehammer?'):
            response=self.send(question,web_search=False)
            self.assertEqual(response.status,200,response.body)
            self.assertEqual(json.loads(response.body)['reply']['response_origin'],'application_guidance')
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])

    def test_common_municipal_backend_uses_regional_snapshot_and_keeps_quote_checks(self):
        from hamar_agent.real_sources import MunicipalWorkflowService
        from hamar_agent.ollama_provider import OllamaClient,OllamaConfig
        from hamar_agent.openai_provider import OpenAIClient,OpenAIConfig
        from hamar_agent.search import SearchIndex
        from hamar_agent.web import WebApplication
        from unittest.mock import Mock
        for provider in ('ollama','openai'):
            with self.subTest(provider=provider):
                service,observations=regional_fixture();calls=[]
                def choose(prompt):
                    calls.append(prompt)
                    p=json.loads(prompt.split('SOURCE_PARAGRAPHS=',1)[1].splitlines()[0])[0]
                    return {'claims':[dict(id='c1',text=p['text'],paragraph_id=p['id'],evidence_quote=p['text'])]}
                if provider=='ollama':
                    def transport(url,headers,body,timeout,limit):
                        payload=json.loads(body)
                        return json.dumps({'message':{'content':json.dumps(choose(payload['messages'][0]['content']))}}).encode()
                    client=OllamaClient(OllamaConfig(),transport=transport)
                else:
                    sdk=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs:SimpleNamespace(
                        status='completed',error=None,output_text=json.dumps(choose(kwargs['input'])))),close=Mock())
                    client=OpenAIClient(OpenAIConfig(model='approved-model',api_key='synthetic-only',enabled=True,privacy_authorized=True),sdk_client=sdk)
                workflow=MunicipalWorkflowService(SearchIndex(),client,provider=provider,request_sources=service)
                app=WebApplication(workflow)
                headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000','Content-Type':'application/json','X-Hamar-Token':app.token}
                for question,city in (('Hva koster vann i Gjøvik?','gjovik'),('Hva koster det?','gjovik'),
                                      ('Og Hamar?','hamar'),('Og prisen i Lillehammer?','lillehammer')):
                    response=app.dispatch('POST','/api/answer',headers,json.dumps({'query':question}).encode())
                    self.assertEqual(response.status,200,response.body)
                    answer=json.loads(response.body)['answer']
                    self.assertEqual(answer['answer_status'],'evidence_checked',answer)
                    self.assertEqual(answer['municipality_id'],city)
                    self.assertTrue(all(city+'.kommune.no' in c['url'] for c in answer['citations']))
                self.assertEqual(len(observations),4);self.assertEqual(len(calls),4)
                self.assertNotEqual(observations[0]['request_id'],observations[1]['request_id'])
                for question in ('Og prisen i Ukjentby kommune?','Og prisen i oslo?',
                                 'Og prisen i Hamar og Gjøvik?'):
                    before=(len(observations),len(calls))
                    response=app.dispatch('POST','/api/answer',headers,json.dumps({'query':question}).encode())
                    self.assertEqual((len(observations),len(calls)),before)
                    if response.status==200:self.assertNotEqual(json.loads(response.body)['answer']['answer_status'],'evidence_checked')
                    else:self.assertEqual(response.status,422)


class ResearchTests(unittest.TestCase):
    # Share the established endpoint/client fixture without inheriting or
    # re-counting its test methods in discovery.
    client=chat_tests.ChatTests.client
    drain=chat_tests.ChatTests.drain
    headers=chat_tests.ChatTests.headers
    send=chat_tests.ChatTests.send
    reset=chat_tests.ChatTests.reset
    state=chat_tests.ChatTests.state

    def setUp(self):
        chat_tests.ChatTests.setUp(self)
        self.service,self.observations=service_fixture()
        self.backend.research_service=self.service
        self.backend.web_authorized=True
        self.selection=dict(source_id='public-a',paragraph_id='p1',quote=approval().excerpts[0].text)
        self.response_factory=lambda:chat_tests.sdk_response(json.dumps(self.selection,ensure_ascii=False))

    def ask(self,**changes):
        return self.send('Hva er testtema?',web_search=True,**changes)

    def assert_rejected(self,response,*,model_calls=0):
        self.assertNotEqual(response.status,200,response.body)
        self.assertEqual(len(self.calls),model_calls)
        self.assertEqual(self.state()['messages'],[])
        self.assertEqual(self.app.sessions[self.token].chat.messages,())
        self.assertEqual(self.app.sessions[self.token].chat.turns,0)

    def test_both_providers_select_exact_excerpt_without_native_search(self):
        for provider,model in (('openai','approved-model'),('ollama','llama3.2:3b')):
            with self.subTest(provider=provider):
                self.reset();self.calls.clear();self.observations.clear()
                response=self.ask(provider=provider,model=model)
                self.assertEqual(response.status,200,response.body)
                answer=json.loads(response.body)['reply']
                self.assertEqual(answer['text'],self.selection['quote'])
                self.assertTrue(answer['research_verified']);self.assertFalse(answer['municipal_verified'])
                self.assertTrue(answer['web_search_used']);self.assertEqual(answer['web_search_calls'],0)
                self.assertEqual(answer['source_observation_count'],1)
                self.assertEqual(len(self.calls),1);self.assertEqual(len(self.observations),1)
                self.assertEqual(answer['citations'][0]['url'],approval().url)
                self.assertEqual(answer['source_receipts'][0]['request_id'],self.observations[0]['request_id'])
                if provider=='openai':
                    self.assertNotIn('tools',self.calls[0]['kwargs'])
                    self.assertFalse(self.calls[0]['kwargs']['store'])
                self.assertEqual(active_workers(),0)

    def test_missing_policy_or_fetcher_cannot_fall_through_to_native_sdk(self):
        for service in (None,ResearchService(),ResearchService([approval()])):
            self.backend.research_service=service
            self.assert_rejected(self.ask())
        self.assertEqual(self.observations,[])

    def test_updated_question_without_search_is_zero_call_guidance(self):
        response=self.send('Hva er siste nytt i dag?')
        self.assertEqual(response.status,200)
        self.assertIn('kan ikke bekrefte',json.loads(response.body)['reply']['text'])
        self.assertFalse(json.loads(response.body)['reply']['ai_generated'])
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])
        self.assertEqual(information_need('Forklar en algoritme'),'stable_or_unspecified')

    def test_current_norwegian_weather_currency_require_explicit_search(self):
        for provider,model in (('ollama','llama3.2:3b'),('openai','approved-model')):
            for question in ('Hva er været i Hamar nå?','Dagens valutakurs?','Hva er været i Hamar?'):
                with self.subTest(provider=provider,question=question):
                    self.reset();self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                    response=self.send(question,provider=provider,model=model,web_search=False)
                    self.assertEqual(response.status,200,response.body)
                    self.assertEqual(json.loads(response.body)['reply']['response_origin'],'application_guidance')
                    self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])
        for question in ('Forklar hvordan valutakurser fungerer.','Forklar hvordan vær oppstår.',
                         'Forklar en algoritme nå.'):
            self.assertEqual(information_need(question),'stable_or_unspecified')

    def test_unsupported_and_municipal_questions_never_use_supplement_as_authority(self):
        self.assert_rejected(self.send('Forklar ukjenttema.',web_search=True))
        response=self.send('Hvordan søker jeg SFO-plass?',web_search=True)
        self.assertEqual(response.status,200)
        self.assertIn('Kommunal informasjon',json.loads(response.body)['reply']['text'])
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])

    def test_external_processing_requires_source_specific_approval(self):
        self.backend.research_service,self.observations=service_fixture([approval(external=False)])
        self.assert_rejected(self.ask())
        self.assertEqual(self.observations,[])
        self.assertEqual(self.ask(provider='ollama',model='llama3.2:3b').status,200)

    def test_expired_policy_is_not_renewed_or_used(self):
        self.backend.research_service,self.observations=service_fixture([
            replace(approval(),reviewed_on='2020-01-01',expires_on='2020-01-02')])
        self.assert_rejected(self.ask());self.assertEqual(self.observations,[])

    def test_changed_corrupt_redirected_and_replayed_observations_fail_closed(self):
        changes=(dict(body=b'Changed text'),dict(url='https://127.0.0.1/'),dict(status=302),
            dict(request_id='0'*32),dict(content_type='text/html'),dict(robots=b'changed'),
            dict(retrieved_at='2020-01-01T00:00:00+00:00'),dict(retrieved_at='2999-01-01T00:00:00+00:00'),
            dict(retrieved_at='2020-01-01T00:00:00'),dict(last_modified='invalid'),
            dict(published_at='2999-01-01T00:00:00+00:00'),dict(published_at=0),dict(published_at=False),
            dict(last_modified=False),dict(last_modified=''),dict(published_at=''))
        for change in changes:
            with self.subTest(change=change):
                self.app.sessions[self.token].chat.attempts.clear()
                self.process_window.attempts.clear()
                self.backend.research_service,self.observations=service_fixture(mutate=lambda obj:obj.update(change))
                self.assert_rejected(self.ask())

    def test_source_outage_is_sanitized_and_no_model_is_called(self):
        self.service.fetcher=lambda *a,**k:(_ for _ in ()).throw(OSError('synthetic-private-diagnostic'))
        response=self.ask();self.assert_rejected(response)
        self.assertNotIn('synthetic-private-diagnostic',response.body.decode())

    def test_conflicting_same_scope_facts_abstain_before_generation(self):
        other=approval('public-b',text='Fiktivt testtema: testverdien er 300 enheter.',value='300')
        self.backend.research_service,self.observations=service_fixture([approval(),other])
        response=self.ask();self.assert_rejected(response)
        self.assertEqual(json.loads(response.body)['error_code'],'research_source_conflict')
        self.assertEqual(len(self.observations),2)

    def test_different_periods_are_not_falsely_called_a_conflict(self):
        other=approval('public-b',text='Fiktivt testtema: testverdien var 300 enheter.',value='300',scope=(*FACT[:2],'2025',*FACT[3:]))
        self.backend.research_service,self.observations=service_fixture([approval(),other])
        self.assertEqual(self.ask().status,200)

    def test_wrong_unapproved_or_malformed_model_claim_is_never_published(self):
        values=({},dict(self.selection,quote='Oppdiktet svar.'),dict(self.selection,paragraph_id='p99'),
            dict(self.selection,source_id='unapproved'),dict(self.selection,url='https://example.org/'),[self.selection])
        for value in values:
            with self.subTest(value=value):
                self.calls.clear();self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                self.response_factory=lambda:chat_tests.sdk_response(json.dumps(value))
                self.assert_rejected(self.ask(),model_calls=1)

    def test_native_tool_output_cannot_masquerade_as_research_evidence(self):
        self.response_factory=lambda:chat_tests.sdk_response(json.dumps(self.selection),[{'type':'web_search_call','status':'completed'}])
        self.assert_rejected(self.ask(),model_calls=1)
        self.assertNotIn('tools',self.calls[0]['kwargs'])

    def test_revoke_during_retrieval_prevents_generation_and_later_observations(self):
        original=self.service.fetcher
        def fetch(*args,**kwargs):
            result=original(*args,**kwargs);self.service.revoke();return result
        self.service.fetcher=fetch
        self.assert_rejected(self.ask());self.assertEqual(len(self.observations),1)

    def test_revoke_during_client_creation_prevents_sdk_dispatch_and_closes(self):
        original=self.backend.client_factory
        def create(*args):
            client=original(*args);self.service.revoke();return client
        self.backend.client_factory=create
        self.assert_rejected(self.ask());self.clients[0]._sdk.close.assert_called_once()

    def test_revoke_at_queued_worker_start_has_zero_sdk_calls(self):
        from hamar_agent import run_control
        original=run_control._start
        def start(function,**kwargs):
            if getattr(kwargs.get('owner'),'_research_authorized',None):self.service.revoke()
            return original(function,**kwargs)
        with patch.object(run_control,'_start',side_effect=start):
            self.assert_rejected(self.ask())

    def test_revoke_after_verification_is_rechecked_at_locked_publication(self):
        original=self.service.verify
        def verify(*args):
            answer=original(*args);self.service.revoke();return answer
        self.service.verify=verify
        self.assert_rejected(self.ask(),model_calls=1)

    def test_reset_during_generation_prevents_publication(self):
        def response():
            self.reset();return chat_tests.sdk_response(json.dumps(self.selection))
        self.response_factory=response
        response=self.ask();self.assertEqual(response.status,409,response.body)
        self.assert_rejected(response,model_calls=1)

    def test_privacy_checks_precede_research_and_history(self):
        response=self.send('My full name: SYNTHETIC_TEST_PERSON.',web_search=True)
        self.assertEqual(response.status,400);self.assert_rejected(response)
        self.assertEqual(self.observations,[])

    def test_each_followup_gets_new_observation_and_sessions_stay_separate(self):
        first=self.ask();self.assertEqual(first.status,200)
        second=self.send('Kan du forklare videre?',web_search=True);self.assertEqual(second.status,200,second.body)
        third=self.send('Fortell mer',web_search=True);self.assertEqual(third.status,200,third.body)
        self.assertNotEqual(self.observations[0]['request_id'],self.observations[1]['request_id'])
        self.assertEqual(len({row['request_id'] for row in self.observations}),3)
        token=self.app._new_page_token()
        self.assertEqual(self.state(token)['messages'],[])
        observations=len(self.observations);calls=len(self.calls)
        response=self.send('Forklar et helt annet emne.',web_search=True)
        self.assertEqual(response.status,422)
        self.assertEqual(len(self.observations),observations);self.assertEqual(len(self.calls),calls)
        self.assertEqual(self.app.sessions[self.token].chat.turns,3)

    def test_research_prompt_limit_prevents_model_calls(self):
        original=self.service.prompt
        def prompt(question,binding,history):
            return original(question,binding,[{'role':'user','content':'x'*12000}])
        self.service.prompt=prompt
        self.assert_rejected(self.ask())

    def test_live_cloud_owner_gates_are_rechecked_in_queued_worker(self):
        from hamar_agent import run_control
        from hamar_agent.openai_provider import OpenAIConfig
        config=OpenAIConfig(model='approved-model',api_key='synthetic-fixture-only',enabled=True,privacy_authorized=True)
        self.backend.openai_dispatch_authorized=None
        for gate in ('HAMAR_OPENAI_ENABLED','HAMAR_OPENAI_PRIVACY_AUTHORIZED','HAMAR_OPENAI_MODEL','advanced'):
            with self.subTest(gate=gate):
                self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                self.calls.clear();self.clients.clear()
                self.backend.client_factory=None
                self.backend.advanced_authorized=True
                variant='advanced' if gate=='advanced' else 'standard'
                self.backend.choices_factory=lambda provider:[dict(provider='openai',model='approved-model',available=True,variant=variant)]
                def constructor(*args,**kwargs):return self.client('openai','approved-model')
                start=run_control._start
                def worker(function,**kwargs):
                    if getattr(kwargs.get('owner'),'_research_authorized',None):
                        if gate=='advanced':self.backend.advanced_authorized=False
                        else:
                            import os
                            os.environ[gate]='different-model' if gate.endswith('MODEL') else 'false'
                    return start(function,**kwargs)
                settings=dict(HAMAR_OPENAI_ENABLED='true',HAMAR_OPENAI_PRIVACY_AUTHORIZED='true',
                    HAMAR_OPENAI_MODEL='approved-model',HAMAR_CHAT_OPENAI_ADVANCED_MODEL='approved-model')
                with patch.dict('os.environ',settings),patch('hamar_agent.chat.OpenAIConfig.from_env',return_value=config), \
                        patch('hamar_agent.chat.ChatOpenAIClient',side_effect=constructor),patch.object(run_control,'_start',side_effect=worker):
                    self.assert_rejected(self.ask())
                self.assertEqual(len(self.clients),1);self.drain()
                self.clients[0]._sdk.close.assert_called_once()

    def test_hamar_service_prices_and_followups_require_municipal_authority(self):
        source=replace(approval(),keywords=('vann','parkering','hamar'))
        self.backend.research_service,self.observations=service_fixture([source])
        for provider,model in (('ollama','llama3.2:3b'),('openai','approved-model')):
            for question in ('Hva koster vann i Hamar?','Hva koster parkering i Hamar?'):
                with self.subTest(provider=provider,question=question):
                    self.reset();self.calls.clear();self.observations.clear()
                    self.app.sessions[self.token].chat.attempts.clear();self.process_window.attempts.clear()
                    for message in (question,'Hva koster det?','Og prisen?'):
                        response=self.send(message,provider=provider,model=model,web_search=True)
                        self.assertEqual(response.status,200,response.body)
                        self.assertEqual(('Kommunal informasjon' in json.loads(response.body)['reply']['text'],
                            len(self.observations),len(self.calls)),(True,0,0))
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])

    def test_ordinary_water_science_and_travel_are_not_municipal_service_requests(self):
        for question in ('Forklar vannets kretsløp.','Hva koster flybilletter til Hamar?',
                         'Forklar kjemiske egenskaper til vann.'):
            with self.subTest(question=question):
                context=self.backend.context((),question,False)
                self.assertIsNone(self.backend.managed_reply(context))

    def test_policy_rejects_unreviewed_or_noncanonical_sources(self):
        for changes in (dict(reuse_reviewed=False),dict(non_personal_input_reviewed=False),
                        dict(url='https://www.ssb.no.evil.invalid/path?redirect=1'),dict(url='http://www.ssb.no/'),
                        dict(url='https://localhost/'),dict(content_type='text/html')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(approval(),**changes)
