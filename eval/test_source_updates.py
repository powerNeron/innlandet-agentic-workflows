import json
from datetime import date, datetime, timezone, timedelta
from dataclasses import asdict, replace
from contextvars import copy_context
from threading import Event, Thread
import time
import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hamar_agent.html_extract import service_candidates
from hamar_agent.portal_sources import ReviewedFetcher
from hamar_agent.source_updates import compare_candidate, load_candidate, load_update_inputs, save_proposal
from hamar_agent.source_updates import RequestBoundSources, PageObservation, SourceRefreshError
from hamar_agent.portal_sources import PageApproval
from hamar_agent.search import SearchIndex, index_document
from hamar_agent.schemas import Source, Paragraph
from hamar_agent.real_sources import MunicipalWorkflowService, create_municipal_service
from hamar_agent.ollama_provider import OllamaClient, OllamaConfig
from hamar_agent.portal import PortalService
from hamar_agent.web import WebApplication, create_server
from hamar_agent.run_control import run_scope, RunPolicy, active_workers, current_run


URL = "https://www.hamar.kommune.no/skolefritidsordning/12-timer-gratis-sfo-for-1-3-trinn/"


def model():
    approval = SimpleNamespace(source_id="hamar-sfo", url=URL, text_sha256="a" * 64,
                               reviewed_on="2026-10-21", expires_on="2026-10-28")
    paragraph = SimpleNamespace(text="Kommunen tilbyr 12 timer gratis SFO.")
    source = SimpleNamespace(id="hamar-sfo", url=URL, paragraphs=(paragraph,))
    doc = SimpleNamespace(source=source)
    return {"hamar-sfo": approval}, SimpleNamespace(documents={"hamar-sfo": doc})


