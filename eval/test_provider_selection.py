"""Provider policy tests use injected transports and never contact external services."""
import json
from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import Mock, patch
from hamar_agent.ollama_provider import OllamaError

from hamar_agent.openai_provider import (OpenAIClient, OpenAIClaimSummarizer,
    OpenAICorrectionProvider, OpenAIConfig, OpenAIProviderError)
from hamar_agent.provider_registry import ProviderRegistry, configured_ollama_models
from hamar_agent.runtime import create_service
from hamar_agent.sources import load_source
from hamar_agent.application import WorkflowService
from hamar_agent.summarize import MockSummarizer
from hamar_agent.web import WebApplication
from hamar_agent.real_sources import MunicipalWorkflowService
from hamar_agent.schemas import Paragraph, Source
from hamar_agent.search import SearchIndex, index_document


class FakeResponses:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(status="completed",error=None,output_text=self.output)


class FakeSDK:
    def __init__(self, output):
        self.responses = FakeResponses(output)
        self.closed = False

    def close(self):
        self.closed = True


class ResponseCompletionTests(unittest.TestCase):
    def test_both_claim_stages_reject_all_incomplete_error_states_before_text(self):
        source=load_source('synthetic-water-demo')
        for stage in ('initial','correction'):
            for status,error in (('incomplete',None),('failed',None),('in_progress',None),('completed',{'code':'synthetic'})):
                with self.subTest(stage=stage,status=status,error=error):
                    reads=[]
                    class Response:
                        @property
                        def output_text(self):
                            reads.append(True);return json.dumps(clean_claim(source))
                    response=Response();response.status=status;response.error=error
                    create=Mock(return_value=response)
                    client=OpenAIClient(OpenAIConfig(model='approved-model',api_key='synthetic-only',enabled=True,
                        privacy_authorized=True),sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create)))
                    with self.assertRaises(OpenAIProviderError):
                        if stage=='initial':OpenAIClaimSummarizer(client).summarize_with_report(source)
                        else:OpenAICorrectionProvider(client).revise(source,(),())
                    self.assertEqual(reads,[]);self.assertEqual(create.call_count,1)

    def test_both_claim_stages_accept_completed_without_error(self):
        source=load_source('synthetic-water-demo')
        for stage in ('initial','correction'):
            with self.subTest(stage=stage):
                sdk=SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=SimpleNamespace(
                    status='completed',error=None,output_text=json.dumps(clean_claim(source))))))
                client=OpenAIClient(OpenAIConfig(model='approved-model',api_key='synthetic-only',enabled=True,
                    privacy_authorized=True),sdk_client=sdk)
                result=(OpenAIClaimSummarizer(client).summarize_with_report(source) if stage=='initial'
                    else OpenAICorrectionProvider(client).revise(source,(),()))
                self.assertTrue(result.claims);self.assertFalse(result.findings)


def clean_claim(source):
    paragraph = source.paragraphs[0]
    return {"claims": [{"id": "c1", "text": paragraph.text,
                        "paragraph_id": paragraph.id, "evidence_quote": paragraph.text}]}


