"""Offline HTML, full-text relevance, provenance and portal integration tests."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from hamar_agent.application import WorkflowService
from hamar_agent.categories import CATEGORY_IDS
from hamar_agent.html_extract import ExtractionError, extract_html
from hamar_agent.portal import PortalService, demo_index
from hamar_agent.schemas import Paragraph, Source
from hamar_agent.search import (FOLLOWUP_MODIFIERS, QUERY_ALIASES, STOPWORDS, InvalidQueryError,
                                QueryPrivacyError, SearchIndex, UnsupportedTopicError,
                                index_document, validate_query)
from hamar_agent.summarize import MockScenario, MockSummarizer
from hamar_agent.web import WebApplication


def document(id, title, text, category="teknisk"):
    return index_document(Source(id, title, (Paragraph("p1", text),), True), category)


def reviewed_document(id, title, text, category):
    source = Source(id, title, (Paragraph("p1", text),), False,
                    "https://www.hamar.kommune.no/tjenester/")
    return index_document(source, category, retrieved_at=datetime.now(timezone.utc).isoformat(),
                          approval_expires=(date.today() + timedelta(days=1)).isoformat(), raw_sha256="0" * 64)


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
        answer = portal.answer("")
        self.assertEqual(answer["answer_status"], "clarification_required")
        self.assertEqual(answer["official_menu_url"], "https://www.hamar.kommune.no/meny/")

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

    def test_real_source_queries_are_limited_to_general_service_topics(self):
        self.assertEqual(validate_query("vanntrykk", real_sources=True), ["vanntrykk"])
        for query in ("Fictional Person", "Storgata 12", "diagnose eksempel"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query, real_sources=True)

    def test_reviewed_municipal_search_matches_common_norwegian_inflections(self):
        index = SearchIndex([
            document("hamar-plan-test", "Politikk og planer", "Kommuneplanens samfunnsdel ble vedtatt.", "politikk"),
            document("hamar-health-test", "Folkehelse", "Folkehelsearbeidet skjer i alle samfunnssektorer.", "helse"),
        ])
        self.assertEqual([h.document.source.id for h in index.search("kommuneplan")], ["hamar-plan-test"])
        self.assertEqual([h.document.source.id for h in index.search("folkehelse")], ["hamar-health-test"])

    def test_real_search_accepts_norwegian_question_phrasing_and_ascii_spelling(self):
        index = SearchIndex([
            reviewed_document("hamar-miljo-test", "Luftkvalitet og miljø", "Informasjon om luftkvalitet og miljø i Hamar.", "miljo"),
            reviewed_document("hamar-sfo-test", "Gratis SFO", "Informasjon om gratis SFO for elever.", "oppvekst"),
            reviewed_document("hamar-vann-test", "Drikkevann", "Informasjon om drikkevann i kommunen.", "teknisk"),
            document("hamar-bygg-test", "Bolig og byggesak", "Du kan bygge en garasje uten å søke.", "bolig"),
        ])
        norwegian_miljo = "milj" + chr(248)
        self.assertEqual([h.document.source.id for h in index.search(norwegian_miljo)], ["hamar-miljo-test"])
        self.assertEqual([h.document.source.id for h in index.search("miljo")], ["hamar-miljo-test"])
        question = "Hvordan s" + chr(248) + "ker jeg gratis SFO?"
        self.assertEqual(validate_query(question, real_sources=True), ["gratis", "sfo"])
        self.assertEqual([h.document.source.id for h in index.search(question)], ["hamar-sfo-test"])
        natural_question = "Hvordan fungerer gratis SFO for elever i Hamar?"
        self.assertEqual(validate_query(natural_question, real_sources=True), ["gratis", "sfo"])
        self.assertEqual([h.document.source.id for h in index.search(natural_question)], ["hamar-sfo-test"])
        who_question = "Hvem får gratis SFO-tid i Hamar?"
        self.assertEqual(validate_query(who_question, real_sources=True), ["gratis", "sfo"])
        self.assertEqual([h.document.source.id for h in index.search(who_question)], ["hamar-sfo-test"])
        offer_question = "Hva med SFO-tilbud for de yngste elevene?"
        self.assertEqual(validate_query(offer_question, real_sources=True), ["sfo"])
        self.assertEqual([h.document.source.id for h in index.search(offer_question)], ["hamar-sfo-test"])
        self.assertEqual(validate_query("Hva gjelder for vann?", real_sources=True), ["vann"])
        self.assertFalse(index.search("skole vann"))
        drinking_water_question = "Hvor finner jeg informasjon om drikkevann?"
        self.assertEqual(validate_query(drinking_water_question, real_sources=True), ["drikkevann"])
        self.assertEqual([h.document.source.id for h in index.search(drinking_water_question)], ["hamar-vann-test"])
        building_question = "Hva gjelder for byggesak?"
        self.assertEqual(validate_query(building_question, real_sources=True), ["bygge"])
        self.assertEqual([h.document.source.id for h in index.search(building_question)], ["hamar-bygg-test"])
        building_answer = PortalService(WorkflowService(), index=index).answer(building_question)
        self.assertEqual(building_answer["answer_status"], "demo")
        self.assertEqual(building_answer["result"]["claims"][0]["evidence_quote"], "Du kan bygge en garasje uten å søke.")
        with self.assertRaises(ValueError):
            index.search("adresse til privat person")

    def test_real_filter_accepts_supported_norwegian_wording_without_widening_topics(self):
        queries = {
            "Hvem f" + chr(229) + "r gratis SFO-tid i Hamar?": ["gratis", "sfo"],
            "Hva gjelder for gratis SFO?": ["gratis", "sfo"],
            "Hvordan s" + chr(248) + "ker jeg om SFO?": ["sfo"],
            "Hva kan jeg bygge uten " + chr(229) + " s" + chr(248) + "ke?": ["bygge"],
            "Bygge uten s" + chr(248) + "knad": ["bygge"],
            "Hvordan s" + chr(248) + "ker jeg om byggetillatelse?": ["bygge"],
            "Hva koster parkering i Hamar?": ["parkering"],
            "M" + chr(229) + " jeg s" + chr(248) + "ke om " + chr(229) + " bygge garasje?": ["bygge"],
            "Hvor kan jeg parkere?": ["parkering"],
            "Hvor kommer drikkevannet fra?": ["drikkevann"],
            "Hvordan fungerer vannforsyningen?": ["vann"],
            "Hva kan jeg l" + chr(229) + "ne p" + chr(229) + " biblioteket?": ["bibliotek"],
        }
        for query, expected in queries.items():
            with self.subTest(query=query):
                self.assertEqual(validate_query(query, real_sources=True), expected)
        self.assertEqual(QUERY_ALIASES["byggetillatelse"], "bygge")
        self.assertEqual(QUERY_ALIASES["garasje"], "bygge")
        self.assertEqual(QUERY_ALIASES["parkere"], "parkering")
        self.assertEqual(QUERY_ALIASES["drikkevannet"], "drikkevann")
        self.assertEqual(QUERY_ALIASES["vannforsyningen"], "vann")
        self.assertEqual(QUERY_ALIASES["lane"], "bibliotek")
        for query in ("Kari Eksempel", "Storgata 12", "diagnose eksempel", "kari@example.invalid"):
            with self.subTest(private_query=query), self.assertRaises(ValueError):
                validate_query(query, real_sources=True)
        with self.assertRaises(QueryPrivacyError):
            validate_query("Kari Eksempel bor i Storgata 12", real_sources=True)
        with self.assertRaises(UnsupportedTopicError):
            validate_query("Hva gjelder teleportering?", real_sources=True)
        overview = PortalService().overview()
        self.assertEqual(overview["query_stopwords"], sorted(STOPWORDS))
        self.assertEqual(overview["query_followup_modifiers"], sorted(FOLLOWUP_MODIFIERS))
        self.assertEqual(overview["query_aliases"], QUERY_ALIASES)

    def test_application_and_exact_parking_price_requests_fail_closed_with_source_links(self):
        index = SearchIndex([
            reviewed_document("hamar-sfo-test", "Skole og SFO", "Alle barn på 1. til 3. trinn får gratis SFO.", "oppvekst"),
            reviewed_document("hamar-building-test", "Bygge uten å søke", "Du kan bygge en garasje, men det er ikke sikkert du må søke.", "bolig"),
            reviewed_document("hamar-parking-test", "Parkering og betaling", "Parkering er gratis den første timen, deretter parkerer du mot avgift.", "teknisk"),
        ])
        provider = Mock()
        workflow = WorkflowService(summarizer=provider, provider="ollama:llama3.2:3b")
        portal = PortalService(workflow, index=index)
        questions = (
            "Hvordan søker jeg om SFO?",
            "Hvordan søker jeg om byggetillatelse?",
            "Hva koster parkering i Hamar?",
        )
        for query in questions:
            with self.subTest(query=query):
                answer = portal.answer(query)
                self.assertEqual(answer["answer_status"], "insufficient_evidence")
                self.assertIsNone(answer["result"])
                self.assertTrue(answer["citations"])
        self.assertEqual(len([c for c in portal.answer("Hva koster parkering i Hamar?")["citations"] if c["source_id"] == "hamar-parking-test"]), 1)
        provider.summarize.assert_not_called()

    def test_safe_unknown_topic_asks_for_clarification_without_model_or_private_label(self):
        provider = Mock()
        portal = PortalService(WorkflowService(summarizer=provider, provider="ollama:llama3.2:3b"))
        answer = portal.answer("Hva gjelder teleportering?")
        self.assertEqual(answer["answer_status"], "clarification_required")
        self.assertEqual(answer["official_menu_url"], "https://www.hamar.kommune.no/meny/")
        self.assertNotIn("teleportering", json.dumps(answer))
        provider.summarize.assert_not_called()
        search = portal.search("teleportering")
        self.assertEqual(search["query_status"], "unsupported_topic")
        self.assertEqual(search["official_menu_url"], "https://www.hamar.kommune.no/meny/")

    def test_library_loan_question_refuses_without_supported_excerpt(self):
        provider = Mock()
        workflow = WorkflowService(summarizer=provider, provider="ollama:llama3.2:3b")
        index = SearchIndex([reviewed_document(
            "hamar-library-test", "Hamar bibliotek",
            "Hamar bibliotek har selvbetjente åpningstider fra kl. 06 til 22.", "kultur")])
        answer = PortalService(workflow, index=index).answer("Hva kan jeg låne på biblioteket?")
        self.assertEqual(answer["answer_status"], "insufficient_evidence")
        self.assertIsNone(answer["result"])
        self.assertEqual(answer["official_menu_url"], "https://www.hamar.kommune.no/meny/")
        self.assertTrue(answer["citations"])
        provider.summarize.assert_not_called()

    def test_privacy_rejection_is_distinct_from_insufficient_topic_coverage(self):
        provider = Mock()
        workflow = WorkflowService(summarizer=provider, provider="ollama:llama3.2:3b")
        answer = PortalService(workflow).answer("Kari Eksempel bor i Storgata 12")
        self.assertEqual(answer["answer_status"], "input_rejected")
        self.assertEqual(answer["query"], "")
        self.assertEqual(answer["citations"], [])
        provider.summarize.assert_not_called()

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
            answer = PortalService(workflow).answer("vanntrykk")
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

    def test_safe_unknown_topic_route_returns_clarification_and_official_menu(self):
        app = WebApplication()
        headers = {"Host":"127.0.0.1:8000", "Origin":"http://127.0.0.1:8000",
                   "Content-Type":"application/json", "X-Hamar-Token":app.token}
        response = app.dispatch("POST", "/api/answer", headers, '{"query":"Hva gjelder teleportering?"}'.encode())
        self.assertEqual(response.status, 200)
        data = json.loads(response.body)["answer"]
        self.assertEqual(data["answer_status"], "clarification_required")
        self.assertEqual(data["official_menu_url"], "https://www.hamar.kommune.no/meny/")
        self.assertNotIn("teleportering", json.dumps(data))

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
        portal = PortalService(workflow, index=SearchIndex([document("a","Helse","A different topic.")]))
        self.assertTrue(portal.search("helse")["results"])
        self.assertEqual(portal.answer("helse")["answer_status"],"insufficient_evidence")
        workflow.summarizer.summarize.assert_not_called()

    def test_homepage_has_official_link_privacy_guidance_and_no_external_scripts(self):
        app = WebApplication()
        response = app.dispatch("GET","/",{"Host":"127.0.0.1:8000"})
        html = response.body.decode("utf-8")
        self.assertIn('href="https://www.hamar.kommune.no/"',html)
        self.assertIn('id="query"',html)
        self.assertIn('Ikke skriv navn',html)
        self.assertNotIn('<script src="http',html)

    def test_public_pages_and_answer_json_use_neutral_credit_without_student_names(self):
        app = WebApplication()
        host = {"Host": "127.0.0.1:8000"}
        headers = host | {"Origin": "http://127.0.0.1:8000", "Content-Type": "application/json",
                          "X-Hamar-Token": app.token}
        homepage = app.dispatch("GET", "/", host)
        html = homepage.body.decode("utf-8")
        self.assertIn("Studentprosjekt ved Universitetet i Innlandet.", html)
        self.assertNotIn("Laget av programmerere", html)

        public_bodies = [homepage.body, app.dispatch("GET", "/app.js", host).body,
                         app.dispatch("GET", "/style.css", host).body,
                         app.dispatch("GET", "/api/portal", host).body,
                         app.dispatch("GET", "/api/sources", host).body]
        search_response = app.dispatch("POST", "/api/search", headers, b'{"query":"vann"}')
        self.assertEqual(search_response.status, 200)
        public_bodies.append(search_response.body)
        answer_response = app.dispatch("POST", "/api/answer", headers, b'{"query":"vann"}')
        self.assertEqual(answer_response.status, 200)
        answer_payload = json.loads(answer_response.body)
        public_bodies.append(answer_response.body)
        download = app.dispatch("GET", "/api/results/" + answer_payload["run_id"], headers)
        self.assertEqual(download.status, 200)
        public_bodies.append(download.body)

        student_names = ("Linda", "Linda Merete Svela", "Jesper", "Jesper Guttormsen")
        for body in public_bodies:
            text = body.decode("utf-8").casefold()
            for name in student_names:
                with self.subTest(name=name):
                    self.assertNotIn(name.casefold(), text)