class SourceUpdateTests(unittest.TestCase):
    def candidate(self, paragraphs, *, url=URL):
        return {"source_id": "hamar-sfo", "url": url,
                "observed_at": datetime.now(timezone.utc).isoformat(), "paragraphs": paragraphs}

    def test_whitespace_normalization_detects_unchanged_page(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["Kommunen  tilbyr\n12 timer gratis SFO."]), approvals, catalog,
                                  today=date(2026, 10, 22))
        self.assertEqual(report["status"], "unchanged")
        self.assertEqual(report["previous_normalized_text_sha256"], report["candidate_normalized_text_sha256"])
        self.assertFalse(report["catalog_changed"])
        self.assertFalse(report["approval_changed"])

    def test_changed_text_is_separate_human_review_proposal(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["Kommunen tilbyr 10 timer gratis SFO."]), approvals, catalog,
                                  today=date(2026, 10, 22))
        self.assertEqual(report["status"], "changed_human_review_required")
        self.assertEqual(report["old_excerpts"], ["Kommunen tilbyr 12 timer gratis SFO."])
        self.assertEqual(report["proposed_excerpts"], ["Kommunen tilbyr 10 timer gratis SFO."])
        self.assertNotEqual(report["previous_normalized_text_sha256"], report["candidate_normalized_text_sha256"])
        self.assertTrue(report["human_approval_required"])
        self.assertFalse(report["catalog_changed"])
        self.assertFalse(report["approval_changed"])

    def test_expired_approval_never_becomes_current(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["New public service excerpt."]), approvals, catalog,
                                  today=date(2026, 10, 29))
        self.assertEqual(report["status"], "approval_expired_human_review_required")
        self.assertEqual(report["previous_approval_expires"], "2026-10-28")

    def test_read_only_update_review_can_report_expired_source_without_reenabling_retrieval(self):
        text = "Kommunen tilbyr 12 timer gratis SFO."
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        approval = {"source_id": "hamar-sfo", "url": URL, "title": "SFO", "category": "oppvekst",
                    "reviewed_on": "2026-01-01", "expires_on": "2026-01-02", "raw_sha256": "1" * 64,
                    "text_sha256": text_hash, "robots_sha256": "2" * 64, "rationale": "Reviewed service text.",
                    "no_personal_data": True}
        catalog = {"catalog_version": 1, "documents": [{"source": {"id": "hamar-sfo", "title": "SFO",
                    "url": URL, "synthetic": False, "paragraphs": [{"id": "p1", "text": text}]},
                    "text_sha256": text_hash, "raw_sha256": "1" * 64, "category": "oppvekst", "approval_expires": "2026-01-02"}]}
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approvals.json"; catalog_path = Path(directory) / "catalog.json"
            approval_path.write_text(json.dumps([approval]), encoding="utf-8")
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            approvals, index = load_update_inputs(approval_path, catalog_path)
            report = compare_candidate(self.candidate([text]), approvals, index, today=date(2026, 10, 22))
            self.assertEqual(report["status"], "approval_expired_human_review_required")
            with self.assertRaises(ValueError):
                # Normal retrieval loader still fails closed for this expired record.
                from hamar_agent.portal_sources import load_approvals
                load_approvals(approval_path)

    def test_wrong_url_and_unknown_source_are_rejected(self):
        approvals, catalog = model()
        with self.assertRaises(ValueError):
            compare_candidate(self.candidate(["Text"], url="https://evil.example/"), approvals, catalog)
        bad = self.candidate(["Text"]); bad["source_id"] = "unknown"
        with self.assertRaises(ValueError):
            compare_candidate(bad, approvals, catalog)

    def test_candidate_rejects_html_and_personal_contact_data(self):
        for paragraph in ("<main>new text</main>", "Contact: person@example.invalid", "Telefon: 12345678"):
            with self.subTest(paragraph=paragraph), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "candidate.json"
                path.write_text(json.dumps(self.candidate([paragraph])), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_candidate(path)

    def test_candidate_schema_rejects_raw_html_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            data = self.candidate(["plain text"]); data["html"] = "<main>raw</main>"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_candidate(path)

    def test_valid_candidate_has_exact_allowlisted_identity_and_normalized_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(self.candidate(["New excerpt."])), encoding="utf-8")
            candidate = load_candidate(path)
        self.assertEqual(candidate["source_id"], "hamar-sfo")
        self.assertEqual(candidate["url"], URL)
        self.assertTrue(candidate["observed_at"].endswith("+00:00"))

    def test_production_live_fetch_is_disabled_before_transport(self):
        fetcher = ReviewedFetcher(enabled=True, approvals={"hamar-sfo": object()})
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS must not be called")), \
             patch("socket.create_connection", side_effect=AssertionError("network must not be called")), \
             self.assertRaisesRegex(ValueError, "retrieval disabled"):
            fetcher.fetch("hamar-sfo")

    def test_synthetic_html_extractor_omits_script_and_contact_boundaries(self):
        html = "<main><p>New service information.</p><script>secret instruction</script><address>private contact</address></main>"
        self.assertEqual(service_candidates(html), ("New service information.",))


    def test_proposal_write_is_exclusive(self):
        approvals, catalog = model()
        report = compare_candidate(self.candidate(["New excerpt."]), approvals, catalog)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "proposal.json"
            save_proposal(report, target)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                save_proposal(report, target)
            self.assertEqual(target.read_bytes(), before)

    def test_proposal_comparison_never_uses_network(self):
        approvals, catalog = model()
        with patch("socket.socket", side_effect=AssertionError("network blocked")):
            report = compare_candidate(self.candidate(["New excerpt."]), approvals, catalog,
                                       today=date(2026, 10, 22))
        self.assertEqual(report["status"], "changed_human_review_required")


FIXTURE_TEXT='Fiktivt testutdrag om vann. Testgebyret er 250 kroner.'
FIXTURE_RAW=('<main><p>'+FIXTURE_TEXT+'</p></main>').encode('utf-8')
FIXTURE_ROBOTS=b'User-agent: *\nAllow: /\n'
FIXTURE_URL='https://www.hamar.kommune.no/offline-source-test/'


def fixture_approval(raw=FIXTURE_RAW, *, source_id='offline-water', url=FIXTURE_URL):
    paragraphs=service_candidates(raw.decode('utf-8'))
    sha=lambda value:hashlib.sha256(value).hexdigest()
    return PageApproval(source_id,url,'Fiktiv kildetest','teknisk','2000-01-01','2099-12-31',
        sha(raw),sha('\n\n'.join(paragraphs).encode()),sha(FIXTURE_ROBOTS),'Synthetic offline fixture only',True,
        review_scope='service_excerpts',paragraph_sha256=tuple(sha(p.encode()) for p in paragraphs))


def fixture_index(text=FIXTURE_TEXT):
    source=Source('offline-water','Fiktiv kildetest',(Paragraph('p1',text),),False,FIXTURE_URL)
    return SearchIndex((index_document(source,'teknisk',retrieved_at='2020-01-01T00:00:00Z',
        approval_expires='2099-12-31',raw_sha256=hashlib.sha256(FIXTURE_RAW).hexdigest()),))


