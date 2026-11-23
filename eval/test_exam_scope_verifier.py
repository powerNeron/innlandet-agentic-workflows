"""Independent exam-scope contracts; synthetic wire/models, never live HTTP.

The complete municipality roster is identity metadata, not source permission.
These contracts exercise production policy composition without editing it.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import eval.test_live_research as live_tests
from hamar_agent.live_research import LiveResearchService
from hamar_agent.research import ResearchError, ResearchService, load_research_policy
from hamar_agent.run_control import run_scope


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs/innlandet-research.json"
ACTIVE = frozenset(("hamar", "elverum", "gjovik"))
PROVIDERS = (("ollama", "llama3.2:3b"), ("openai", "gpt-4.1-mini"))


class ExamScopeVerifierTests(unittest.TestCase):
    def setUp(self):
        self.case = live_tests.LiveResearchTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.live = LiveResearchService.from_reviewed_policy(
            POLICY, enabled=True, transport=self.case.wire.transport,
            external_policy=lambda url, digest: True,  # Synthetic cloud only.
        )
        self.case.live = self.live
        self.case.backend.research_service = self.live

    @staticmethod
    def located(entry):
        return entry.name + (" i Innlandet" if entry.requires_region else "")

    def test_shipped_policy_preserves_46_identities_and_activates_exactly_three(self):
        self.assertEqual(len(self.live.municipalities.entries), 46)
        self.assertEqual(self.live.active_municipalities, ACTIVE)
        service = ResearchService.from_reviewed_policy(POLICY)
        self.assertEqual(service.active_municipalities, ACTIVE)
        self.assertEqual(service.municipalities.fingerprint(), self.live.municipalities.fingerprint())

    def test_all_43_inactive_identities_refuse_before_dns_or_source_fetch(self):
        inactive = [m for key, m in self.live.municipalities.entries.items() if key not in ACTIVE]
        self.assertEqual(len(inactive), 43)
        for provider, _ in PROVIDERS:
            for entry in inactive:
                with self.subTest(provider=provider, municipality=entry.id):
                    before = len(self.case.wire.calls), self.case.wire.resolver.call_count
                    with run_scope(), self.assertRaises(ResearchError) as caught:
                        self.live.prepare("Hva koster SFO i " + self.located(entry) + "?",
                                          provider=provider, authorized=lambda: True,
                                          require_municipal=True)
                    self.assertEqual(caught.exception.code, "research_municipality_inactive")
                    self.assertEqual((len(self.case.wire.calls), self.case.wire.resolver.call_count), before)

    def test_chat_inactive_places_are_explicit_and_never_publish_or_call_models(self):
        inactive = [m for key, m in self.live.municipalities.entries.items() if key not in ACTIVE]
        for provider, model in PROVIDERS:
            for entry in inactive:
                with self.subTest(provider=provider, municipality=entry.id):
                    self.case.clear()
                    response = self.case.send("Hva koster SFO i " + self.located(entry) + "?",
                                              provider=provider, model=model)
                    payload = json.loads(response.body)
                    self.assertNotEqual(response.status, 200, payload)
                    self.assertEqual(payload.get("error_code"), "research_municipality_inactive", payload)
                    for name in ("Hamar", "Elverum", "Gjøvik"):
                        self.assertIn(name, payload.get("error", ""))
                    self.assertEqual(self.case.calls, [])
                    self.assertEqual(self.case.wire.calls, [])
                    self.assertEqual(self.case.state()["messages"], [])

    def test_each_active_place_can_publish_its_own_current_synthetic_source(self):
        for provider, model in PROVIDERS:
            for city in sorted(ACTIVE):
                with self.subTest(provider=provider, municipality=city):
                    self.case.clear()
                    entry = self.live.municipalities.entries[city]
                    response = self.case.send("Hva koster SFO i " + entry.name + "?",
                                              provider=provider, model=model)
                    self.assertEqual(response.status, 200, response.body)
                    reply = json.loads(response.body)["reply"]
                    self.assertEqual(reply["municipality_id"], city)
                    self.assertTrue(reply["research_verified"])
                    self.assertTrue(reply["citations"])
                    self.assertTrue(all(c["url"].startswith("https://" + entry.official_host + "/")
                                        for c in reply["citations"]))
                    self.assertEqual(len(self.case.calls), 1)

    def test_inactive_followup_cannot_inherit_or_republish_the_last_active_place(self):
        for provider, model in PROVIDERS:
            with self.subTest(provider=provider):
                self.case.clear()
                response = self.case.send("Hva koster SFO i Hamar?", provider=provider, model=model)
                self.assertEqual(response.status, 200, response.body)
                before = len(self.case.calls), len(self.case.wire.calls), self.case.state()["messages"]
                response = self.case.send("Og Lillehammer?", provider=provider, model=model)
                self.assertNotEqual(response.status, 200, response.body)
                self.assertEqual(json.loads(response.body).get("error_code"), "research_municipality_inactive")
                self.assertEqual((len(self.case.calls), len(self.case.wire.calls)), before[:2])
                self.assertEqual(self.case.state()["messages"], before[2])

    def test_v01c_english_municipal_fees_never_reach_unsourced_generation(self):
        questions = ("How much does a nursing home cost in Hamar?",
                     "What are the nursing home fees in Elverum?",
                     "What does home care cost in Gjøvik?",
                     "How much is after school care in Hamar?")
        for provider, model in PROVIDERS:
            for service in (None, self.live):
                self.case.backend.research_service = service
                for question in questions:
                    with self.subTest(provider=provider, live=service is not None, question=question):
                        self.case.clear()
                        response = self.case.send(question, provider=provider, model=model)
                        if self.case.calls:
                            self.assertEqual(response.status, 200, response.body)
                            reply = json.loads(response.body)["reply"]
                            self.assertTrue(reply.get("research_verified"), reply)
                            self.assertTrue(reply.get("source_receipts"), reply)
                            self.assertTrue(reply.get("citations"), reply)
                        else:
                            self.assertNotIn("250", json.dumps(self.case.state()["messages"]))

    def test_source_admission_is_not_limited_to_the_old_service_categories(self):
        # A controlled transport attempt is required; no real page or personal
        # contact is approved here, and successful answer generation is not assumed.
        questions = ("Hvilke barnehager finnes i Hamar?",
                     "Hvilke helsestasjoner finnes i Elverum?",
                     "Hva koster trygghetsalarm i Gjøvik?",
                     "Hvordan søker jeg om byggetillatelse i Hamar?",
                     "Hvilke svømmehaller finnes i Elverum?",
                     "Hva er søknadsfristen for startlån i Gjøvik?",
                     "Hvor finner jeg kommunens servicetorg i Hamar?")
        for provider, model in PROVIDERS:
            for question in questions:
                with self.subTest(provider=provider, question=question):
                    self.case.clear()
                    self.case.send(question, provider=provider, model=model)
                    self.assertTrue(self.case.wire.calls,
                                    "Enabled synthetic municipal discovery never attempted an official source")

    def test_scope_change_revokes_an_already_prepared_answer(self):
        with run_scope():
            binding = self.live.prepare("Hva koster SFO i Gjøvik?", provider="ollama",
                                        authorized=lambda: True, require_municipal=True)
            binding.assert_publishable()
            self.live.active_municipalities = frozenset(("hamar", "elverum"))
            with self.assertRaises(ResearchError):
                binding.assert_publishable()

    def test_http_payload_cannot_expand_the_backend_allowlist(self):
        self.case.clear()
        response = self.case.send("Hva koster SFO i Lillehammer?", provider="ollama",
                                  model="llama3.2:3b", active_municipalities=["lillehammer"])
        self.assertNotEqual(response.status, 200)
        self.assertEqual(self.case.calls, [])
        self.assertEqual(self.case.wire.calls, [])

    def test_disabled_source_chat_still_identifies_inactive_municipality(self):
        self.case.backend.research_service = None
        for provider, model in PROVIDERS:
            with self.subTest(provider=provider):
                self.case.clear()
                response = self.case.send("Hva koster SFO i Lillehammer?", provider=provider, model=model)
                payload = json.loads(response.body)
                self.assertEqual(payload.get("error_code"), "research_municipality_inactive", payload)
                self.assertEqual(self.case.calls, [])
                self.assertEqual(self.case.wire.calls, [])

    def test_municipal_api_lists_only_active_places_and_refuses_inactive_sources(self):
        from hamar_agent.real_sources import MunicipalWorkflowService
        from hamar_agent.search import SearchIndex
        from hamar_agent.web import WebApplication
        for provider, model in PROVIDERS:
            with self.subTest(provider=provider):
                client = Mock()
                client.config = SimpleNamespace(model=model)
                workflow = MunicipalWorkflowService(SearchIndex(), client, provider=provider,
                                                     request_sources=self.live)
                app = WebApplication(workflow)
                headers = self.case.headers(app.token)
                response = app.dispatch("GET", "/api/portal", headers, b"")
                self.assertEqual(response.status, 200, response.body)
                self.assertEqual({m["id"] for m in json.loads(response.body)["municipalities"]}, ACTIVE)
                for route in ("/api/search", "/api/answer"):
                    before = len(self.case.wire.calls)
                    response = app.dispatch("POST", route, headers,
                                            json.dumps({"query": "Hva koster SFO i Lillehammer?"}).encode())
                    self.assertNotEqual(response.status, 200, response.body)
                    self.assertEqual(json.loads(response.body).get("error_code"),
                                     "research_municipality_inactive", response.body)
                    self.assertEqual(len(self.case.wire.calls), before)
                client.generate.assert_not_called()
                client.summarize.assert_not_called()

    def test_malformed_active_policy_never_silently_restores_all_46(self):
        data = json.loads(POLICY.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-policy.json"
            for value in (None, [], ["hamar", "hamar"], ["not-in-roster"], "hamar"):
                with self.subTest(active=value):
                    altered = dict(data, active_municipalities=value)
                    path.write_text(json.dumps(altered), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_research_policy(path)


if __name__ == "__main__":
    unittest.main()
