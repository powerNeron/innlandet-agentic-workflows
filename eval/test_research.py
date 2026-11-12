"""Fictional research observations and mocked providers; no external access."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import eval.test_chat as chat_tests
from hamar_agent.research import ResearchApproval, ResearchExcerpt, ResearchService, information_need
from hamar_agent.run_control import active_workers

ROBOTS=b'User-agent: *\nAllow: /\n'
FACT=('fictional-service','test-value','2026','fictional-area','units')


def approval(source_id='public-a',*,text='Fiktivt testtema: testverdien er 250 enheter.',value='250',scope=FACT,external=True):
    return ResearchApproval(source_id,'https://www.ssb.no/synthetic-offline-'+source_id+'/',
        'Fiktiv testkilde',('testtema',),(ResearchExcerpt('p1',text,scope,value),),
        date.today().isoformat(),(date.today()+timedelta(days=7)).isoformat(),
        hashlib.sha256(ROBOTS).hexdigest(),True,True,external)


def service_fixture(approvals=None,*,mutate=None):
    approvals=tuple(approvals or [approval()]);registry={a.source_id:a for a in approvals};calls=[]
    def fetch(source_id,**kwargs):
        a=registry[source_id];calls.append(dict(source_id=source_id,**kwargs))
        value=dict(source_id=source_id,url=a.url,request_id=kwargs['request_id'],body=a.body,robots=ROBOTS,
            retrieved_at=datetime.now(timezone.utc).isoformat(),status=200,content_type='text/plain')
        if mutate:mutate(value)
        return value
    return ResearchService(approvals,fetcher=fetch),calls


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
