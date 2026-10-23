"""Route and HTTP-wire tests without opening sockets or calling paid APIs."""
import io
import json
from pathlib import Path
from threading import Barrier, Event, Thread
import unittest
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
        self.assertIn("<h1>Aisha Agent</h1>", html)
        self.assertEqual(html.count("<h1>"), 1)
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

    def test_malformed_summary_does_not_create_a_result(self):
        self.app.service = WorkflowService(summarizer=MockSummarizer(MockScenario.MALFORMED_OUTPUT))
        self.assertEqual(self.run_source().status, 422)
        self.assertFalse(self.app.results)

    def test_result_memory_is_bounded(self):
        first = json.loads(self.run_source().body)["run_id"]
        for _ in range(16):
            self.run_source()
        self.assertEqual(len(self.app.results), 16)
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

    def test_expired_session_removes_its_saved_json_results(self):
        page = self.app.dispatch("GET", "/", self.headers).body
        token = page.split(b'name="hamar-token" content="', 1)[1].split(b'"', 1)[0].decode()
        headers = self.headers | {"X-Hamar-Token": token}
        answer = json.loads(self.app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}').body)
        run_id = answer["run_id"]
        self.app.sessions[token].last_seen -= 3 * 60 * 60
        self.assertEqual(self.app.dispatch("GET", "/api/results/" + run_id, headers).status, 403)
        self.assertNotIn(run_id, self.app.results)
