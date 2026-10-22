"""Reviewed local source management and fail-closed live HTML regressions."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent.html_extract import extract_html
from hamar_agent.portal import PortalService
from hamar_agent.portal_sources import (
    APPROVED_PAGES, MAX_BYTES, PageApproval,
    ReviewedFetcher, import_reviewed_bytes, load_approvals, load_catalog,
    main, save_catalog, validate_page_url,
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


class ReviewedSourceTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("external network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.approval = approval()

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

    def test_live_fetch_and_private_transport_fail_before_dns_or_connection(self):
        resolver, factory, gate = Mock(), Mock(), Mock()
        fetcher = ReviewedFetcher(enabled=True, approvals={self.approval.source_id:self.approval},
                                  resolver=resolver, connection_factory=factory, rate_gate=gate)
        with self.assertRaisesRegex(ValueError, "Live HTML retrieval disabled"):
            fetcher.fetch(self.approval.source_id)
        with self.assertRaisesRegex(ValueError, "no network access was attempted"):
            fetcher._get(self.approval.url, "text/html", MAX_BYTES, 0)
        resolver.assert_not_called()
        factory.assert_not_called()
        gate.wait.assert_not_called()

    def test_live_fetch_cli_flag_cannot_enable_retrieval(self):
        from contextlib import redirect_stderr
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approvals = root / "approvals.json"
            approvals.write_text(json.dumps([asdict(self.approval)]), encoding="utf-8")
            resolver, factory = Mock(), Mock()
            with patch("socket.getaddrinfo", resolver), \
                    patch("socket.create_connection", factory), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(["fetch-reviewed", "--enable-live", "--approvals", str(approvals),
                      "--source-id", self.approval.source_id, "--output", str(root / "catalog.json")])
            self.assertEqual(raised.exception.code, 2)
            resolver.assert_not_called()
            factory.assert_not_called()
            self.assertFalse((root / "catalog.json").exists())

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
        expired = replace(self.approval,reviewed_on=yesterday,expires_on=yesterday)
        resolver = Mock()
        fetcher = ReviewedFetcher(enabled=True, approvals={expired.source_id:expired}, resolver=resolver)
        with self.assertRaises(ValueError):
            fetcher.fetch(expired.source_id)
        resolver.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"expired-approvals.json"
            from dataclasses import asdict
            path.write_text(json.dumps([asdict(expired)]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expired"):
                load_approvals(path)

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

    def test_existing_reviewed_manifest_has_eight_fixed_expiries(self):
        manifest = Path(__file__).resolve().parents[1] / "docs" / "approved-service-pages.json"
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(entries), 8)
        self.assertEqual({entry["expires_on"] for entry in entries}, {"2026-10-28"})
        self.assertTrue(all(entry["reviewed_on"] == "2026-10-21" for entry in entries))

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
