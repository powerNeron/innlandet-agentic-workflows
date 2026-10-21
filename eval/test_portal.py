"""Offline HTML, full-text relevance, provenance and portal integration tests."""
from dataclasses import replace
from datetime import date, timedelta
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from hamar_agent.application import WorkflowService
from hamar_agent.categories import CATEGORY_IDS
from hamar_agent.html_extract import ExtractionError, extract_html
from hamar_agent.portal import PortalService, demo_index
from hamar_agent.schemas import Paragraph, Source
from hamar_agent.search import SearchIndex, index_document, validate_query
from hamar_agent.summarize import MockScenario, MockSummarizer
from hamar_agent.web import WebApplication


def document(id, title, text, category="teknisk"):
    return index_document(Source(id, title, (Paragraph("p1", text),), True), category)


class PortalTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("external network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def test_html_extracts_article_without_template_or_active_content(self):
        html = '<html><header>Menu</header><main><h1>Vann &amp; avløp</h1><p>Ren tekst.</p><script>alert(1)</script><nav>Navigate</nav><div hidden>Hidden</div><form>Form</form></main><footer>Footer</footer></html>'
        self.assertEqual(extract_html(html), ("Vann & avløp", "Ren tekst."))

    def test_html_rejects_missing_duplicate_hidden_or_empty_boundaries(self):
        for html in ('<p>No main</p>', '<main>A</main><main>B</main>', '<main hidden>A</main>', '<main> </main>'):
            with self.subTest(html=html), self.assertRaises(ExtractionError):
                extract_html(html)

    def test_html_rejects_login_noindex_contact_and_size(self):
        for html in ('<input type="password"><main>A</main>', '<meta name="robots" content="noindex"><main>A</main>',
                     '<main>example@example.invalid</main>', '<main>Phone 12345678</main>', '<main>' + 'a'*524289 + '</main>'):
            with self.subTest(html=html[:60]), self.assertRaises(ExtractionError):
                extract_html(html)

    def test_article_boundary_is_explicit(self):
        self.assertEqual(extract_html('<article><p>One</p><p>Two</p></article>', content_tag="article"), ("One", "Two"))
        with self.assertRaises(ExtractionError):
            extract_html('<main>A</main>', content_tag="body")

    def test_search_indexes_full_body_and_is_deterministic(self):
        index = SearchIndex([document("a", "Other title", "Long body with parking and water."), document("b", "Other", "Nothing relevant.")])
        hits = index.search("PARKING water")
        self.assertEqual([h.document.source.id for h in hits], ["a"])
        self.assertEqual(hits, index.search("parking water"))

    def test_title_boost_ranks_title_match_first(self):
        index = SearchIndex([document("a", "Water", "Water service."), document("b", "Other", "Water service.")])
        self.assertEqual(index.search("water")[0].document.source.id, "a")

    def test_norwegian_unicode_and_category_filters(self):
        index = SearchIndex([document("a", "Miljø", "Grønn transport og miljø.", "miljo"), document("b", "Miljø", "Miljø i biblioteket.", "kultur")])
        self.assertEqual([h.document.source.id for h in index.search("MILJØ", category="miljo")], ["a"])
        self.assertFalse(index.search("unmatched"))
        self.assertFalse(index.search("transport biblioteket"))

    def test_empty_query_browses_but_does_not_generate_answer(self):
        portal = PortalService()
        self.assertTrue(portal.search("", category="kultur")["results"])
        self.assertEqual(portal.answer("")["answer_status"], "insufficient_evidence")

    def test_query_and_index_limits(self):
        for query in (None, "a"*161, "hello\nworld", "a@example.invalid", "12345678", "https://example.invalid"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query)
        with self.assertRaises(ValueError):
            SearchIndex([document("a", "A", "A"), document("a", "B", "B")])
        with self.assertRaises(ValueError):
            SearchIndex([document(str(i), "A", "A") for i in range(201)])
        with self.assertRaises(ValueError):
            demo_index().search("vann", category="unapproved")

    def test_text_integrity_is_required(self):
        with self.assertRaises(ValueError):
            replace(document("a", "A", "Text"), text_sha256="0"*64)

    def test_demo_collection_is_synthetic_and_categories_are_reference_only(self):
        portal = PortalService()
        overview = portal.overview()
        self.assertTrue(overview["synthetic"])
        self.assertEqual(len(overview["categories"]), 7)
        self.assertEqual({c["id"] for c in overview["categories"]}, CATEGORY_IDS)
        for hit in portal.search("vann")["results"]:
            self.assertIsNone(hit["url"])
            self.assertIsNone(hit["retrieved_at"])
            self.assertTrue(hit["synthetic"])

    def test_no_hit_never_calls_provider_or_fetch(self):
        workflow = WorkflowService(summarizer=Mock())
        with patch("hamar_agent.portal_sources.socket.getaddrinfo", side_effect=AssertionError("must not resolve")):
            answer = PortalService(workflow).answer("unmatchedword")
        workflow.summarizer.summarize.assert_not_called()
        self.assertEqual(answer["answer_status"], "insufficient_evidence")
        self.assertIsNone(answer["result"])

    def test_answer_invokes_verifier_and_every_reference_has_a_citation(self):
        answer = PortalService().answer("vann")
        self.assertEqual(answer["answer_status"], "demo")
        citations = {c["paragraph_id"]: c for c in answer["citations"]}
        for claim in answer["result"]["claims"]:
            self.assertIn(claim["paragraph_id"], citations)
            self.assertEqual(claim["evidence_status"], "exact_match")
        self.assertTrue(answer["result"]["warnings"])

    def test_invalid_answer_reference_is_flagged(self):
        workflow = WorkflowService(summarizer=MockSummarizer(MockScenario.INVALID_PARAGRAPH))
        answer = PortalService(workflow).answer("vann")
        self.assertEqual(answer["answer_status"], "review_required")
        self.assertEqual(answer["result"]["verification"]["findings"][0]["code"], "invalid_paragraph_id")

    def test_search_and_answer_web_routes_and_exact_download(self):
        app = WebApplication()
        headers = {"Host":"127.0.0.1:8000", "Origin":"http://127.0.0.1:8000", "Content-Type":"application/json", "X-Hamar-Token":app.token}
        search = app.dispatch("POST", "/api/search", headers, b'{"query":"vann"}')
        self.assertEqual(search.status, 200)
        self.assertTrue(json.loads(search.body)["results"])
        answer = app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}')
        data = json.loads(answer.body)
        download = app.dispatch("GET", "/api/results/"+data["run_id"], headers)
        self.assertEqual(json.loads(download.body), data["answer"])
        self.assertEqual(app.dispatch("GET", "/api/portal", headers).status, 200)

    def test_portal_requests_cannot_supply_urls_or_approvals(self):
        app = WebApplication()
        headers = {"Host":"127.0.0.1:8000", "Origin":"http://127.0.0.1:8000", "Content-Type":"application/json", "X-Hamar-Token":app.token}
        for body in (b'{"query":"vann","url":"https://example.invalid"}', b'{"query":42}', b'{"query":"vann","category":[]}', b'[]', b'{"query":"a@example.invalid"}'):
            self.assertEqual(app.dispatch("POST", "/api/search", headers, body).status, 400)
        headers["X-Hamar-Token"] = "wrong"
        self.assertEqual(app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}').status, 403)

    def test_portal_provider_failure_is_sanitized(self):
        workflow = WorkflowService(summarizer=Mock())
        workflow.summarizer.summarize.side_effect = RuntimeError("secret")
        app = WebApplication(workflow)
        headers = {"Host":"127.0.0.1:8000", "Origin":"http://127.0.0.1:8000", "Content-Type":"application/json", "X-Hamar-Token":app.token}
        response = app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}')
        self.assertEqual(response.status, 422)
        self.assertNotIn(b"secret", response.body)

    def test_empty_index_is_honest_and_has_no_answers(self):
        portal = PortalService(index=SearchIndex())
        self.assertEqual(portal.overview()["documents"], 0)
        self.assertFalse(portal.search("vann")["results"])
        self.assertEqual(portal.answer("vann")["answer_status"], "insufficient_evidence")

    def test_title_only_match_is_not_answer_evidence(self):
        workflow = WorkflowService(summarizer=Mock())
        portal = PortalService(workflow, index=SearchIndex([document("a","Unicorn","A different topic.")]))
        self.assertTrue(portal.search("unicorn")["results"])
        self.assertEqual(portal.answer("unicorn")["answer_status"],"insufficient_evidence")
        workflow.summarizer.summarize.assert_not_called()

    def test_homepage_has_official_link_privacy_guidance_and_no_external_scripts(self):
        app = WebApplication()
        response = app.dispatch("GET","/",{"Host":"127.0.0.1:8000"})
        html = response.body.decode("utf-8")
        self.assertIn('href="https://www.hamar.kommune.no/"',html)
        self.assertIn('id="query"',html)
        self.assertIn('Ikke skriv navn',html)
        self.assertNotIn('<script src="http',html)
