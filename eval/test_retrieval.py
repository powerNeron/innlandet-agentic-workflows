"""Synthetic HTTP transport tests. No real connections are permitted."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
from email.message import Message
import hashlib
from http.client import IncompleteRead
import io
import ssl
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, HTTPSHandler

from hamar_agent.retrieval import (
    HTTP_APPROVALS, MAX_RESPONSE_BYTES, HttpApproval, RetrievalError,
    _RejectRedirects, fetch_document,
)

TODAY = date(2026, 10, 21)
URL = "https://example.invalid/synthetic.txt"
BODY = "Fictional water data: not municipal information. \u00f8".encode("utf-8")


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        # Guard low-level connections even if the mocked opener is bypassed.
        self.socket = patch("socket.socket", side_effect=AssertionError("real network forbidden"))
        self.socket.start()
        self.addCleanup(self.socket.stop)
        self.connect = patch("socket.create_connection", side_effect=AssertionError("real network forbidden"))
        self.connect.start()
        self.addCleanup(self.connect.stop)
        self.approval = HttpApproval("synthetic-http", URL, "Synthetic test only", TODAY, TODAY)
        self.registry = {self.approval.source_id: self.approval}
        self.response = MagicMock()
        self.response.__enter__.return_value = self.response
        self.response.status = 200
        self.response.geturl.return_value = URL
        self.response.headers = Message()
        self.response.headers["Content-Type"] = "text/plain; charset=utf-8"
        self.response.read.side_effect = io.BytesIO(BODY).read
        self.builder = patch("hamar_agent.retrieval.build_opener")
        self.build = self.builder.start()
        self.addCleanup(self.builder.stop)
        self.opener = self.build.return_value
        self.opener.open.return_value = self.response

    def fetch(self):
        return fetch_document("synthetic-http", registry=self.registry, today=TODAY)

    def test_empty_production_registry_rejects_before_opener(self):
        self.assertEqual(dict(HTTP_APPROVALS), {})
        with self.assertRaises(RetrievalError):
            fetch_document("any-source")
        self.build.assert_not_called()
        with self.assertRaises(TypeError):
            HTTP_APPROVALS["x"] = self.approval

    def test_immutable_approval(self):
        with self.assertRaises(FrozenInstanceError):
            self.approval.url = URL

    def test_invalid_urls_rejected_before_network(self):
        urls = ["http://example.invalid/a", "file:///a", "https://user:pass@example.invalid/a",
                "https://example.invalid:443/a", "https://example.invalid/a?x=1",
                "https://example.invalid/a#part", "https://example.invalid/a?",
                "https://example.invalid/a#", "https://example.invalid/white space",
                "https://example.invalid/\npath", "https://example.invalid/a\\b",
                "https://127.0.0.1/a", "https://[::1]/a", "https://EXAMPLE.invalid/a",
                "https://example.invalid", "https://example.invalid/../a", "https://example.invalid/\u00f8"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                replace(self.approval, url=url)
        self.build.assert_not_called()

    def test_invalid_approval_metadata(self):
        changes = [dict(source_id=""), dict(rationale=" "), dict(sha256="bad"),
                   dict(reviewed_on="2026-10-21"), dict(expires_on=date(2026, 1, 1))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.approval, **change)

    def test_unknown_mismatched_and_expired_entries_never_open(self):
        registries = [{}, {"synthetic-http": replace(self.approval, source_id="other")},
                      {"synthetic-http": replace(self.approval, expires_on=date(2026, 10, 20), reviewed_on=date(2026, 10, 19))},
                      {"synthetic-http": replace(self.approval, reviewed_on=date(2026, 10, 22), expires_on=date(2026, 10, 23))}]
        for registry in registries:
            with self.subTest(registry=registry), self.assertRaises(RetrievalError):
                fetch_document("synthetic-http", registry=registry, today=TODAY)
        self.build.assert_not_called()

    def test_success_exact_url_timeout_tls_and_cleanup(self):
        result = self.fetch()
        self.assertEqual(result.text, BODY.decode("utf-8"))
        self.assertEqual(result.sha256, hashlib.sha256(BODY).hexdigest())
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(self.opener.open.call_args.kwargs, {"timeout": 10})
        handlers = self.build.call_args.args
        self.assertTrue(any(isinstance(h, _RejectRedirects) for h in handlers))
        self.assertEqual(next(h for h in handlers if isinstance(h, ProxyHandler)).proxies, {})
        context = next(h for h in handlers if isinstance(h, HTTPSHandler))._context
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.response.__exit__.assert_called_once()

    def test_all_redirects_refused_without_reading(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.response.status = status
                with self.assertRaises(RetrievalError):
                    self.fetch()
        self.response.read.assert_not_called()

    def test_redirect_handler_never_follows_even_same_domain(self):
        for destination in (URL, "https://other.invalid/target", "http://example.invalid/a"):
            with self.subTest(destination=destination):
                body = io.BytesIO(b"synthetic")
                with self.assertRaises(HTTPError) as raised:
                    _RejectRedirects().redirect_request(Request(URL), body, 302, "redirect", Message(), destination)
                raised.exception.close()
                self.assertTrue(body.closed)

    def test_changed_response_url_rejected(self):
        self.response.geturl.return_value = "https://other.invalid/document"
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.read.assert_not_called()
        self.response.__exit__.assert_called_once()

    def test_non_200_status_rejected(self):
        for status in (201, 204, 206, 404, 500):
            with self.subTest(status=status), self.assertRaises(RetrievalError):
                self.response.status = status
                self.fetch()
        self.response.read.assert_not_called()

    def test_missing_wrong_and_duplicate_content_types(self):
        for values in ([], ["text/html; charset=utf-8"], ["application/pdf"],
                       ["text/plain; charset=utf-8", "text/plain; charset=utf-8"]):
            self.response.headers = Message()
            for value in values:
                self.response.headers["Content-Type"] = value
            with self.subTest(values=values), self.assertRaises(RetrievalError):
                self.fetch()
        self.response.read.assert_not_called()

    def test_charset_must_be_explicit_utf8(self):
        for value in ("text/plain", "text/plain; charset=latin-1"):
            self.response.headers.replace_header("Content-Type", value)
            with self.subTest(value=value), self.assertRaises(RetrievalError):
                self.fetch()
        self.response.read.assert_not_called()

    def test_compression_rejected(self):
        self.response.headers["Content-Encoding"] = "gzip"
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.read.assert_not_called()

    def test_declared_oversize_rejected_before_read(self):
        self.response.headers["Content-Length"] = str(MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.read.assert_not_called()

    def test_invalid_and_duplicate_lengths_rejected(self):
        for values in (["-1"], ["garbage"], ["1", "1"]):
            if "Content-Length" in self.response.headers:
                del self.response.headers["Content-Length"]
            for value in values:
                self.response.headers["Content-Length"] = value
            with self.subTest(values=values), self.assertRaises(RetrievalError):
                self.fetch()
        self.response.read.assert_not_called()

    def test_stream_size_limit_with_and_without_length(self):
        for length in (None, "1"):
            self.response.read.side_effect = io.BytesIO(b"a" * (MAX_RESPONSE_BYTES + 1)).read
            if length is not None:
                self.response.headers["Content-Length"] = length
            with self.subTest(length=length), self.assertRaises(RetrievalError):
                self.fetch()

    def test_exact_limit_allowed(self):
        raw = b"a" * MAX_RESPONSE_BYTES
        self.response.read.side_effect = io.BytesIO(raw).read
        self.response.headers["Content-Length"] = str(len(raw))
        self.assertEqual(len(self.fetch().text), MAX_RESPONSE_BYTES)

    def test_declared_length_mismatch_rejected(self):
        self.response.headers["Content-Length"] = str(len(BODY) + 1)
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.__exit__.assert_called_once()

    def test_matching_hash_accepted(self):
        self.registry["synthetic-http"] = replace(self.approval, sha256=hashlib.sha256(BODY).hexdigest())
        self.assertEqual(self.fetch().text, BODY.decode())

    def test_wrong_hash_rejected_and_response_closed(self):
        self.registry["synthetic-http"] = replace(self.approval, sha256="0" * 64)
        with self.assertRaisesRegex(RetrievalError, "integrity"):
            self.fetch()
        self.response.__exit__.assert_called_once()

    def test_invalid_utf8_rejected_and_response_closed(self):
        self.response.read.side_effect = io.BytesIO(b"\xff").read
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.__exit__.assert_called_once()

    def test_timeout_tls_and_network_errors_are_sanitized(self):
        for error in (TimeoutError("secret body"), ssl.SSLError("secret body"),
                      URLError("secret body"), ConnectionError("secret body")):
            self.opener.open.side_effect = error
            with self.subTest(error=error), self.assertRaises(RetrievalError) as raised:
                self.fetch()
            self.assertNotIn("secret body", str(raised.exception))

    def test_read_failure_closes_response(self):
        self.response.read.side_effect = TimeoutError("synthetic timeout")
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.__exit__.assert_called_once()

    def test_http_error_body_is_closed_without_reading(self):
        body = io.BytesIO(b"synthetic error response")
        self.opener.open.side_effect = HTTPError(URL, 302, "redirect", Message(), body)
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.assertTrue(body.closed)
        self.opener.open.assert_called_once()

    def test_incomplete_read_is_sanitized_and_closed(self):
        self.response.read.side_effect = IncompleteRead(b"synthetic partial response")
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.__exit__.assert_called_once()

    def test_duplicate_charset_is_rejected(self):
        self.response.headers.replace_header("Content-Type", "text/plain; charset=utf-8; charset=latin-1")
        with self.assertRaises(RetrievalError):
            self.fetch()
        self.response.read.assert_not_called()