class ProviderSelectionTests(unittest.TestCase):
    def setUp(self):
        self.source = load_source("synthetic-verification-demo")

    def test_openai_is_disabled_without_two_explicit_server_flags_and_key(self):
        with patch.dict(os.environ, {}, clear=True):
            config = OpenAIConfig.from_env()
            self.assertFalse(config.enabled)
            self.assertFalse(config.privacy_authorized)
            with self.assertRaises(OpenAIProviderError):
                OpenAIClient(config, sdk_client=FakeSDK("{}"))

    def test_openai_provider_choices_are_disabled_without_configuration(self):
        registry = ProviderRegistry(ollama_models=lambda: ("llama3.2:3b",), sdk_available=lambda: True)
        with patch.dict(os.environ, {}, clear=True):
            choices = registry.choices()
        cloud = next(choice for choice in choices if choice["provider"] == "openai")
        self.assertFalse(cloud["available"])
        self.assertEqual(cloud["processing"], "external")
        self.assertIn("deaktivert", cloud["reason"])

    def test_municipal_metadata_uses_credential_presence_only_and_constructs_no_client(self):
        class PresenceOnly(dict):
            def __getitem__(self,key):
                if key=='OPENAI_API_KEY':raise AssertionError('Credential value must not be read')
                return super().__getitem__(key)
            def get(self,key,default=None):
                if key=='OPENAI_API_KEY':raise AssertionError('Credential value must not be read')
                return super().get(key,default)
        for enabled,privacy,sdk,state,key_present in ((True,True,True,'configured',True),(False,True,True,'paused',True),
                (True,False,True,'setup_required',True),(True,True,False,'setup_required',True),
                (True,True,True,'setup_required',False)):
            with self.subTest(state=state,privacy=privacy,sdk=sdk):
                environment=PresenceOnly(HAMAR_OPENAI_MODEL='gpt-4.1-mini',HAMAR_OPENAI_ENABLED=str(enabled),
                    HAMAR_OPENAI_PRIVACY_AUTHORIZED=str(privacy))
                if key_present:environment['OPENAI_API_KEY']='synthetic-membership-only'
                registry=ProviderRegistry(ollama_models=lambda:('llama3.2:3b',),sdk_available=lambda:sdk)
                created=Mock(side_effect=AssertionError('Metadata must not construct a workflow'))
                app=WebApplication(provider_registry=registry,service_factory=created)
                with patch.object(os,'environ',environment), \
                        patch('hamar_agent.openai_provider.OpenAIConfig.from_env',side_effect=AssertionError('No credential loading')), \
                        patch('hamar_agent.openai_provider.OpenAIClient',side_effect=AssertionError('No SDK client')):
                    response=app.dispatch('GET','/api/providers',{'Host':'127.0.0.1:8000'})
                self.assertEqual(response.status,200)
                cloud=next(c for c in json.loads(response.body)['choices'] if c['provider']=='openai')
                self.assertEqual(cloud['model'],'gpt-4.1-mini');self.assertEqual(cloud['availability_status'],state)
                self.assertEqual(cloud['available'],state=='configured')
                self.assertEqual(cloud['connection_status'],'not_checked')
                self.assertNotIn('synthetic-membership-only',response.body.decode())
                created.assert_not_called()

    def test_disabled_municipal_openai_rejects_forged_selection_without_constructing_provider(self):
        config=OpenAIConfig(model='gpt-4.1-mini',api_key='synthetic-only',enabled=False,privacy_authorized=True)
        factory=Mock(side_effect=AssertionError('Owner-disabled paid provider must not be created'))
        registry=ProviderRegistry(ollama_models=lambda:('llama3.2:3b',),openai_config_factory=lambda:config,sdk_available=lambda:True)
        app=WebApplication(provider_registry=registry,service_factory=factory)
        headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000','Content-Type':'application/json','X-Hamar-Token':app.token}
        response=app.dispatch('POST','/api/answer',headers,b'{"query":"vann","provider":"openai","model":"gpt-4.1-mini"}')
        self.assertEqual(response.status,400);factory.assert_not_called()
        self.assertFalse(app.sessions[app.token].chat.messages)

    def test_both_selected_municipal_providers_use_same_strict_workflow_and_source_gate(self):
        from hamar_agent.ollama_provider import OllamaClient,OllamaConfig
        from hamar_agent.portal import PortalService
        text='Fictional water service: vann koster 250 kroner.'
        source=Source('municipal-test','Fictional water fixture',(Paragraph('p1',text),),False,
                      'https://www.hamar.kommune.no/fictional-test-only/')
        now=datetime.now(timezone.utc)
        config=OpenAIConfig(model='gpt-4.1-mini',api_key='synthetic-only',enabled=True,privacy_authorized=True)
        for provider,model in (('ollama','llama3.2:3b'),('openai','gpt-4.1-mini')):
            for case in ('exact','changed-number','multiple','expired','unapproved'):
                with self.subTest(provider=provider,case=case):
                    expiry=(now.date()+timedelta(days=-1 if case=='expired' else 2)).isoformat()
                    doc=index_document(source,'teknisk',retrieved_at=(now-timedelta(days=2)).isoformat(),approval_expires=expiry)
                    index=SearchIndex([] if case=='unapproved' else [doc]);dispatches=[];created=[]
                    claim={'id':'c1','text':text if case!='changed-number' else text.replace('250','999'),
                           'paragraph_id':'municipal-test:p1','evidence_quote':text}
                    claims=[claim,{**claim,'id':'c2'}] if case=='multiple' else [claim]
                    def factory(selected,selected_model):
                        self.assertEqual((selected,selected_model),(provider,model))
                        def payload():
                            dispatches.append(selected)
                            return json.dumps({'claims':claims})
                        if selected=='openai':
                            sdk=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs:SimpleNamespace(status="completed",error=None,output_text=payload())),close=lambda:None)
                            client=OpenAIClient(config,sdk_client=sdk)
                        else:
                            client=OllamaClient(OllamaConfig(model=selected_model),transport=lambda *args:json.dumps({'message':{'content':payload()}}).encode())
                        workflow=MunicipalWorkflowService(index,client,provider=selected, historical_baseline=True);created.append(workflow);return workflow
                    registry=ProviderRegistry(ollama_models=lambda:('llama3.2:3b',),openai_config_factory=lambda:config,sdk_available=lambda:True)
                    base=WorkflowService();app=WebApplication(base,portal=PortalService(base,index=index),
                        provider_registry=registry,service_factory=factory)
                    headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000','Content-Type':'application/json','X-Hamar-Token':app.token}
                    body=json.dumps({'query':'vann','provider':provider,'model':model}).encode()
                    with patch.object(app.chat_backend,'generate',side_effect=AssertionError('Municipal answer cannot use general chat')), \
                            patch('socket.socket',side_effect=AssertionError('No real provider or source fetch')), \
                            patch('socket.getaddrinfo',side_effect=AssertionError('No real DNS')):
                        response=app.dispatch('POST','/api/answer',headers,body)
                    self.assertIsInstance(created[0],MunicipalWorkflowService)
                    self.assertFalse(app.sessions[app.token].chat.messages)
                    if case=='exact':
                        self.assertEqual(response.status,200);answer=json.loads(response.body)['answer']
                        self.assertEqual(answer['answer_status'],'evidence_checked')
                        self.assertEqual(answer['result']['claims'][0]['text'],text)
                        self.assertEqual(answer['citations'][0]['url'],source.url)
                        self.assertEqual(answer['citations'][0]['approval_status'],'within_recorded_period')
                        self.assertEqual(dispatches,[provider])
                    elif case in ('expired','unapproved'):
                        self.assertEqual(response.status,200)
                        self.assertEqual(json.loads(response.body)['answer']['answer_status'],'insufficient_evidence')
                        self.assertEqual(dispatches,[])
                        # Existing owned exports also retain safe refusals; none may contain model claims.
                        self.assertTrue(all(json.loads(raw)['result'] is None for raw in app.results.values()))
                    else:
                        self.assertEqual(response.status,422);self.assertFalse(app.results)
                        self.assertEqual(dispatches,[provider]*(2 if case=='changed-number' else 1))

    def test_server_allowlist_includes_only_configured_local_model_names(self):
        with patch.dict(os.environ, {"HAMAR_OLLAMA_MODEL": "llama3.2:3b",
                                     "HAMAR_OLLAMA_ALLOWED_MODELS": "qwen2.5:3b, llama3.2:3b"}, clear=True):
            self.assertEqual(configured_ollama_models(), ("llama3.2:3b", "qwen2.5:3b"))

    def test_cloud_selection_does_not_inspect_or_probe_local_configuration(self):
        config = OpenAIConfig(model='synthetic-cloud', api_key='synthetic-only', enabled=True, privacy_authorized=True)
        local_probe = Mock(side_effect=AssertionError('Unselected provider must not be probed'))
        registry = ProviderRegistry(ollama_models=local_probe,
            openai_config_factory=lambda: config, sdk_available=lambda: True)
        with patch.dict(os.environ, {'HAMAR_OLLAMA_MODEL': 'invalid/model'}, clear=True), \
             patch('hamar_agent.provider_registry.configured_ollama_models', side_effect=AssertionError('Unselected local settings read')):
            choice = registry.require_choice('openai', 'synthetic-cloud')
        self.assertTrue(choice['available'])
        self.assertEqual(choice['connection_status'], 'not_checked')
        local_probe.assert_not_called()

    def test_local_selection_does_not_inspect_cloud_configuration_or_sdk(self):
        cloud_config = Mock(side_effect=AssertionError('Unselected cloud configuration read'))
        cloud_sdk = Mock(side_effect=AssertionError('Unselected cloud SDK inspected'))
        registry = ProviderRegistry(ollama_models=lambda: ('llama3.2:3b',),
            openai_config_factory=cloud_config, sdk_available=cloud_sdk)
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(registry.require_choice('ollama', 'llama3.2:3b')['available'])
        cloud_config.assert_not_called()
        cloud_sdk.assert_not_called()

    def test_bad_local_configuration_does_not_hide_configured_cloud_choice(self):
        config = OpenAIConfig(model='synthetic-cloud', api_key='synthetic-only', enabled=True, privacy_authorized=True)
        for local_settings, failure in (({'HAMAR_OLLAMA_MODEL': 'invalid/model'}, None),
                                         ({}, TimeoutError('synthetic-private-diagnostic'))):
            with self.subTest(settings=local_settings), patch.dict(os.environ, local_settings, clear=True):
                probe = Mock(side_effect=failure, return_value=())
                registry = ProviderRegistry(ollama_models=probe,
                    openai_config_factory=lambda: config, sdk_available=lambda: True)
                choices = registry.choices()
                cloud = next(c for c in choices if c['provider'] == 'openai')
                self.assertTrue(cloud['available'])
                self.assertFalse(any(c['available'] for c in choices if c['provider'] == 'ollama'))
                self.assertNotIn('synthetic-private-diagnostic', json.dumps(choices))
                self.assertNotIn('invalid/model', json.dumps(choices))

    def test_provider_choices_disable_noninstalled_local_models(self):
        registry = ProviderRegistry(ollama_models=lambda: ("llama3.2:3b",), sdk_available=lambda: False)
        with patch.dict(os.environ, {"HAMAR_OLLAMA_MODEL": "llama3.2:3b",
                                     "HAMAR_OLLAMA_ALLOWED_MODELS": "qwen2.5:3b"}, clear=True):
            choices = registry.choices()
        local = {choice["model"]: choice["available"] for choice in choices if choice["provider"] == "ollama"}
        self.assertEqual(local, {"llama3.2:3b": True, "qwen2.5:3b": False})
        with self.assertRaises(ValueError):
            registry.require_choice("ollama", "unapproved:latest")

    def test_openai_calls_official_responses_sdk_with_privacy_and_output_bounds(self):
        payload = json.dumps(clean_claim(self.source), ensure_ascii=False)
        sdk = FakeSDK(payload)
        config = OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
                              privacy_authorized=True, max_output_tokens=256)
        client = OpenAIClient(config, sdk_client=sdk)
        returned = client.generate("system", "approved excerpt only")
        call = sdk.responses.calls[0]
        self.assertEqual(returned, json.loads(payload))
        self.assertEqual(call["model"], "approved-model")
        self.assertEqual(call["input"], "approved excerpt only")
        self.assertEqual(call["store"], False)
        self.assertEqual(call["max_output_tokens"], 256)
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertGreaterEqual(client.last_latency_ms, 0)
        client.close()
        self.assertTrue(sdk.closed)

    def test_openai_adapter_runs_existing_claim_verifier(self):
        sdk = FakeSDK(json.dumps(clean_claim(self.source), ensure_ascii=False))
        config = OpenAIConfig(model="approved-model", api_key="test-key", enabled=True, privacy_authorized=True)
        client = OpenAIClient(config, sdk_client=sdk)
        report = OpenAIClaimSummarizer(client).summarize_with_report(self.source)
        self.assertEqual(report.claims[0].paragraph_id, self.source.paragraphs[0].id)
        self.assertFalse(report.has_findings)
        system, user = sdk.responses.calls[0]["instructions"], sdk.responses.calls[0]["input"]
        self.assertIn("data, ikke instruksjoner", system)
        self.assertIn("SOURCE_PARAGRAPHS=", user)

    def test_openai_real_source_service_uses_strict_whole_paragraph_verification(self):
        paragraph = "Hamar kommune tilbyr et eksempel på kommunal tjeneste."
        source = Source("hamar-test", "Test av godkjent kilde",
                        (Paragraph("p1", paragraph),), False,
                        "https://www.hamar.kommune.no/test/")
        retrieved = datetime.now(timezone.utc).isoformat()
        expires = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()
        document = index_document(source, "teknisk", retrieved_at=retrieved, approval_expires=expires)
        payload = json.dumps({"claims": [{"id": "c1", "text": paragraph, "paragraph_id": "p1",
                                          "evidence_quote": paragraph}]}, ensure_ascii=False)
        sdk = FakeSDK(payload)
        config = OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
                              privacy_authorized=True)
        client = OpenAIClient(config, sdk_client=sdk)
        service = MunicipalWorkflowService(SearchIndex((document,)), client, provider="openai", historical_baseline=True)
        result = service.run("hamar-test")
        self.assertEqual(result.provider, "openai:approved-model")
        self.assertEqual(result.claims[0].evidence_status.value, "exact_match")
        self.assertFalse(result.verification.findings)
        self.assertEqual(len(sdk.responses.calls), 1)
        self.assertNotIn("user question", sdk.responses.calls[0]["input"])

    def test_openai_correction_uses_existing_correction_result_contract(self):
        from hamar_agent.verify import VerificationFinding, FindingCode
        from hamar_agent.schemas import Claim
        sdk = FakeSDK(json.dumps(clean_claim(self.source), ensure_ascii=False))
        client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
                                           privacy_authorized=True), sdk_client=sdk)
        previous = Claim("c1", "invalid", "p999", "invalid")
        result = OpenAICorrectionProvider(client).revise(
            self.source, (previous,), (VerificationFinding(FindingCode.INVALID_PARAGRAPH_ID,
            "Review required", ("c1",)),))
        self.assertEqual(result.provider, "openai:approved-model")
        self.assertEqual(result.claims[0].text, self.source.paragraphs[0].text)
        self.assertIn("VERIFIER_FINDINGS=", sdk.responses.calls[0]["input"])

    def test_openai_sdk_error_is_sanitized_and_never_echoes_key(self):
        class FailingResponses:
            def create(self, **kwargs):
                raise RuntimeError("Authorization: secret-value")
        sdk = SimpleNamespace(responses=FailingResponses())
        client = OpenAIClient(OpenAIConfig(model="approved", api_key="secret-value", enabled=True,
                                           privacy_authorized=True), sdk_client=sdk)
        with self.assertRaises(OpenAIProviderError) as raised:
            client.generate("system", "safe prompt")
        self.assertNotIn("secret-value", str(raised.exception))

    def test_runtime_openai_selection_requires_explicit_server_authorization(self):
        with patch.dict(os.environ, {"HAMAR_OPENAI_ENABLED": "false",
                                     "HAMAR_OPENAI_PRIVACY_AUTHORIZED": "false",
                                     "HAMAR_OPENAI_MODEL": "approved-model",
                                     "OPENAI_API_KEY": "test-key"}, clear=True):
            with self.assertRaises(OpenAIProviderError):
                create_service("openai")

    def test_web_provider_choice_is_server_allowlisted_and_factory_receives_selection(self):
        registry = ProviderRegistry(ollama_models=lambda: ("llama3.2:3b",), sdk_available=lambda: False)
        requested = []
        def factory(provider, model):
            requested.append((provider, model))
            return WorkflowService(summarizer=MockSummarizer(), provider=f"{provider}:{model}")
        service = WorkflowService()
        app = WebApplication(service, provider_registry=registry, service_factory=factory)
        headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000",
                   "Content-Type": "application/json", "X-Hamar-Token": app.token}
        permitted = app.dispatch("POST", "/api/answer", headers,
            b'{"query":"vann","provider":"ollama","model":"llama3.2:3b"}')
        self.assertEqual(permitted.status, 200)
        self.assertEqual(requested, [("ollama", "llama3.2:3b")])
        rejected = app.dispatch("POST", "/api/answer", headers,
            b'{"query":"vann","provider":"ollama","model":"unapproved:latest"}')
        self.assertEqual(rejected.status, 400)
        self.assertEqual(requested, [("ollama", "llama3.2:3b")])

    def test_openai_unavailable_selection_never_constructs_provider(self):
        registry = ProviderRegistry(ollama_models=lambda: (), sdk_available=lambda: False)
        calls = []
        app = WebApplication(WorkflowService(), provider_registry=registry,
                             service_factory=lambda *args: calls.append(args))
        headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000",
                   "Content-Type": "application/json", "X-Hamar-Token": app.token}
        response = app.dispatch("POST", "/api/answer", headers,
            b'{"query":"vann","provider":"openai","model":""}')
        self.assertEqual(response.status, 400)
        self.assertEqual(calls, [])

    def test_provider_discovery_failure_is_safe_and_does_not_leak_configuration(self):
        registry = ProviderRegistry(ollama_models=lambda: ("llama3.2:3b",),
            openai_config_factory=lambda: (_ for _ in ()).throw(ValueError("private config value")),
            sdk_available=lambda: False)
        app = WebApplication(WorkflowService(), provider_registry=registry)
        headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000"}
        response = app.dispatch("GET", "/api/providers", headers)
        self.assertEqual(response.status, 200)
        choices = json.loads(response.body)["choices"]
        self.assertTrue(next(c for c in choices if c["provider"] == "ollama")["available"])
        cloud = next(c for c in choices if c["provider"] == "openai")
        self.assertFalse(cloud["available"])
        self.assertEqual(cloud["availability_status"], "configuration_error")
        self.assertNotIn(b"private config value", response.body)

    def test_configured_cloud_choice_never_claims_verified_connectivity(self):
        config = OpenAIConfig(model="approved-model", api_key="synthetic-secret", enabled=True, privacy_authorized=True)
        registry = ProviderRegistry(ollama_models=lambda: ("llama3.2:3b",),
                                    openai_config_factory=lambda: config, sdk_available=lambda: True)
        with patch("socket.socket", side_effect=AssertionError("No cloud probe allowed")):
            choices = registry.choices()
        cloud = next(c for c in choices if c["provider"] == "openai")
        self.assertTrue(cloud["available"])
        self.assertEqual(cloud["availability_status"], "configured")
        self.assertEqual(cloud["connection_status"], "not_checked")
        self.assertFalse(cloud["generation_verified"])
        self.assertNotIn("synthetic-secret", json.dumps(choices))
        local = next(c for c in choices if c["provider"] == "ollama")
        self.assertEqual(local["connection_status"], "local_catalog_verified")
        self.assertFalse(local["generation_verified"])

    def test_sdk_failure_categories_are_sanitized_and_do_not_retry(self):
        cases = [(401, "provider_authentication"), (403, "provider_authentication"),
                 (429, "provider_rate_limit"), (504, "provider_timeout"),
                 (503, "provider_unavailable"), (404, "provider_model_unavailable"),
                 (400, "provider_configuration"), (None, "provider_unavailable")]
        for status, expected in cases:
            with self.subTest(status=status):
                error = RuntimeError("Authorization: synthetic-secret; private provider body")
                error.status_code = status
                create = Mock(side_effect=error)
                client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="synthetic-secret",
                    enabled=True, privacy_authorized=True), sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create)))
                with self.assertRaises(OpenAIProviderError) as caught:
                    client.generate("system", "synthetic source")
                self.assertEqual(caught.exception.code, expected)
                self.assertNotIn("synthetic-secret", str(caught.exception))
                self.assertNotIn("private provider body", str(caught.exception))
                self.assertEqual(create.call_count, 1)
                self.assertIsNotNone(client.last_latency_ms)

    def test_sdk_timeout_and_malformed_responses_have_distinct_safe_categories(self):
        class APITimeoutError(RuntimeError):
            pass
        for error in (TimeoutError("synthetic-secret"), APITimeoutError("synthetic-secret")):
            create = Mock(side_effect=error)
            client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
                privacy_authorized=True), sdk_client=SimpleNamespace(responses=SimpleNamespace(create=create)))
            with self.assertRaises(OpenAIProviderError) as caught:
                client.generate("system", "synthetic source")
            self.assertEqual(caught.exception.code, "provider_timeout")
        for output in ("", "not-json", "[]", "x" * 17000):
            client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
                privacy_authorized=True), sdk_client=FakeSDK(output))
            with self.assertRaises(OpenAIProviderError) as caught:
                client.generate("system", "synthetic source")
            self.assertEqual(caught.exception.code, "provider_response_invalid")

    def test_both_providers_fail_safely_and_recover_through_public_answer_route(self):
        source = Source("fictional-water", "Syntetisk testkilde om vann",
            (Paragraph("p1", "Dette er et oppdiktet eksempel om vann i kommunen."),), False,
            "https://www.hamar.kommune.no/fictional-water-test-only/")
        doc = index_document(source, "teknisk", retrieved_at=datetime.now(timezone.utc).isoformat(),
            approval_expires=(datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat())
        def grounded(system, prompt):
            paragraph = json.loads(prompt.split("SOURCE_PARAGRAPHS=", 1)[1].splitlines()[0])[0]
            return {"claims": [{"id": "c1", "paragraph_id": paragraph["id"],
                "text": paragraph["text"], "evidence_quote": paragraph["text"]}]}
        for provider, error_type in (("ollama", OllamaError), ("openai", OpenAIProviderError)):
            codes = ["provider_authentication", "provider_timeout", "provider_rate_limit",
                     "provider_unavailable", "provider_response_invalid"]
            if provider == "openai":
                codes.append("provider_quota")
            for code in codes:
                with self.subTest(provider=provider, code=code):
                    generate = Mock(side_effect=error_type("synthetic-secret", code=code))
                    client = SimpleNamespace(config=SimpleNamespace(model="test-model"), generate=generate)
                    service = MunicipalWorkflowService(SearchIndex((doc,)), client, provider=provider, historical_baseline=True)
                    app = WebApplication(service)
                    headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000",
                        "Content-Type": "application/json", "X-Hamar-Token": app.token}
                    response = app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}')
                    self.assertEqual(response.status, 429 if code == "provider_rate_limit" else 422)
                    self.assertEqual(json.loads(response.body)["error_code"], code)
                    self.assertEqual(json.loads(response.body)["retryable"], code not in {"provider_authentication", "provider_quota"})
                    self.assertNotIn(b"synthetic-secret", response.body)
                    self.assertEqual(len(app.results), 0)
                    self.assertEqual(generate.call_count, 1)
                    generate.side_effect = grounded
                    recovered = app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}')
                    self.assertEqual(recovered.status, 200)
                    answer = json.loads(recovered.body)["answer"]
                    self.assertEqual(answer["answer_status"], "evidence_checked")
                    self.assertEqual(answer["result"]["provider"], provider+":test-model")
                    self.assertFalse(answer["result"]["verification"]["findings"])
                    self.assertEqual(answer["result"]["claims"][0]["text"], source.paragraphs[0].text)

    def test_quota_failure_does_not_suggest_automatic_retry(self):
        error = RuntimeError("synthetic-secret")
        error.status_code = 429
        error.code = "insufficient_quota"
        client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="test-key", enabled=True,
            privacy_authorized=True), sdk_client=SimpleNamespace(responses=SimpleNamespace(create=Mock(side_effect=error))))
        with self.assertRaises(OpenAIProviderError) as caught:
            client.generate("system", "synthetic source")
        self.assertEqual(caught.exception.code, "provider_quota")

    def test_live_smoke_requires_separate_local_and_paid_opt_in_before_execution(self):
        from eval import ollama_smoke as smoke
        for arguments in (["--workflow", "--output", "output/unused"],
                          ["--workflow", "--provider", "openai", "--output", "output/unused"],
                          ["--workflow", "--provider", "openai", "--enable-paid-api", "--output", "output/unused"],
                          ["--source-id", "synthetic-water-demo", "--provider", "openai"]):
            with self.subTest(arguments=arguments), patch.object(smoke, "workflow_smoke") as execute:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    smoke.main(arguments)
                self.assertEqual(caught.exception.code, 2)
                execute.assert_not_called()

    def test_openai_smoke_check_only_never_loads_credentials_or_probes_network(self):
        from eval import ollama_smoke as smoke
        class PresenceOnly(dict):
            def __getitem__(self, key):
                if key.startswith(("OPENAI", "HAMAR_OPENAI")):
                    raise AssertionError("Credential values must not be read")
                return super().__getitem__(key)
            def get(self, key, default=None):
                if key.startswith(("OPENAI", "HAMAR_OPENAI")):
                    raise AssertionError("Credential values must not be read")
                return super().get(key, default)
        entries = PresenceOnly({name: "synthetic-do-not-read" for name in
            ("OPENAI_API_KEY", "HAMAR_OPENAI_MODEL", "HAMAR_OPENAI_ENABLED", "HAMAR_OPENAI_PRIVACY_AUTHORIZED")})
        output = io.StringIO()
        with patch.object(smoke.os, "environ", entries), patch.object(smoke.importlib.util, "find_spec", return_value=object()), \
                patch.object(smoke, "_live_client", side_effect=AssertionError("No client allowed")), redirect_stdout(output):
            code = smoke.main(["--workflow", "--provider", "openai", "--check-only"])
        self.assertEqual(code, 0)
        status = json.loads(output.getvalue())
        self.assertFalse(status["connectivity_verified"])
        self.assertFalse(status["generation_verified"])
        self.assertNotIn("synthetic-do-not-read", output.getvalue())

    def test_openai_smoke_missing_prerequisites_return_non_success(self):
        from eval import ollama_smoke as smoke
        with patch.dict(os.environ, {}, clear=True), patch.object(smoke.importlib.util, "find_spec", return_value=None), redirect_stdout(io.StringIO()):
            self.assertEqual(smoke.main(["--workflow", "--provider", "openai", "--check-only"]), 3)

    def smoke_output(self):
        root = Path(__file__).resolve().parents[1] / "output"
        root.mkdir(exist_ok=True)
        return root / ("mock-smoke-unit-" + uuid.uuid4().hex)

    def test_strict_smoke_records_grounded_answer_refusals_and_budget_without_real_calls(self):
        from eval import ollama_smoke as smoke
        from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
        output = self.smoke_output()
        def transport(url, headers, body, timeout, limit):
            prompt = json.loads(body)["messages"][0]["content"]
            paragraph = json.loads(prompt.split("SOURCE_PARAGRAPHS=", 1)[1].splitlines()[0])[0]
            return json.dumps({"message": {"content": json.dumps({"claims": [{"id": "c1",
                "text": paragraph["text"], "paragraph_id": paragraph["id"], "evidence_quote": paragraph["text"]}]})}}).encode()
        client = OllamaClient(OllamaConfig(), transport=transport)
        with patch.object(smoke, "_live_client", return_value=client), redirect_stdout(io.StringIO()):
            code = smoke.main(["--workflow", "--enable-local-llm", "--repeats", "1", "--output", str(output)])
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        records = [json.loads(line) for line in (output / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(code, 0)
        self.assertEqual((summary["executed"], summary["passed"], summary["generation_tasks_started"]), (4, 4, 1))
        self.assertTrue(summary["content_synthetic"])
        self.assertTrue(summary["source_approval_simulated"])
        self.assertEqual(summary["active_workers_at_return"], 0)
        self.assertTrue(records[0]["grounded"])
        self.assertTrue(records[0]["citation_valid"])
        self.assertTrue(all(r["audit"]["provider_tasks_started"] == 0 for r in records[1:]))

    def test_strict_smoke_preserves_failure_and_does_not_count_refusal_as_model_success(self):
        from eval import ollama_smoke as smoke
        from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
        output = self.smoke_output()
        client = OllamaClient(OllamaConfig(), transport=Mock(side_effect=OllamaError("private synthetic body")))
        with patch.object(smoke, "_live_client", return_value=client), redirect_stdout(io.StringIO()):
            code = smoke.main(["--workflow", "--enable-local-llm", "--repeats", "1", "--output", str(output)])
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["positive_passed"], 0)
        self.assertFalse(summary["success"])
        self.assertEqual(summary["passed"], 3)
        self.assertNotIn("private synthetic body", (output / "raw.jsonl").read_text(encoding="utf-8"))

    def test_strict_smoke_refuses_existing_or_non_evidence_output_before_client_creation(self):
        from eval import ollama_smoke as smoke
        existing = self.smoke_output()
        existing.mkdir()
        outside_output = Path(__file__).resolve().parents[1] / ("not-an-evidence-directory-" + uuid.uuid4().hex)
        for target in (existing, outside_output):
            with self.subTest(target=target), patch.object(smoke, "_live_client") as create:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    smoke.main(["--workflow", "--enable-local-llm", "--output", str(target)])
                self.assertEqual(caught.exception.code, 2)
                create.assert_not_called()

    def test_authorized_paid_smoke_is_limited_to_one_call_with_mock_sdk_only(self):
        from eval import ollama_smoke as smoke
        output = self.smoke_output()
        paragraph = load_source("synthetic-water-demo").paragraphs[0]
        sdk = FakeSDK(json.dumps({"claims": [{"id": "c1", "text": paragraph.text,
            "paragraph_id": "provider-smoke-fixture:" + paragraph.id, "evidence_quote": paragraph.text}]}))
        client = OpenAIClient(OpenAIConfig(model="approved-model", api_key="synthetic-never-log",
            enabled=True, privacy_authorized=True), sdk_client=sdk)
        with patch.object(smoke, "_live_client", return_value=client), redirect_stdout(io.StringIO()):
            code = smoke.main(["--workflow", "--provider", "openai", "--enable-paid-api", "--repeats", "1", "--output", str(output)])
        self.assertEqual(code, 0)
        self.assertEqual(len(sdk.responses.calls), 1)
        self.assertEqual(sdk.responses.calls[0]["max_output_tokens"], 512)
        self.assertFalse(sdk.responses.calls[0]["store"])
        self.assertTrue(sdk.closed)
        summary_text = (output / "summary.json").read_text(encoding="utf-8")
        self.assertNotIn("synthetic-never-log", summary_text)
        self.assertEqual(json.loads(summary_text)["policy"]["max_calls"], 1)
        self.assertIsNone(json.loads(summary_text)["actual_transport_calls"])
        self.assertEqual(json.loads(summary_text)["generation_tasks_started"], 1)

    def test_live_smoke_cleanup_failure_is_sanitized_and_preserves_primary_failure(self):
        from eval import ollama_smoke as smoke
        from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
        output = self.smoke_output()
        client = OllamaClient(OllamaConfig(), transport=Mock())
        client.close = Mock(side_effect=RuntimeError("synthetic-secret cleanup body"))
        with patch.object(smoke, "_live_client", return_value=client), \
                patch("hamar_agent.real_sources.MunicipalWorkflowService", side_effect=ValueError("synthetic-secret primary body")), \
                redirect_stdout(io.StringIO()) as stdout:
            code = smoke.main(["--workflow", "--enable-local-llm", "--repeats", "1", "--output", str(output)])
        summary_text = (output / "summary.json").read_text(encoding="utf-8")
        summary = json.loads(summary_text)
        self.assertEqual(code, 1)
        self.assertEqual(summary["failure"]["type"], "ValueError")
        self.assertEqual(summary["cleanup_failure"], {"type": "RuntimeError", "code": "provider_cleanup_failed"})
        self.assertFalse(summary["success"])
        self.assertNotIn("synthetic-secret", summary_text + stdout.getvalue())

    def test_live_smoke_distinguishes_pre_transport_failure_from_actual_dispatch(self):
        from eval import ollama_smoke as smoke
        from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
        output = self.smoke_output()
        transport = Mock(side_effect=AssertionError("Preflight must prevent transport"))
        client = OllamaClient(OllamaConfig(max_request_chars=512), transport=transport)
        with patch.object(smoke, "_live_client", return_value=client), redirect_stdout(io.StringIO()):
            code = smoke.main(["--workflow", "--enable-local-llm", "--repeats", "1", "--output", str(output)])
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["generation_tasks_started"], 1)
        self.assertEqual(summary["actual_transport_calls"], 0)
        transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
