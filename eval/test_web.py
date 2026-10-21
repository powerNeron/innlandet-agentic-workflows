"""Route and HTTP-wire tests without opening sockets or calling paid APIs."""
import io
import json
from pathlib import Path
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
        self.assertIn(self.app.token.encode(), page.body)
        self.assertIn(b"Hamar KommuneAgent", page.body)
        self.assertNotIn(b"{{TOKEN}}", page.body)
        for path in ("/app.js", "/style.css"):
            with self.subTest(path=path):
                self.assertEqual(self.app.dispatch("GET", path, self.headers).status, 200)

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