def fixture_fetch(approval=None, raw=FIXTURE_RAW, **changes):
    approval=approval or fixture_approval(raw)
    def fetch(source_id, *, request_id, **limits):
        if source_id!=approval.source_id:
            raise OSError('Synthetic outage')
        return PageObservation(source_id,approval.url,request_id,raw,FIXTURE_ROBOTS,**changes)
    return fetch


class RequestBoundSourceTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock
        self.calls=[]
        def transport(url,headers,body,timeout,limit):
            payload=json.loads(body);self.calls.append(payload)
            prompt=payload['messages'][-1]['content']
            p=json.loads(prompt.split('SOURCE_PARAGRAPHS=',1)[1].splitlines()[0])[0]
            return json.dumps({'message':{'content':json.dumps({'claims':[{'id':'c1','text':p['text'],
                'paragraph_id':p['id'],'evidence_quote':p['text']}]})}}).encode()
        self.client=OllamaClient(OllamaConfig(),transport=transport)
        self.approval=fixture_approval()
        self.observations=[]
        fetch=fixture_fetch()
        def observed(*args,**kwargs):
            self.observations.append((args,kwargs))
            return fetch(*args,**kwargs)
        self.policy=RequestBoundSources({self.approval.source_id:self.approval},fetcher=observed,
                                        observation_method='synthetic_mock_http')
        self.original=fixture_index()
        self.service=MunicipalWorkflowService(self.original,self.client,request_sources=self.policy)
        self.app=WebApplication(self.service)
        self.headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000',
                      'Content-Type':'application/json','X-Hamar-Token':self.app.token}
        for target in ('socket.socket','socket.getaddrinfo'):
            guard=patch(target,side_effect=AssertionError('Real network forbidden'))
            guard.start();self.addCleanup(guard.stop)
        self.addCleanup(self.drain)

    def drain(self):
        end=time.monotonic()+2
        while active_workers() and time.monotonic()<end:time.sleep(.002)
        self.assertEqual(active_workers(),0)

    def post(self,path='/api/answer',query='vann'):
        data={'source_id':self.approval.source_id} if path=='/api/run' else {'query':query}
        return self.app.dispatch('POST',path,self.headers,json.dumps(data).encode())

    def test_each_search_and_answer_observes_again_with_distinct_request_receipt(self):
        search=json.loads(self.post('/api/search').body)
        answer=json.loads(self.post().body)['answer']
        again=json.loads(self.post().body)['answer']
        receipts=[x['source_observation']['request_id'] for x in (search,answer,again)]
        self.assertEqual(len(set(receipts)),3);self.assertEqual(len(self.observations),3)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(answer['result']['claims'][0]['text'],FIXTURE_TEXT)
        self.assertEqual(answer['citations'][0]['retrieval_request_id'],receipts[1])
        self.assertIs(self.service.index,self.original)

    def test_newly_approved_content_is_used_instead_of_old_index_bytes(self):
        text='Fiktivt oppdatert testutdrag om vann. Testgebyret er 300 kroner.'
        raw=('<main><p>'+text+'</p></main>').encode()
        approval=fixture_approval(raw)
        self.service.request_sources=RequestBoundSources({approval.source_id:approval},
            fetcher=fixture_fetch(approval,raw),observation_method='synthetic_mock_http')
        response=self.post();self.assertEqual(response.status,200)
        self.assertEqual(json.loads(response.body)['answer']['result']['claims'][0]['text'],text)
        self.assertEqual(self.original.documents[approval.source_id].source.paragraphs[0].text,FIXTURE_TEXT)

    def test_changed_unapproved_body_and_robots_cannot_publish_or_call_model(self):
        for change in ('body','robots'):
            with self.subTest(change=change):
                fetch=fixture_fetch()
                self.policy.fetcher=lambda *a,**k:replace(fetch(*a,**k),**{change:b'changed synthetic bytes'})
                response=self.post()
                self.assertEqual(response.status,503)
                self.assertEqual(json.loads(response.body)['error_code'],'source_changed_review_required')
                self.assertEqual(self.calls,[]);self.assertFalse(self.app.results)
                self.assertEqual(self.app.sessions[self.app.token].topic_terms,())

    def test_outage_missing_bad_status_redirect_and_nonce_replay_are_fail_closed(self):
        fetch=fixture_fetch()
        for mode in ('outage','missing','status','redirect','nonce'):
            def broken(*args,**kwargs):
                if mode=='outage':raise OSError('Synthetic diagnostic must remain private')
                if mode=='missing':return None
                value=fetch(*args,**kwargs)
                return replace(value,**({'status':404} if mode=='status' else
                    {'url':'https://127.0.0.1/private'} if mode=='redirect' else {'request_id':'0'*32}))
            with self.subTest(mode=mode):
                self.policy.fetcher=broken;response=self.post()
                self.assertEqual(response.status,503);self.assertNotIn(b'Synthetic diagnostic',response.body)
                self.assertFalse(self.app.results);self.assertEqual(self.calls,[])

    def test_atomic_batch_failure_retains_original_index_and_no_partial_results(self):
        other=fixture_approval(source_id='offline-other',url='https://www.hamar.kommune.no/offline-other/')
        self.policy=RequestBoundSources({self.approval.source_id:self.approval,other.source_id:other},
            fetcher=fixture_fetch(),observation_method='synthetic_mock_http')
        self.service.request_sources=self.policy
        before=json.dumps([asdict(d) for d in self.original.documents.values()],sort_keys=True)
        for path in ('/api/search','/api/answer'):
            self.assertEqual(self.post(path).status,503)
        self.assertIs(self.service.index,self.original)
        self.assertEqual(json.dumps([asdict(d) for d in self.original.documents.values()],sort_keys=True),before)
        self.assertFalse(self.app.results);self.assertEqual(self.calls,[])

    def test_expiry_and_disabled_transport_fail_before_dns_without_historical_exception(self):
        for policy in (RequestBoundSources({self.approval.source_id:replace(self.approval,expires_on='2001-01-01')}),
                       RequestBoundSources({self.approval.source_id:self.approval})):
            self.service.request_sources=policy
            with patch('hamar_agent.historical_sources.retained_document',side_effect=AssertionError('No historical exception')):
                for path in ('/api/search','/api/answer','/api/run'):
                    self.assertEqual(self.post(path).status,503)
        self.assertEqual(self.calls,[]);self.assertFalse(self.app.results)

    def test_factory_production_does_not_open_catalog_or_invoke_historical_loaders(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'approvals.json'
            manifest.write_text(json.dumps([asdict(self.approval)]),encoding='utf-8')
            with patch('hamar_agent.real_sources.load_catalog',side_effect=AssertionError('No cached production corpus')), \
                 patch('hamar_agent.real_sources.load_approvals',side_effect=AssertionError('No historical approval exception')):
                service=create_municipal_service([Path(directory)/'nonexistent-catalog'],manifest,client=self.client)
            self.assertEqual(service.index.documents,{})
            with self.assertRaises(SourceRefreshError):service.run(self.approval.source_id)

    def test_provenance_keeps_three_different_dates_and_unknowns_as_unknown(self):
        self.policy.fetcher=fixture_fetch(published_at='2024-01-02',last_modified='Wed, 03 Jan 2024 12:00:00 GMT')
        record=json.loads(self.post('/api/search').body)['results'][0]
        self.assertEqual(record['published_at'],'2024-01-02')
        self.assertEqual(record['last_modified'],'2024-01-03T12:00:00+00:00')
        self.assertNotEqual(record['retrieved_at'],record['last_modified'])
        self.assertEqual(record['link_checked_at'],record['retrieved_at'])
        self.policy.fetcher=fixture_fetch()
        record=json.loads(self.post('/api/search').body)['results'][0]
        self.assertIsNone(record['published_at']);self.assertIsNone(record['last_modified'])

    def test_malformed_and_future_metadata_are_rejected_not_relabelled_as_fresh(self):
        for changes in ({'published_at':'not-a-date'},{'published_at':'2099-01-01'},
                        {'last_modified':'not-a-date'},{'last_modified':'Wed, 03 Jan 2024 12:00:00'},
                        {'last_modified':'Thu, 01 Jan 2099 12:00:00 GMT'}):
            with self.subTest(changes=changes):
                self.policy.fetcher=fixture_fetch(**changes)
                self.assertEqual(self.post('/api/search').status,503)

    def test_snapshots_reject_other_request_copied_context_and_completed_or_aborted_owner(self):
        for fail in (False,True):
            try:
                with run_scope() as owner:
                    snapshot=self.policy.retrieve();saved=copy_context()
                    snapshot.assert_publishable()
                    if fail:raise OSError('Synthetic aborted caller')
            except OSError:pass
            self.assertTrue(owner.finished)
            with self.assertRaises(SourceRefreshError):saved.run(snapshot.assert_publishable)
            with run_scope():
                with self.assertRaises(SourceRefreshError):snapshot.assert_publishable()

    def test_revoke_at_locked_publication_prevents_history_and_result_mutations(self):
        from hamar_agent import web
        checkpoint=web.checkpoint
        def revoke(stage):
            if stage=='publication':self.policy.revoke()
            checkpoint(stage)
        with patch('hamar_agent.web.checkpoint',side_effect=revoke):response=self.post()
        self.assertEqual(response.status,503);self.assertEqual(len(self.calls),1)
        self.assertFalse(self.app.results);self.assertFalse(self.app.result_owners)
        self.assertEqual(self.app.sessions[self.app.token].turns,0)

    def test_blocked_observation_abandons_caller_without_late_publication(self):
        entered=Event();release=Event();fetch=fixture_fetch()
        def blocked(*a,**k):
            entered.set();release.wait(2);return fetch(*a,**k)
        self.policy.fetcher=blocked;self.service.run_policy=RunPolicy(seconds=.04)
        start=time.perf_counter()
        try:
            response=self.post()
            self.assertTrue(entered.is_set());self.assertLess(time.perf_counter()-start,.5)
            self.assertEqual(json.loads(response.body)['error_code'],'run_deadline_exceeded')
            self.assertGreater(active_workers(),0);self.assertFalse(self.app.results);self.assertEqual(self.calls,[])
        finally:release.set()
        self.drain();self.assertFalse(self.app.results)

    def test_invalid_urls_privacy_and_scope_cannot_reach_transport(self):
        for url in ('http://www.hamar.kommune.no/a/','https://127.0.0.1/a/',
                    'https://www.hamar.kommune.no.evil.invalid/a/','https://www.hamar.kommune.no/a/?x=1',
                    'https://www.hamar.kommune.no/%2fprivate'):
            with self.subTest(url=url),self.assertRaises(ValueError):fixture_approval(url=url)
        self.assertEqual(self.post(query='synthetic@example.invalid').status,400)
        self.assertEqual(self.observations,[]);self.assertEqual(self.calls,[])

    def test_source_byte_count_and_attempt_budgets_fail_before_generation(self):
        self.policy.max_total_bytes=1
        self.assertEqual(self.post().status,503);self.assertEqual(self.calls,[])
        self.policy.max_sources=0
        self.assertEqual(self.post().status,503);self.assertEqual(len(self.observations),1)

    def test_historical_baseline_is_explicit_and_not_a_production_server_option(self):
        baseline=MunicipalWorkflowService(self.original,self.client,historical_baseline=True)
        with self.assertRaisesRegex(ValueError,'Historical evaluation'):create_server(service=baseline,port=0)
        response=self.post('/api/run')
        self.assertEqual(response.status,200)
        self.assertEqual(len(self.observations),1);self.assertEqual(len(self.calls),1)

    def test_direct_municipal_entry_points_cannot_reuse_a_previous_request(self):
        source=self.original.documents[self.approval.source_id].source
        receipts=[]
        for call in (lambda:self.service.run(source.id),lambda:self.service.run_prepared(source),
                     lambda:self.service.run_context(source)):
            result=call()
            receipts.append(result.source_provenance[0]['retrieval_request_id'])
            with run_scope(),self.assertRaises(SourceRefreshError):result.assert_publishable()
        self.assertEqual(len(set(receipts)),3)
        self.assertEqual(len(self.observations),3);self.assertEqual(len(self.calls),3)

    def test_concurrent_requests_have_private_corpora_and_independent_receipts(self):
        from threading import Barrier
        rendezvous=Barrier(2);fetch=fixture_fetch();results=[]
        def simultaneous(*a,**k):
            rendezvous.wait(timeout=1);return fetch(*a,**k)
        self.policy.fetcher=simultaneous
        tokens=(self.app.token,self.app._new_page_token())
        def answer(token):
            headers={**self.headers,'X-Hamar-Token':token}
            results.append(self.app.dispatch('POST','/api/answer',headers,b'{"query":"vann"}'))
        threads=[Thread(target=answer,args=(token,)) for token in tokens]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=2);self.assertFalse(thread.is_alive())
        self.assertEqual(len(results),2)
        self.assertTrue(all(result.status==200 for result in results))
        values=[json.loads(result.body)['answer'] for result in results]
        ids=[value['source_observation']['request_id'] for value in values]
        self.assertEqual(len(set(ids)),2)
        self.assertTrue(all(v['citations'][0]['retrieval_request_id']==v['source_observation']['request_id'] for v in values))
        self.assertIs(self.service.index,self.original)

    def test_both_provider_adapters_use_the_same_request_bound_source_control(self):
        from hamar_agent.openai_provider import OpenAIClient,OpenAIConfig
        from eval.test_provider_selection import FakeSDK
        paragraph='offline-water:p1'
        claims=json.dumps({'claims':[{'id':'c1','text':FIXTURE_TEXT,'paragraph_id':paragraph,'evidence_quote':FIXTURE_TEXT}]})
        sdk=FakeSDK(claims)
        cloud=OpenAIClient(OpenAIConfig(model='approved-model',api_key='synthetic-not-a-real-key',
            enabled=True,privacy_authorized=True),sdk_client=sdk)
        service=MunicipalWorkflowService(self.original,cloud,provider='openai',request_sources=self.policy)
        app=WebApplication(service);headers={**self.headers,'X-Hamar-Token':app.token}
        response=app.dispatch('POST','/api/answer',headers,b'{"query":"vann"}')
        self.assertEqual(response.status,200);self.assertEqual(len(sdk.responses.calls),1)
        answer=json.loads(response.body)['answer']
        self.assertEqual(answer['result']['claims'][0]['text'],FIXTURE_TEXT)
        self.assertEqual(answer['citations'][0]['retrieval_request_id'],answer['source_observation']['request_id'])

    def test_modified_snapshot_and_duplicate_manifest_fields_are_rejected(self):
        with run_scope():
            snapshot=self.policy.retrieve()
            source_id=self.approval.source_id
            snapshot.index.documents[source_id]=replace(snapshot.index.documents[source_id],published_at='2022-01-01')
            with self.assertRaises(SourceRefreshError):snapshot.assert_publishable()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad-approvals.json'
            raw=json.dumps([asdict(self.approval)]).replace('"no_personal_data": true','"no_personal_data": false, "no_personal_data": true')
            path.write_text(raw,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate'):RequestBoundSources.from_manifest(path)

    def test_extra_http_flags_cannot_enable_baseline_or_transport(self):
        for path in ('/api/search','/api/answer'):
            for key in ('historical_baseline','enable_live','request_id','source_snapshot'):
                with self.subTest(path=path,key=key):
                    data={'query':'vann',key:True}
                    self.assertEqual(self.app.dispatch('POST',path,self.headers,json.dumps(data).encode()).status,400)
        self.assertEqual(self.observations,[]);self.assertEqual(self.calls,[])

    def test_worker_held_before_admission_cannot_dispatch_after_caller_abandonment(self):
        from hamar_agent import run_control
        start=run_control._start;held=Event();release=Event()
        def queued(function,**kwargs):
            def delayed():
                held.set();release.wait(2);return function()
            return start(delayed,**kwargs)
        self.service.run_policy=RunPolicy(seconds=.04)
        try:
            with patch('hamar_agent.run_control._start',side_effect=queued):response=self.post()
            self.assertTrue(held.is_set());self.assertEqual(json.loads(response.body)['error_code'],'run_deadline_exceeded')
        finally:release.set()
        self.drain()
        self.assertEqual(self.observations,[]);self.assertEqual(self.calls,[]);self.assertFalse(self.app.results)

    def test_revocation_during_first_source_stops_second_observer_dispatch(self):
        other=fixture_approval(source_id='offline-other',url='https://www.hamar.kommune.no/offline-other/')
        observations=[]
        def fetch(source_id,**kwargs):
            observations.append(source_id)
            if source_id==self.approval.source_id:self.policy.revoke()
            approval=self.approval if source_id==self.approval.source_id else other
            return fixture_fetch(approval)(source_id,**kwargs)
        self.policy=RequestBoundSources({self.approval.source_id:self.approval,other.source_id:other},
            fetcher=fetch,observation_method='synthetic_mock_http')
        self.service.request_sources=self.policy
        response=self.post()
        self.assertEqual(response.status,503)
        self.assertEqual(observations,[self.approval.source_id]);self.assertEqual(self.calls,[])
        self.assertFalse(self.app.results)

    def test_revocation_while_worker_queued_prevents_the_first_observer_call(self):
        from hamar_agent import run_control
        start=run_control._start;held=Event();release=Event();responses=[]
        def queued(function,**kwargs):
            def delayed():
                held.set();release.wait(2);return function()
            return start(delayed,**kwargs)
        worker=Thread(target=lambda:responses.append(self.post()))
        try:
            with patch('hamar_agent.run_control._start',side_effect=queued):
                worker.start();self.assertTrue(held.wait(1));self.policy.revoke();release.set();worker.join(2)
            self.assertFalse(worker.is_alive());self.assertEqual(responses[0].status,503)
        finally:release.set();worker.join(2)
        self.drain();self.assertEqual(self.observations,[]);self.assertEqual(self.calls,[])
        self.assertFalse(self.app.results)

    def test_production_server_factory_cannot_return_a_historical_service(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from hamar_agent import web
        baseline=MunicipalWorkflowService(self.original,OllamaClient(OllamaConfig()),historical_baseline=True)
        captured=[];handler=web.make_handler
        def capture(app):
            captured.append(app);return handler(app)
        with patch('hamar_agent.web.ThreadingHTTPServer') as server,patch('hamar_agent.web.make_handler',side_effect=capture):
            server.return_value.server_port=8000
            create_server(service=self.service,service_factory=lambda *a:baseline,
                provider_registry=SimpleNamespace(require_choice=Mock()),port=8000)
        app=captured[0];headers={**self.headers,'X-Hamar-Token':app.token}
        data={'query':'vann','provider':'ollama','model':self.client.config.model}
        response=app.dispatch('POST','/api/answer',headers,json.dumps(data).encode())
        self.assertEqual(response.status,503);self.assertFalse(app.results)
        self.assertEqual(self.calls,[]);self.assertEqual(self.observations,[])

    def checker_fixture(self):
        records={'offline-water':{'url':FIXTURE_URL,'paragraphs':{'p1':FIXTURE_TEXT},
                                 'raw_sha256':'a'*64,'text_sha256':'b'*64}}
        claim={'paragraph_id':'offline-water:p1','text':FIXTURE_TEXT,'evidence_quote':FIXTURE_TEXT}
        citation={'source_id':'offline-water','paragraph_id':'offline-water:p1','url':FIXTURE_URL,
                  'raw_sha256':'a'*64,'text_sha256':'b'*64,'retrieval_request_id':'1'*32}
        return records,claim,citation

    def test_scientific_citation_checker_rejects_wrong_ids_urls_quotes_and_duplicates(self):
        from harness.request_bound_eval import exact_citation_count
        records,claim,citation=self.checker_fixture()
        self.assertEqual(exact_citation_count([claim],[citation],records),1)
        self.assertEqual(exact_citation_count([{**claim,'paragraph_id':'offline-water:p99'}],
            [{**citation,'paragraph_id':'offline-water:p99'}],records),0)
        for change in ({'url':'https://example.invalid/'},{'source_id':'unknown'},{'raw_sha256':'c'*64}):
            self.assertEqual(exact_citation_count([claim],[{**citation,**change}],records),0)
        self.assertEqual(exact_citation_count([{**claim,'evidence_quote':'Wrong quote'}],[citation],records),0)
        self.assertEqual(exact_citation_count([claim,claim],[citation],records),0)

    def test_scientific_proof_checker_rejects_vacuous_or_foreign_receipts(self):
        from harness.request_bound_eval import request_bound_proof
        records,claim,citation=self.checker_fixture()
        receipt={'policy':'request_bound','request_id':'1'*32,'sources':1,'source_attempts':1,
                 'received_bytes':10,'corpus_sha256':'d'*64}
        observation={'source_id':'offline-water','request_id':'1'*32,'returned_request_id':'1'*32,
                     'received_bytes':10,'status':200,'url':FIXTURE_URL,'body_sha256':'a'*64,'outcome':'mock_http_response'}
        check=lambda claims,citations,r,obs:request_bound_proof(claims,citations,r,[receipt],obs,records)
        self.assertTrue(check([claim],[citation],receipt,[observation]))
        self.assertFalse(check([],[],receipt,[observation]))
        self.assertFalse(check([claim],[],receipt,[observation]))
        self.assertFalse(check([claim],[citation],{**receipt,'corpus_sha256':'f'*64},[observation]))
        self.assertFalse(check([claim],[citation],receipt,[{**observation,'request_id':'2'*32}]))
        self.assertFalse(check([claim],[citation],receipt,[{**observation,'body_sha256':'f'*64}]))

    def test_scientific_exit_and_rejection_predicates_enforce_status_and_dispatch(self):
        from harness.request_bound_eval import behavior_passed,campaign_valid
        expectation={'http_status':503,'error_code':'source_unavailable','answer_status':None,
                     'source_attempts':1,'model_calls':0,'published':False}
        row={**expectation,'expected_behavior':expectation,'budget_compliant':True,
             'workers_after_release':0,'shared_index_unchanged':True,'architecture':'request_bound',
             'case_contract_passed':True,'behavior_checks_passed':True}
        self.assertTrue(behavior_passed(row));self.assertTrue(campaign_valid([row],[]))
        self.assertFalse(behavior_passed({**row,'http_status':500}))
        self.assertFalse(behavior_passed({**row,'model_calls':1}))
        self.assertFalse(campaign_valid([{**row,'case_contract_passed':False}],[]))
        self.assertTrue(campaign_valid([{**row,'architecture':'historical_index','case_contract_passed':False}],[]))
        self.assertFalse(campaign_valid([{**row,'architecture':'historical_index','behavior_checks_passed':False}],[]))

    def test_scientific_metrics_separate_safe_rejection_from_task_withholding(self):
        from harness.request_bound_eval import _metrics
        positive={'case_id':'positive','provider':'mock','phase':'primary','expected_action':'publish',
            'published':True,'content_correct':True,'claims':1,'valid_exact_citations':1,'same_request_source_proof':True,
            'source_attempts':1,'source_snapshot_ready':True,'source_observation_required':True,'model_calls':1,
            'budget_compliant':True,'http_status':200,'error_code':None,'answer_status':'evidence_checked',
            'query_answerable_from_current_fixture':True,'task_completed':True,'case_contract_passed':True,
            'behavior_checks_passed':True,'response_latency_ms':2.0}
        refused={**positive,'case_id':'safe_refusal','expected_action':'reject','published':False,
            'claims':0,'valid_exact_citations':0,'same_request_source_proof':False,'content_correct':False,'task_completed':False}
        values=_metrics([positive,refused])
        self.assertEqual(values['policy_decision_confusion'],{'TP':1,'FN':0,'FP':0,'TN':1,'n':2,'limitation':'Against declared expected_action; content correctness is separate'})
        self.assertEqual(values['false_rejection_rate'],0)
        self.assertEqual(values['answerable_task_withheld_rate'],50)
        self.assertEqual(values['task_completion_rate'],50)
        self.assertIsNone(_metrics([])['case_pass_rate'])

    def test_scientific_comparison_detects_stale_content_and_preserves_one_claim_guard(self):
        from harness.request_bound_eval import CASES,experiment
        case=next(c for c in CASES if c['id']=='changed_approved')
        old,_=experiment(case,'historical_index','ollama_mock',0)
        new,_=experiment(case,'request_bound','ollama_mock',0)
        self.assertTrue(old['behavior_checks_passed']);self.assertFalse(old['content_correct'])
        self.assertFalse(old['case_contract_passed']);self.assertTrue(new['case_contract_passed'])
        self.assertTrue(new['same_request_source_proof'])
        case=next(c for c in CASES if c['id']=='multiple_model_claims')
        rejected,_=experiment(case,'request_bound','ollama_mock',0)
        self.assertEqual(rejected['model_calls'],1)
        self.assertEqual(rejected['error_code'],'provider_response_invalid')
        self.assertTrue(rejected['case_contract_passed'])

    def test_scientific_byte_transcript_counts_the_actual_changed_robots_payload(self):
        from harness.request_bound_eval import CASES,experiment
        case=next(c for c in CASES if c['id']=='source_robots_changed')
        row,_=experiment(case,'request_bound','ollama_mock',0)
        self.assertEqual(row['source_observations'][0]['received_bytes'],len(FIXTURE_RAW)+len(b'User-agent: *\nDisallow: /'))
        self.assertEqual(row['source_observations'][0]['received_bytes'],99)
        self.assertFalse(row['source_snapshot_ready']);self.assertTrue(row['case_contract_passed'])



if __name__ == "__main__":
    unittest.main()
