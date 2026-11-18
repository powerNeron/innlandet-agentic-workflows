"""Route and HTTP-wire tests without opening sockets or calling paid APIs."""
import io
import json
import subprocess
from pathlib import Path
from threading import Barrier, Event, Thread
import unittest
from html.parser import HTMLParser
from unittest.mock import Mock, patch

from hamar_agent.application import WorkflowService
from hamar_agent.summarize import MockScenario, MockSummarizer
from hamar_agent.web import MAX_REQUEST_BYTES, WebApplication, create_server, make_handler

SOURCE_ID = "synthetic-verification-demo"


class FakeConnection:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.output = io.BytesIO()
        self.timeout = None

    def makefile(self, mode, *args):
        return self.request

    def sendall(self, data):
        self.output.write(data)

    def settimeout(self, value):
        self.timeout = value


class WebTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("network/paid APIs forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.app = WebApplication()
        self.headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:8000",
                        "Content-Type": "application/json", "X-Hamar-Token": self.app.token}

    def run_source(self, source_id=SOURCE_ID):
        return self.app.dispatch("POST", "/api/run", self.headers, json.dumps({"source_id": source_id}).encode())

    def test_actual_insufficient_evidence_api_response_uses_public_message_without_indexing_jargon(self):
        from hamar_agent.portal import PortalService
        from hamar_agent.search import SearchIndex
        summarizer=Mock(side_effect=AssertionError('Insufficient sources must not call a model'))
        service=WorkflowService(summarizer=summarizer)
        app=WebApplication(service,portal=PortalService(service,index=SearchIndex()))
        headers={**self.headers,'X-Hamar-Token':app.token}
        response=app.dispatch('POST','/api/answer',headers,b'{"query":"vann"}')
        self.assertEqual(response.status,200)
        payload=json.loads(response.body)
        self.assertEqual(payload['answer']['answer_status'],'insufficient_evidence')
        self.assertIsNone(payload['answer']['result'])
        self.assertIn('indeksert',payload['answer']['message'].casefold())  # Real backend wording remains unchanged.
        original=response.body
        root=Path(__file__).resolve().parents[1]
        try:
            rendered=subprocess.run(['node',str(root/'harness/browser_smoke.cjs'),'--render-api-answer'],
                input=response.body.decode('utf-8'),cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=15)
        except FileNotFoundError:
            self.skipTest('Node unavailable; actual-JS rendering regression requires the existing Node runtime')
        self.assertEqual(rendered.returncode,0,rendered.stdout+rendered.stderr)
        view=json.loads(rendered.stdout)
        self.assertNotIn('indeksert',view['text'].casefold())
        self.assertIn('Vi fant ikke nok informasjon til å svare. Prøv et annet spørsmål eller se kommunens nettside.',view['text'])
        self.assertFalse(view['has_claim']);self.assertEqual(view['generation_requests'],0)
        self.assertTrue(view['initial_hidden']);self.assertFalse(view['panel_hidden'])
        self.assertIn('https://www.hamar.kommune.no/meny/',view['links'])
        self.assertTrue(view['payload_unchanged']);self.assertEqual(response.body,original)
        self.assertNotIn('indeksert',app.dispatch('GET','/',headers).body.decode('utf-8').casefold())
        summarizer.summarize.assert_not_called()

    def test_initial_answer_panel_is_hidden_without_empty_waiting_text(self):
        from html.parser import HTMLParser
        class Elements(HTMLParser):
            def handle_starttag(parser,tag,attributes):
                if dict(attributes).get('id')=='ai-result':parser.panel=dict(attributes)
        html=self.app.dispatch('GET','/',self.headers).body.decode('utf-8')
        parsed=Elements();parsed.feed(html)
        self.assertIn('hidden',parsed.panel)
        self.assertLess(html.index('id="reset-conversation"'),html.index('id="ai-result"'))
        self.assertNotIn('Venter på spørsmål',html)
        self.assertIn('id="answer-content" aria-live="polite"',html)

    def wire(self, raw):
        conn = FakeConnection(raw)
        make_handler(self.app)(conn, ("127.0.0.1", 12345), Mock())
        head, body = conn.output.getvalue().split(b"\r\n\r\n", 1)
        return head.decode("iso-8859-1"), body

    def test_page_and_static_assets(self):
        page = self.app.dispatch("GET", "/", self.headers)
        self.assertEqual(page.status, 200)
        page_token = page.body.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0]
        self.assertTrue(page_token)
        self.assertNotEqual(page_token.decode(), self.app.token)
        self.assertIsNotNone(self.app._session(page_token.decode()))
        self.assertIn(b"<title>Aisha Agent</title>", page.body)
        self.assertNotIn(b"KommuneAgent", page.body)
        html = page.body.decode("utf-8")
        self.assertIn('<h1 id="municipal-title">Aisha Agent</h1>', html)
        self.assertIn('<h1 id="chat-title">Hei, jeg er Aisha</h1>', html)
        self.assertEqual(html.count('<h1 '), 2)  # One per mutually exclusive mode.
        self.assertIn('id="municipal-mode" role="region" aria-labelledby="municipal-title" hidden', html)
        self.assertIn('<h2 id="categories-title" tabindex="-1">Hvordan kan vi hjelpe deg?</h2>',html)
        self.assertIn('href="https://www.hamar.kommune.no/meny/" target="_blank" rel="noopener noreferrer">Kommunens tjenestemeny',html)
        self.assertNotIn('<h2>Hva kan jeg hjelpe deg med?</h2>',html)
        self.assertIn('Spør meg om det du lurer på! Jeg kan hjelpe deg med spørsmål, læring og praktiske oppgaver.',html)
        self.assertIn('id="municipal-model-choices" class="model-choices" role="group"',html)
        self.assertIn('id="chat-model-choices" class="model-choices" role="group"',html)
        self.assertIn('id="provider-model" hidden',html)
        self.assertIn('<p class="eyebrow">Svar fra Aisha</p>',html)
        self.assertIn('<p id="answer-help">Kildene vises sammen med svaret.</p>',html)
        hero = html.split('<section class="hero glass">', 1)[1].split('<form id="search-form"', 1)[0]
        expected_hero = ("Aisha Agent", "Din AI-guide til informasjon og kommunale tjenester i Hamar.",
                         "Hva kan vi hjelpe deg med?", "Søk etter informasjon om Hamar og kommunale tjenester.")
        positions = [hero.index(text) for text in expected_hero]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('<h2 class="hero-question">Hva kan vi hjelpe deg med?</h2>', hero)
        self.assertIn("Din AI-guide til informasjon og kommunale tjenester i Hamar.", html)
        self.assertIn("Søk etter informasjon om Hamar og kommunale tjenester.", html)
        self.assertLess(html.index('id="about-service"'), html.index('id="about-project"'))
        project = html.split('<details id="about-project"', 1)[1].split("</details>", 1)[0]
        self.assertNotRegex(project.split(">", 1)[0], r"\bopen\b")
        self.assertIn("KIUA-2003 – Aisha Agent", project)
        self.assertIn("Prosjektets læringsmål", project)
        self.assertIn("Dette er et studentprosjekt og ikke en offisiell tjeneste fra Hamar kommune.", project)
        for removed_id in ("portal-download", "download", "source", "run", "result", "json"):
            self.assertNotIn(f'id="{removed_id}"'.encode(), page.body)
        self.assertNotIn(b'class="developer', page.body)
        self.assertNotIn(b"{{TOKEN}}", page.body)
        self.assertIn(b'<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon">', page.body)
        for path in ("/app.js", "/style.css"):
            with self.subTest(path=path):
                self.assertEqual(self.app.dispatch("GET", path, self.headers).status, 200)

    def test_favicon_is_served_as_a_valid_ico_asset(self):
        response = self.app.dispatch("GET", "/favicon.ico", self.headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/vnd.microsoft.icon")
        self.assertTrue(response.body.startswith(b"\x00\x00\x01\x00"))

    def test_independent_search_and_ai_forms_are_present(self):
        html = self.app.dispatch("GET", "/", self.headers).body.decode("utf-8")
        search_form = html.split('<form id="search-form"', 1)[1].split("</form>", 1)[0]
        ai_form = html.split('<form id="ai-form"', 1)[1].split("</form>", 1)[0]
        search_section = html.split('<section id="search-area"', 1)[1].split("</section>", 1)[0]
        self.assertIn('id="query"', search_form)
        self.assertNotIn("/api/answer", search_section)
        self.assertIn('id="ai-query"', ai_form)
        self.assertIn("Sp\u00f8r Aisha", ai_form)
        self.assertIn('id="answer-content"', html)

    def test_ai_answer_route_runs_without_a_prior_search_and_downloads_its_own_result(self):
        query = b'{"query":"vann"}'
        answer_response = self.app.dispatch("POST", "/api/answer", self.headers, query)
        self.assertEqual(answer_response.status, 200)
        answer = json.loads(answer_response.body)
        self.assertEqual(answer["answer"]["answer_status"], "demo")
        self.assertTrue(answer["answer"]["citations"])
        download = self.app.dispatch("GET", "/api/results/" + answer["run_id"], self.headers)
        self.assertEqual(json.loads(download.body), answer["answer"])

    def test_search_and_ai_answer_are_independent_requests(self):
        search = self.app.dispatch("POST", "/api/search", self.headers, b'{"query":"vann"}')
        answer = self.app.dispatch("POST", "/api/answer", self.headers, b'{"query":"bibliotek"}')
        self.assertEqual(search.status, 200)
        self.assertEqual(answer.status, 200)
        self.assertNotEqual(json.loads(search.body)["results"][0]["source_id"],
                            json.loads(answer.body)["answer"]["citations"][0]["source_id"])

    def test_source_list_contains_only_approved_fixtures(self):
        data = json.loads(self.app.dispatch("GET", "/api/sources", self.headers).body)
        self.assertEqual({s["id"] for s in data["sources"]}, {SOURCE_ID, "synthetic-water-demo"})
        self.assertFalse(data["external_retrieval"])
        self.assertEqual(data["provider"], "mock")

    def test_run_download_is_exact_verified_result(self):
        response = self.run_source()
        self.assertEqual(response.status, 200)
        data = json.loads(response.body)
        self.assertTrue(all(c["evidence_status"] == "exact_match" for c in data["result"]["claims"]))
        downloaded = self.app.dispatch("GET", "/api/results/" + data["run_id"], self.headers)
        self.assertTrue(downloaded.download)
        self.assertEqual(json.loads(downloaded.body), data["result"])
        self.assertEqual(json.loads(downloaded.body), json.loads(self.app.service.run(SOURCE_ID).to_json()))

    def test_ui_findings_and_original_correction_history_survive(self):
        self.app.service = WorkflowService(summarizer=MockSummarizer(MockScenario.CHANGED_NUMBER))
        result = json.loads(self.run_source().body)["result"]
        self.assertEqual(result["verification"]["findings"][0]["code"], "unsupported_number")
        self.assertTrue(result["correction"]["initial_findings"])

    def test_unknown_source_and_url_rejected_without_provider_call(self):
        self.app.service.summarizer = Mock(side_effect=AssertionError("must not run"))
        for source in ("unknown", "https://example.invalid/document"):
            self.assertEqual(self.run_source(source).status, 400)
        self.app.service.summarizer.summarize.assert_not_called()
        self.assertFalse(self.app.results)

    def test_bad_json_and_extra_options_cannot_enable_http(self):
        for value in (b"{", b"[]", b'{}', b'null', b'"source"',
                      b'{"source_id":123}', b'{"source_id":"x","enable_http":true}'):
            with self.subTest(value=value):
                self.assertEqual(self.app.dispatch("POST", "/api/run", self.headers, value).status, 400)
        self.assertFalse(self.app.service.enable_http)

    def test_request_size_and_content_type_limits(self):
        self.assertEqual(self.app.dispatch("POST", "/api/run", self.headers, b"a" * (MAX_REQUEST_BYTES + 1)).status, 413)
        self.headers["Content-Type"] = "text/plain"
        self.assertEqual(self.run_source().status, 415)

    def test_host_and_origin_rebinding_controls(self):
        for key, value in (("Host", "evil.invalid:8000"), ("Host", "127.0.0.1.evil.invalid:8000"),
                           ("Origin", "https://evil.invalid"), ("Origin", "null")):
            headers = self.headers | {key: value}
            with self.subTest(key=key, value=value):
                self.assertEqual(self.app.dispatch("POST", "/api/run", headers, b"{}").status, 403)

    def test_token_required_for_runs_and_downloads(self):
        headers = self.headers | {"X-Hamar-Token": "wrong"}
        self.assertEqual(self.app.dispatch("POST", "/api/run", headers, b"{}").status, 403)
        self.assertEqual(self.app.dispatch("GET", "/api/results/x", headers).status, 403)

    def test_expired_download_and_path_traversal(self):
        self.assertEqual(self.app.dispatch("GET", "/api/results/missing", self.headers).status, 404)
        for path in ("/../AGENTS.md", "/api/run?url=x", "/hamar_agent/schemas.py"):
            self.assertEqual(self.app.dispatch("GET", path, self.headers).status, 404)

    def test_backend_errors_are_sanitized(self):
        self.app.service.run = Mock(side_effect=RuntimeError("secret adapter details"))
        response = self.run_source()
        self.assertEqual(response.status, 422)
        self.assertNotIn(b"secret adapter details", response.body)
        self.assertFalse(self.app.results)

    def test_page_accessibility_references_and_recovery_controls_are_well_formed(self):
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__(); self.elements = []
            def handle_starttag(self, tag, attrs):
                self.elements.append((tag, dict(attrs)))
        page = self.app.dispatch("GET", "/", self.headers).body.decode()
        parser = Elements(); parser.feed(page)
        identified = [attrs['id'] for tag, attrs in parser.elements if 'id' in attrs]
        self.assertEqual(len(identified), len(set(identified)))
        for tag, attrs in parser.elements:
            for reference in attrs.get('aria-describedby', '').split():
                self.assertIn(reference, identified)
            if tag == 'label' and 'for' in attrs:
                self.assertIn(attrs['for'], identified)
        controls = {attrs.get('id'): (tag, attrs) for tag, attrs in parser.elements}
        for name in ('refresh-providers', 'retry-answer', 'reset-conversation'):
            self.assertEqual(controls[name][0], 'button')
            self.assertEqual(controls[name][1]['type'], 'button')
        self.assertIn('hidden', controls['retry-answer'][1])
        self.assertLess(page.index('id="privacy"'), page.index('id="about-service"'))

    def test_unknown_provider_diagnostics_are_not_exposed_or_saved(self):
        from hamar_agent.real_sources import RealSourceError
        self.app.portal.answer = Mock(side_effect=RealSourceError('synthetic-secret', code='synthetic-secret'))
        response = self.app.dispatch('POST', '/api/answer', self.headers, b'{"query":"vann"}')
        self.assertEqual(response.status, 422)
        self.assertEqual(json.loads(response.body)['error_code'], 'workflow_failed')
        self.assertNotIn(b'synthetic-secret', response.body)
        self.assertFalse(self.app.results)

    def test_provider_cleanup_failure_cannot_leak_diagnostics(self):
        from hamar_agent.provider_registry import ProviderRegistry
        from hamar_agent.openai_provider import OpenAIConfig
        registry = ProviderRegistry(ollama_models=lambda: (), openai_config_factory=OpenAIConfig,
            sdk_available=lambda: False, include_mock=True)
        service = WorkflowService()
        service.close = Mock(side_effect=KeyError('synthetic-secret'))
        app = WebApplication(provider_registry=registry, service_factory=lambda *args: service)
        headers = {**self.headers, 'X-Hamar-Token': app.token}
        response = app.dispatch('POST', '/api/answer', headers,
            b'{"query":"vann","provider":"mock","model":"mock"}')
        self.assertEqual(response.status, 200)
        self.assertNotIn(b'synthetic-secret', response.body)
        self.assertEqual(json.loads(response.body)['answer']['answer_status'], 'demo')
        service.close.assert_called_once()

    def test_registry_free_selection_only_reuses_the_configured_service(self):
        for provider, model, processing in (('mock', 'mock', 'local'), ('ollama', 'synthetic-local', 'local'),
                                             ('openai', 'synthetic-cloud', 'external')):
            with self.subTest(provider=provider):
                name = provider if provider == 'mock' else provider + ':' + model
                service = WorkflowService(provider=name, summarizer=MockSummarizer())
                app = WebApplication(service=service)
                headers = self.headers | {'X-Hamar-Token': app.token}
                choice, = json.loads(app.dispatch('GET', '/api/providers', headers).body)['choices']
                self.assertEqual((choice['provider'], choice['model'], choice['processing']), (provider, model, processing))
                self.assertTrue(choice['available'])
                self.assertFalse(choice['generation_verified'])
                self.assertEqual(choice['connection_status'], 'not_applicable' if provider == 'mock' else 'not_checked')
                original_answer = app.portal.answer
                app.portal.answer = Mock(wraps=original_answer)
                response = app.dispatch('POST', '/api/answer', headers,
                    json.dumps({'query': 'vann', 'provider': provider, 'model': model}).encode())
                self.assertEqual(response.status, 200)
                self.assertIs(app.portal.answer.call_args.kwargs['workflow_service'], service)
                calls, results = app.portal.answer.call_count, len(app.results)
                for selection in ({'provider': provider, 'model': 'unconfigured'}, {'provider': 'other', 'model': model}, {'provider': provider}):
                    rejected = app.dispatch('POST', '/api/answer', headers, json.dumps({'query': 'vann', **selection}).encode())
                    self.assertEqual(rejected.status, 400)
                self.assertEqual(app.portal.answer.call_count, calls)
                self.assertEqual(len(app.results), results)
        for name in ('ollama', 'openai'):
            app = WebApplication(service=WorkflowService(provider=name))
            choice, = json.loads(app.dispatch('GET', '/api/providers', self.headers).body)['choices']
            self.assertFalse(choice['available'])
            self.assertEqual(choice['model'], '')

    def test_cleanup_lookup_failure_preserves_primary_error_and_interrupts_propagate(self):
        from hamar_agent.provider_registry import ProviderRegistry
        from hamar_agent.openai_provider import OpenAIConfig, OpenAIProviderError
        class LookupFailure(WorkflowService):
            @property
            def close(self):
                raise KeyError('synthetic-secret-lookup')
        registry = ProviderRegistry(ollama_models=lambda: (), openai_config_factory=OpenAIConfig,
            sdk_available=lambda: False, include_mock=True)
        for failure in (None, OpenAIProviderError('synthetic-secret-primary', code='provider_authentication')):
            with self.subTest(primary_failure=bool(failure)):
                app = WebApplication(provider_registry=registry, service_factory=lambda *args: LookupFailure())
                if failure:
                    app.portal.answer = Mock(side_effect=failure)
                headers = self.headers | {'X-Hamar-Token': app.token}
                response = app.dispatch('POST', '/api/answer', headers, b'{"query":"vann","provider":"mock","model":"mock"}')
                self.assertEqual(response.status, 422 if failure else 200)
                self.assertNotIn(b'synthetic-secret', response.body)
                if failure:
                    self.assertEqual(json.loads(response.body)['error_code'], 'provider_authentication')
                    self.assertFalse(app.results)
        service = WorkflowService()
        service.close = Mock(side_effect=KeyboardInterrupt())
        app = WebApplication(provider_registry=registry, service_factory=lambda *args: service)
        with self.assertRaises(KeyboardInterrupt):
            app.dispatch('POST', '/api/answer', self.headers | {'X-Hamar-Token': app.token},
                b'{"query":"vann","provider":"mock","model":"mock"}')

    def test_malformed_summary_does_not_create_a_result(self):
        self.app.service = WorkflowService(summarizer=MockSummarizer(MockScenario.MALFORMED_OUTPUT))
        self.assertEqual(self.run_source().status, 422)
        self.assertFalse(self.app.results)

    def test_result_memory_is_bounded(self):
        first = json.loads(self.run_source().body)["run_id"]
        for _ in range(16):
            self.run_source()
        self.assertEqual(len(self.app.results), 16)
        self.assertEqual(set(self.app.result_owners), set(self.app.results))
        self.assertEqual(self.app.dispatch("GET", "/api/results/" + first, self.headers).status, 404)

    def test_actual_http_handler_parses_run_and_sets_security_headers(self):
        body = json.dumps({"source_id": SOURCE_ID}).encode()
        raw = (f"POST /api/run HTTP/1.0\r\nHost: 127.0.0.1:8000\r\nOrigin: http://127.0.0.1:8000\r\n"
               f"X-Hamar-Token: {self.app.token}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body
        head, payload = self.wire(raw)
        self.assertIn("200 OK", head)
        self.assertIn("Cache-Control: no-store", head)
        self.assertIn("Content-Security-Policy", head)
        self.assertEqual(json.loads(payload)["result"]["source"]["id"], SOURCE_ID)

    def test_http_handler_download_content_disposition(self):
        run_id = json.loads(self.run_source().body)["run_id"]
        head, payload = self.wire((f"GET /api/results/{run_id} HTTP/1.0\r\nHost: 127.0.0.1:8000\r\nX-Hamar-Token: {self.app.token}\r\n\r\n").encode())
        self.assertIn("attachment; filename=", head)
        self.assertEqual(json.loads(payload)["source"]["id"], SOURCE_ID)

    def test_http_framing_rejects_duplicates_truncation_and_transfer_encoding(self):
        frames = ["Content-Length: 0\r\nContent-Length: 0", "Content-Length: -1",
                  "Content-Length: 8193", "Content-Length: x", "Transfer-Encoding: chunked", "Content-Length: 5"]
        for frame in frames:
            with self.subTest(frame=frame):
                head, body = self.wire(("POST /api/run HTTP/1.0\r\nHost: 127.0.0.1:8000\r\n" + frame + "\r\n\r\n").encode())
                self.assertNotIn("200 OK", head)
                self.assertIn("error", json.loads(body))

    def test_server_factory_always_binds_loopback(self):
        with patch("hamar_agent.web.ThreadingHTTPServer") as server:
            server.return_value.server_port = 8001
            create_server(port=8001)
            self.assertEqual(server.call_args.args[0], ("127.0.0.1", 8001))

    def test_unsupported_http_method_returns_405(self):
        head, _ = self.wire(b"DELETE /api/run HTTP/1.0\r\nHost: 127.0.0.1:8000\r\n\r\n")
        self.assertIn("405 Method Not Allowed", head)

    def test_non_ascii_token_is_rejected_without_crashing(self):
        headers = self.headers | {"X-Hamar-Token": "\u00f8"}
        self.assertEqual(self.app.dispatch("POST", "/api/run", headers, b"{}").status, 403)

    def test_each_page_receives_an_isolated_session_token(self):
        first = self.app.dispatch("GET", "/", self.headers).body
        second = self.app.dispatch("GET", "/", self.headers).body
        first_token = first.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0]
        second_token = second.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0]
        self.assertNotEqual(first_token, second_token)
        self.assertIsNotNone(self.app._session(first_token.decode()))
        self.assertIsNotNone(self.app._session(second_token.decode()))

    def test_followup_uses_only_session_topic_terms_and_reset_clears_them(self):
        first = self.app.dispatch("POST", "/api/answer", self.headers, b'{"query":"vann"}')
        self.assertEqual(first.status, 200)
        followup = self.app.dispatch("POST", "/api/answer", self.headers, b'{"query":"hva med priser?"}')
        self.assertEqual(followup.status, 200)
        self.assertTrue(json.loads(followup.body)["answer"]["is_follow_up"])
        reset = self.app.dispatch("POST", "/api/conversation/reset", self.headers, b"{}")
        self.assertEqual(reset.status, 200)
        no_context = self.app.dispatch("POST", "/api/answer", self.headers, b'{"query":"hva med priser?"}')
        self.assertEqual(no_context.status, 200)
        no_context_answer = json.loads(no_context.body)["answer"]
        self.assertEqual(no_context_answer["answer_status"], "clarification_required")
        self.assertFalse(no_context_answer["is_follow_up"])
        self.assertEqual(no_context_answer["official_menu_url"], "https://www.hamar.kommune.no/meny/")

    def test_followup_cannot_use_another_page_session_context(self):
        first_page = self.app.dispatch("GET", "/", self.headers).body
        other_page = self.app.dispatch("GET", "/", self.headers).body
        tokens = [page.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0].decode()
                  for page in (first_page, other_page)]
        first_headers = self.headers | {"X-Hamar-Token": tokens[0]}
        second_headers = self.headers | {"X-Hamar-Token": tokens[1]}
        self.assertEqual(self.app.dispatch("POST", "/api/answer", first_headers, b'{"query":"vann"}').status, 200)
        second = self.app.dispatch("POST", "/api/answer", second_headers, b'{"query":"hva med priser?"}')
        self.assertEqual(second.status, 200)
        second_answer = json.loads(second.body)["answer"]
        self.assertEqual(second_answer["answer_status"], "clarification_required")
        self.assertFalse(second_answer["is_follow_up"])
        self.assertEqual(second_answer["official_menu_url"], "https://www.hamar.kommune.no/meny/")

    def test_concurrent_sessions_keep_followup_context_isolated(self):
        page_tokens = []
        for _ in range(2):
            page = self.app.dispatch("GET", "/", self.headers).body
            page_tokens.append(page.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0].decode())
        rendezvous = Barrier(2)
        original = self.app.portal.answer
        def concurrent_answer(*args, **kwargs):
            rendezvous.wait(timeout=2)
            return original(*args, **kwargs)
        self.app.portal.answer = concurrent_answer
        queries = ("vann", "bibliotek")
        responses = [None, None]
        def run(index):
            headers = self.headers | {"X-Hamar-Token": page_tokens[index]}
            responses[index] = self.app.dispatch("POST", "/api/answer", headers,
                json.dumps({"query": queries[index]}).encode())
        workers = [Thread(target=run, args=(i,)) for i in range(2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(3)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual([response.status for response in responses], [200, 200])
        self.assertTrue(all(json.loads(response.body)["answer"]["result"] for response in responses))
        self.assertIn("vann", self.app.sessions[page_tokens[0]].topic_terms)
        self.assertIn("bibliotek", self.app.sessions[page_tokens[1]].topic_terms)
        self.assertNotIn("bibliotek", self.app.sessions[page_tokens[0]].topic_terms)
        self.assertNotIn("vann", self.app.sessions[page_tokens[1]].topic_terms)

    def test_reset_during_inference_rejects_stale_conversation_update(self):
        entered, release = Event(), Event()
        original = self.app.portal.answer
        def blocked(*args, **kwargs):
            entered.set(); release.wait(2)
            return original(*args, **kwargs)
        self.app.portal.answer = blocked
        response_box = []
        worker = Thread(target=lambda: response_box.append(
            self.app.dispatch("POST", "/api/answer", self.headers, b'{"query":"vann"}')))
        worker.start()
        self.assertTrue(entered.wait(1))
        self.assertEqual(self.app.dispatch("POST", "/api/conversation/reset", self.headers, b"{}").status, 200)
        release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(response_box[0].status, 409)
        self.assertFalse(self.app.results)

    def test_reset_or_expiry_at_publication_cannot_save_an_answer_or_run(self):
        # Pause at ID allocation after inference, rather than relying on sleeps.
        for route, body in (('/api/answer', b'{"query":"vann"}'),
                            ('/api/run', json.dumps({'source_id': SOURCE_ID}).encode())):
            for invalidation in ('reset', 'expiry', 'expired_registered'):
                with self.subTest(route=route, invalidation=invalidation):
                    app = WebApplication()
                    headers = self.headers | {'X-Hamar-Token': app.token}
                    entered, release = Event(), Event()
                    responses, errors = [], []
                    def delayed_id(*args):
                        entered.set()
                        if not release.wait(3):
                            raise RuntimeError('Synthetic publication barrier timed out')
                        return 'synthetic-race-result'
                    def request():
                        try:
                            responses.append(app.dispatch('POST', route, headers, body))
                        except Exception as error:
                            errors.append(type(error).__name__)
                    with patch('hamar_agent.web.secrets.token_hex', side_effect=delayed_id):
                        worker = Thread(target=request)
                        worker.start()
                        try:
                            self.assertTrue(entered.wait(2), errors)
                            if invalidation == 'reset':
                                self.assertEqual(app.dispatch('POST', '/api/conversation/reset', headers, b'{}').status, 200)
                            else:
                                app.sessions[app.token].last_seen -= 3 * 60 * 60
                                if invalidation == 'expiry':
                                    self.assertEqual(app.dispatch('GET', '/api/results/missing', headers).status, 403)
                        finally:
                            release.set()
                            worker.join(3)
                    self.assertFalse(worker.is_alive())
                    self.assertFalse(errors)
                    self.assertEqual(responses[0].status, 409)
                    self.assertFalse(app.results)
                    self.assertFalse(app.result_owners)
                    if invalidation == 'reset':
                        self.assertEqual(app.sessions[app.token].topic_terms, ())
                        self.assertEqual(app.sessions[app.token].turns, 0)
                    if invalidation == 'expired_registered':
                        self.assertIn(app.token, app.sessions)
                    self.assertNotEqual(app.dispatch('GET', '/api/results/synthetic-race-result', headers).status, 200)

    def test_expired_session_removes_its_saved_json_results(self):
        page = self.app.dispatch("GET", "/", self.headers).body
        token = page.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0].decode()
        headers = self.headers | {"X-Hamar-Token": token}
        answer = json.loads(self.app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}').body)
        run_id = answer["run_id"]
        self.app.sessions[token].last_seen -= 3 * 60 * 60
        self.assertEqual(self.app.dispatch("GET", "/api/results/" + run_id, headers).status, 403)
        self.assertNotIn(run_id, self.app.results)


class RegionalStartupTests(unittest.TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        self.directory=TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'synthetic-policy.json'
        from eval.test_research import complete_policy_fixture
        self.path.write_text(json.dumps(complete_policy_fixture()),encoding='utf-8')
        for name in ('socket.socket','socket.getaddrinfo'):
            guard=patch(name,side_effect=AssertionError('Startup test forbids network'))
            guard.start();self.addCleanup(guard.stop)

    def test_shared_policy_survives_startup_and_provider_model_switches(self):
        from contextlib import contextmanager,redirect_stdout
        from types import SimpleNamespace
        from hamar_agent.real_sources import MunicipalWorkflowService
        from hamar_agent.search import SearchIndex
        from hamar_agent.web import main
        captured={}
        def service(*args,model=None,provider='ollama',request_sources=None,**kwargs):
            client=SimpleNamespace(config=SimpleNamespace(model=model or 'llama3.2:3b'))
            return MunicipalWorkflowService(SearchIndex(),client,provider=provider,request_sources=request_sources)
        @contextmanager
        def server(**kwargs):
            captured.update(kwargs)
            def stop():raise KeyboardInterrupt
            yield SimpleNamespace(server_port=8000,serve_forever=stop)
        for live,local_router in ((False,False),(True,False),(True,True)):
            args=['--research-policy',str(self.path),'--provider','ollama']+(['--enable-live-research'] if live else [])
            if local_router:args+=['--enable-local-router','--router-model','llama3.2:3b']
            with patch('hamar_agent.real_sources.create_municipal_service',side_effect=service), \
                    patch('hamar_agent.web.create_server',side_effect=server),redirect_stdout(io.StringIO()):
                self.assertEqual(main(args),0)
            policy=captured['chat_backend'].research_service
            self.assertIs(captured['service'].request_sources,policy)
            self.assertIsNone(policy.fetcher);self.assertEqual(policy.configured(),live)
            self.assertEqual(captured['chat_backend'].search_allowed(),live)
            self.assertEqual(captured['chat_backend'].question_router.classifier is not None,local_router)
            self.assertEqual(captured['chat_backend'].policy().max_calls,2 if local_router else 1)
            for provider,model in (('ollama','llama3.2:3b'),('openai','gpt-4.1-mini')):
                switched=captured['service_factory'](provider,model)
                self.assertIs(switched.request_sources,policy)
                self.assertEqual(switched.provider,provider+':'+model)

    def test_bad_policy_and_demo_combination_fail_before_provider_setup(self):
        from contextlib import redirect_stderr
        from hamar_agent.web import main
        for args in (['--demo','--research-policy',str(self.path)],
                     ['--demo','--enable-live-research'],
                     ['--research-policy',str(self.path)+'.missing']):
            with patch('hamar_agent.real_sources.create_municipal_service') as factory, \
                    redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as stop:
                main(args)
            self.assertEqual(stop.exception.code,2);factory.assert_not_called()
