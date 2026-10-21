"""Reviewed source management and SSRF-safe HTML ingestion, mocked only."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent.html_extract import extract_html
from hamar_agent.portal import PortalService
from hamar_agent.portal_sources import (
    APPROVED_PAGES, HOST, MAX_BYTES, PageApproval, PinnedHTTPSConnection, RateGate,
    ReviewedFetcher, import_reviewed_bytes, load_approvals, load_catalog,
    main, public_addresses, save_catalog, validate_page_url,
)
from hamar_agent.search import SearchIndex
from hamar_agent.application import WorkflowService
from hamar_agent.schemas import Claim

RAW = b"<html><main><h1>Fictional water</h1><p>Fictional service information.</p></main></html>"
ROBOTS = b"User-agent: *\nAllow: /\n"


def approval(raw=RAW, robots=ROBOTS):
    paragraphs = extract_html(raw.decode())
    return PageApproval("synthetic-network-test", "https://www.hamar.kommune.no/approved-offline-test/",
                        "Synthetic network test, not municipal facts", "teknisk", str(date.today()), str(date.today()),
                        hashlib.sha256(raw).hexdigest(), hashlib.sha256("\n\n".join(paragraphs).encode()).hexdigest(),
                        hashlib.sha256(robots).hexdigest(), "Offline synthetic test artifact only", True)


def response(raw, content_type):
    result = Mock()
    result.status = 200
    result.headers = Message()
    result.headers["Content-Type"] = content_type + "; charset=utf-8"
    result.read.side_effect = io.BytesIO(raw).read
    return result


class ReviewedSourceTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("external network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.approval = approval()

    def fetcher(self, robots=ROBOTS, raw=RAW):
        robot_response = response(robots, "text/plain")
        page_response = response(raw, "text/html")
        factory = Mock()
        first, second = Mock(), Mock()
        first.getresponse.return_value = robot_response
        second.getresponse.return_value = page_response
        factory.side_effect = [first, second]
        gate = Mock()
        fetcher = ReviewedFetcher(enabled=True, approvals={self.approval.source_id:self.approval},
                                  resolver=Mock(return_value=["93.184.216.34"]), connection_factory=factory, rate_gate=gate)
        return fetcher, factory, gate, first, second, robot_response, page_response

    def test_production_registry_is_empty_immutable_and_disabled_before_dns(self):
        self.assertEqual(dict(APPROVED_PAGES), {})
        resolver = Mock()
        with self.assertRaises(ValueError):
            ReviewedFetcher(resolver=resolver).fetch("unapproved")
        resolver.assert_not_called()
        with self.assertRaises(TypeError):
            APPROVED_PAGES["x"] = self.approval

    def test_disabled_even_with_test_approval(self):
        resolver = Mock()
        with self.assertRaises(ValueError):
            ReviewedFetcher(approvals={self.approval.source_id:self.approval}, resolver=resolver).fetch(self.approval.source_id)
        resolver.assert_not_called()

    def test_unsafe_urls_and_missing_privacy_review_are_rejected(self):
        for url in ("http://www.hamar.kommune.no/a/", "https://localhost/a/", "https://127.0.0.1/a/", "https://www.hamar.kommune.no.evil.invalid/a/", "https://user@www.hamar.kommune.no/a/", "https://www.hamar.kommune.no:443/a/", "https://www.hamar.kommune.no/a/?x=1", "https://www.hamar.kommune.no/%2fprivate", "https://www.hamar.kommune.no//other", "https://www.hamar.kommune.no/a/#x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_page_url(url)
        with self.assertRaises(ValueError):
            replace(self.approval, no_personal_data=False)
        with self.assertRaises(ValueError):
            replace(self.approval, raw_sha256="missing")

    def test_private_or_mixed_dns_answers_refused(self):
        for addresses in (["127.0.0.1"], ["10.0.0.1"], ["169.254.169.254"], ["::1"], ["93.184.216.34", "192.168.1.1"]):
            fetcher, factory, *_ = self.fetcher()
            fetcher.resolver.return_value = addresses
            with self.subTest(addresses=addresses), self.assertRaises(ValueError):
                fetcher.fetch(self.approval.source_id)
            factory.assert_not_called()

    def test_default_resolver_checks_every_ip(self):
        with patch("socket.getaddrinfo", return_value=[(None,None,None,None,("10.0.0.1",443))]):
            with self.assertRaises(ValueError):
                public_addresses(HOST)

    def test_pinned_connection_uses_ip_with_original_tls_hostname(self):
        connection = PinnedHTTPSConnection(HOST, "93.184.216.34")
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)
        fake_socket = Mock()
        connection._context = Mock()
        with patch("socket.create_connection", return_value=fake_socket) as connect:
            connection.connect()
        connect.assert_called_once_with(("93.184.216.34",443), timeout=10)
        connection._context.wrap_socket.assert_called_once_with(fake_socket, server_hostname=HOST)

    def test_tls_failure_closes_raw_socket(self):
        connection = PinnedHTTPSConnection(HOST, "93.184.216.34")
        connection._context = Mock()
        connection._context.wrap_socket.side_effect = ssl.SSLError("failure")
        raw = Mock()
        with patch("socket.create_connection", return_value=raw), self.assertRaises(ssl.SSLError):
            connection.connect()
        raw.close.assert_called_once()

    def test_live_pipeline_mocked_html_robots_provenance_and_cleanup(self):
        fetcher, factory, gate, first, second, robot_response, page_response = self.fetcher()
        doc = fetcher.fetch(self.approval.source_id)
        self.assertEqual(doc.source.url, self.approval.url)
        self.assertFalse(doc.source.synthetic)
        self.assertTrue(doc.retrieved_at)
        self.assertEqual(factory.call_args_list[0].args, (HOST,"93.184.216.34"))
        self.assertEqual(first.request.call_args.args[1], "/robots.txt")
        self.assertEqual(second.request.call_args.args[1], "/approved-offline-test/")
        self.assertEqual([call.args[0] for call in gate.wait.call_args_list], [2,2])
        first.close.assert_called_once(); second.close.assert_called_once()
        robot_response.close.assert_called_once(); page_response.close.assert_called_once()

    def test_robots_deny_or_changed_policy_prevents_page_request(self):
        for robots in (b"User-agent: *\nDisallow: /\n", b"changed"):
            fetcher, factory, *_ = self.fetcher(robots=robots)
            if robots.startswith(b"User-agent"):
                fetcher.approvals = {self.approval.source_id:approval(robots=robots)}
            with self.subTest(robots=robots), self.assertRaises(ValueError):
                fetcher.fetch(self.approval.source_id)
            self.assertEqual(factory.call_count, 1)

    def test_crawl_delay_and_request_rate_are_respected(self):
        robots = b"User-agent: *\nAllow: /\nCrawl-delay: 5\nRequest-rate: 1/8\n"
        fetcher, _, gate, *_ = self.fetcher(robots=robots)
        fetcher.approvals = {self.approval.source_id:approval(robots=robots)}
        fetcher.fetch(self.approval.source_id)
        self.assertEqual(gate.wait.call_args_list[-1].args, (8.0,))

    def test_rate_gate_waits_between_requests(self):
        clock, sleep = Mock(side_effect=[10,11,12]), Mock()
        gate = RateGate(clock=clock, sleep=sleep)
        gate.wait(2); gate.wait(2)
        sleep.assert_called_once_with(1)

    def test_redirect_and_login_http_statuses_never_followed(self):
        for status in (301,302,307,308,401,403,500):
            fetcher, _, _, _, second, _, page_response = self.fetcher()
            page_response.status = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                fetcher.fetch(self.approval.source_id)
            page_response.read.assert_not_called()
            second.close.assert_called_once()

    def test_wrong_content_type_size_encoding_and_noindex_fail_closed(self):
        for name,value in (("Content-Type","application/pdf"),("Content-Length",str(MAX_BYTES+1)),
                           ("Content-Encoding","gzip"),("X-Robots-Tag","noindex")):
            fetcher, *_, page_response = self.fetcher()
            if name in page_response.headers:
                page_response.headers.replace_header(name,value)
            else:
                page_response.headers[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                fetcher.fetch(self.approval.source_id)
            page_response.close.assert_called_once()

    def test_stream_limits_apply_without_length_header(self):
        fetcher, *_, page_response = self.fetcher(raw=b'a'*(MAX_BYTES+1))
        with self.assertRaises(ValueError):
            fetcher.fetch(self.approval.source_id)
        page_response.close.assert_called_once()

    def test_timeout_tls_and_incomplete_http_errors_are_sanitized(self):
        for exc in (TimeoutError("secret"), ssl.SSLError("secret")):
            fetcher, _, _, first, *_ = self.fetcher()
            first.request.side_effect = exc
            with self.subTest(exc=exc), self.assertRaises(ValueError) as raised:
                fetcher.fetch(self.approval.source_id)
            self.assertNotIn("secret", str(raised.exception))
            first.close.assert_called_once()

    def test_snapshot_import_requires_fixed_body_and_extracted_hashes(self):
        stamp = datetime.now(timezone.utc).isoformat()
        doc = import_reviewed_bytes(self.approval, RAW, retrieved_at=stamp,robots=ROBOTS)
        self.assertEqual(doc.retrieved_at, stamp)
        with self.assertRaises(ValueError):
            import_reviewed_bytes(self.approval, RAW+b' ', retrieved_at=stamp,robots=ROBOTS)
        with self.assertRaises(ValueError):
            import_reviewed_bytes(replace(self.approval,text_sha256="0"*64), RAW, retrieved_at=stamp,robots=ROBOTS)
        with self.assertRaises(ValueError):
            import_reviewed_bytes(self.approval, RAW, retrieved_at="2020-01-01",robots=ROBOTS)

    def test_expired_approval_rejected_before_network(self):
        yesterday = str(date.today()-timedelta(days=1))
        fetcher, factory, *_ = self.fetcher()
        fetcher.approvals = {self.approval.source_id:replace(self.approval,reviewed_on=yesterday,expires_on=yesterday)}
        with self.assertRaises(ValueError):
            fetcher.fetch(self.approval.source_id)
        factory.assert_not_called()

    def test_catalog_roundtrip_reapproval_and_no_overwrite(self):
        doc = import_reviewed_bytes(self.approval, RAW, retrieved_at=datetime.now(timezone.utc).isoformat(),robots=ROBOTS)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"catalog.json"
            save_catalog([doc],path)
            index = load_catalog(path,{self.approval.source_id:self.approval})
            self.assertEqual(index.search("water")[0].document.source.url,self.approval.url)
            with self.assertRaises(FileExistsError):
                save_catalog([doc],path)
            with self.assertRaises(ValueError):
                load_catalog(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["documents"][0]["source"]["paragraphs"][0]["text"] = "tampered"
            path.write_text(json.dumps(payload),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_catalog(path,{self.approval.source_id:self.approval})

    def test_real_catalog_mock_reports_provider_dependency_and_injected_provider_works(self):
        doc = import_reviewed_bytes(self.approval,RAW,retrieved_at=datetime.now(timezone.utc).isoformat(),robots=ROBOTS)
        index = SearchIndex([doc])
        self.assertEqual(PortalService(index=index).answer("water")["answer_status"],"provider_unavailable")
        provider = Mock()
        provider.summarize.side_effect = lambda source: (Claim("c1",source.paragraphs[0].text,source.paragraphs[0].id,source.paragraphs[0].text),)
        answer = PortalService(WorkflowService(summarizer=provider,provider="injected-test-double"),index=index).answer("water")
        self.assertEqual(answer["answer_status"],"evidence_checked")
        self.assertEqual(answer["citations"][0]["url"],self.approval.url)

    def test_manifest_empty_and_invalid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"approvals.json"
            path.write_text('[]',encoding="utf-8")
            self.assertFalse(load_approvals(path))
            path.write_text('[{}]',encoding="utf-8")
            with self.assertRaises(TypeError):
                load_approvals(path)

    def test_snapshot_import_also_checks_robots(self):
        with self.assertRaises(ValueError):
            import_reviewed_bytes(self.approval,RAW,retrieved_at=datetime.now(timezone.utc).isoformat(),robots=b"different")

    def test_catalog_documents_expire_without_a_network_refresh(self):
        doc = import_reviewed_bytes(self.approval,RAW,retrieved_at=datetime.now(timezone.utc).isoformat(),robots=ROBOTS)
        doc = replace(doc,approval_expires=str(date.today()-timedelta(days=1)))
        self.assertFalse(SearchIndex([doc]).search("water"))

    def test_source_admin_default_list_and_snapshot_import_are_offline(self):
        from contextlib import redirect_stdout
        from dataclasses import asdict
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["list"]),0)
        self.assertEqual(json.loads(output.getvalue())["approved_sources"],[])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"approvals.json").write_text(json.dumps([asdict(self.approval)]),encoding="utf-8")
            (root/"snapshot.html").write_bytes(RAW)
            (root/"robots.txt").write_bytes(ROBOTS)
            args=["import-snapshot","--approvals",str(root/"approvals.json"),"--source-id",self.approval.source_id,
                  "--snapshot",str(root/"snapshot.html"),"--robots-snapshot",str(root/"robots.txt"),
                  "--retrieved-at",datetime.now(timezone.utc).isoformat(),"--output",str(root/"catalog.json")]
            self.assertEqual(main(args),0)
            self.assertTrue(load_catalog(root/"catalog.json",{self.approval.source_id:self.approval}).search("water"))

    def test_missing_snapshot_timestamp_is_rejected(self):
        from contextlib import redirect_stderr
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"approvals.json").write_text(json.dumps([asdict(self.approval)]),encoding="utf-8")
            (root/"snapshot.html").write_bytes(RAW)
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as raised:
                main(["import-snapshot","--approvals",str(root/"approvals.json"),"--source-id",self.approval.source_id,
                      "--snapshot",str(root/"snapshot.html"),"--output",str(root/"catalog.json")])
            self.assertEqual(raised.exception.code,2)
            self.assertFalse((root/"catalog.json").exists())

    def test_untyped_approval_fields_are_rejected_cleanly(self):
        for field in ("title","rationale","reviewed_on","raw_sha256"):
            with self.subTest(field=field),self.assertRaises(ValueError):
                replace(self.approval,**{field:None})
