"""Provider policy tests use injected transports and never contact external services."""
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
        return SimpleNamespace(output_text=self.output)


class FakeSDK:
    def __init__(self, output):
        self.responses = FakeResponses(output)
        self.closed = False

    def close(self):
        self.closed = True


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

    def test_server_allowlist_includes_only_configured_local_model_names(self):
        with patch.dict(os.environ, {"HAMAR_OLLAMA_MODEL": "llama3.2:3b",
                                     "HAMAR_OLLAMA_ALLOWED_MODELS": "qwen2.5:3b, llama3.2:3b"}, clear=True):
            self.assertEqual(configured_ollama_models(), ("llama3.2:3b", "qwen2.5:3b"))

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
        service = MunicipalWorkflowService(SearchIndex((document,)), client, provider="openai")
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
        registry = ProviderRegistry(ollama_models=lambda: (),
            openai_config_factory=lambda: (_ for _ in ()).throw(ValueError("private config value")),
            sdk_available=lambda: False)
        app = WebApplication(WorkflowService(), provider_registry=registry)
        headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000"}
        response = app.dispatch("GET", "/api/providers", headers)
        self.assertEqual(response.status, 503)
        self.assertNotIn(b"private config value", response.body)


if __name__ == "__main__":
    unittest.main()
