"""Application wiring uses the actual Ollama classes with offline fake transport."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch

from hamar_agent.__main__ import main
from hamar_agent.correction import CorrectionResult
from hamar_agent.ollama_provider import OllamaClient, OllamaConfig, OllamaError, OllamaSummarizer
from hamar_agent.portal import PortalService
from hamar_agent.runtime import create_service, structured_transport
from hamar_agent.schemas import Claim
from hamar_agent.sources import load_source
from hamar_agent.verify import FindingCode, VerificationFinding
from hamar_agent.web import WebApplication
from hamar_agent.workflow import run_workflow

SOURCE_ID="synthetic-verification-demo"


def envelope(claims):
    return json.dumps({"message":{"content":json.dumps({"claims":claims})}}).encode()


def echo_transport(url,headers,body,timeout,limit):
    prompt=json.loads(body)["messages"][0]["content"]
    if "SOURCE_PARAGRAPHS=" in prompt:
        paragraphs=json.loads(prompt.split("SOURCE_PARAGRAPHS=",1)[1].splitlines()[0])
        id,text=paragraphs[0]["id"],paragraphs[0]["text"]
    else:
        id,text=re.search(r"^\[([^\]]+)\] (.+)$",prompt,re.M).groups()
    return envelope([{"id":"c1","text":text,"paragraph_id":id,"evidence_quote":text}])


class RuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket","socket.create_connection"):
            guard=patch(target,side_effect=AssertionError("real network/paid APIs forbidden"))
            guard.start();self.addCleanup(guard.stop)
        self.source=load_source(SOURCE_ID)

    def service(self,transport=echo_transport,**kwargs):
        client=OllamaClient(OllamaConfig(),transport=structured_transport(transport))
        return create_service("ollama",client=client,**kwargs)

    def test_default_factory_is_offline_mock(self):
        result=create_service().run(SOURCE_ID)
        self.assertEqual(result.provider,"mock")
        self.assertFalse(result.verification.has_findings)

    def test_factory_uses_actual_summarizer_and_client(self):
        service=self.service()
        self.assertIsInstance(service.summarizer,OllamaSummarizer)
        result=service.run(SOURCE_ID)
        self.assertEqual(result.provider,"ollama:llama3.2:3b")
        self.assertEqual(result.claims[0].paragraph_id,"p1")
        self.assertFalse(result.verification.has_findings)

    def test_schema_wrapper_retains_transport_limits_and_provider_options(self):
        base=Mock(side_effect=echo_transport)
        self.service(base).run(SOURCE_ID)
        url,headers,body,timeout,limit=base.call_args.args
        payload=json.loads(body)
        self.assertEqual(url,"http://127.0.0.1:11434/api/chat")
        self.assertEqual(payload["format"]["properties"]["claims"]["items"]["properties"]["paragraph_id"]["type"],"string")
        self.assertEqual(payload["options"]["temperature"],0)
        self.assertEqual(timeout,45)
        self.assertEqual(limit,128000)

    def test_actual_correction_provider_is_called_once_and_reverified(self):
        source=self.source
        bad={"id":"c1","text":"A fictional claim","paragraph_id":"p999","evidence_quote":"Invented"}
        transport=Mock(side_effect=[envelope([bad]),echo_transport("",{},json.dumps({"messages":[{"content":"[p1] "+source.paragraphs[0].text}]}).encode(),0,0)])
        result=self.service(transport).run(SOURCE_ID)
        self.assertEqual(transport.call_count,2)
        self.assertIn(b"SOURCE_PARAGRAPHS",transport.call_args.args[2])
        self.assertEqual(result.correction.attempts,1)
        self.assertEqual(result.correction.provider,"ollama")
        self.assertTrue(result.correction.initial_findings)
        self.assertFalse(result.verification.has_findings)

    def test_structured_correction_provider_findings_are_not_lost(self):
        from hamar_agent.summarize import MockSummarizer, MockScenario
        extra=VerificationFinding(FindingCode.UNCERTAIN_CLAIM,"Provider review required",("c1",))
        clean=MockSummarizer().summarize(self.source)
        callback=Mock(return_value=CorrectionResult(clean,(extra,),"injected-corrector"))
        result=run_workflow(SOURCE_ID,MockSummarizer(MockScenario.INVALID_PARAGRAPH),provider="test",corrector=callback)
        self.assertEqual(result.correction.provider_findings,(extra,))
        self.assertIn(extra,result.verification.findings)
        self.assertIn("Review required"," ".join(result.warnings))

    def test_unresolved_real_correction_is_bounded(self):
        bad={"id":"c1","text":"Fictional","paragraph_id":"p999","evidence_quote":"Invented"}
        transport=Mock(return_value=envelope([bad]))
        result=self.service(transport).run(SOURCE_ID)
        self.assertEqual(transport.call_count,2)
        self.assertTrue(result.verification.has_findings)
        self.assertEqual(result.correction.attempts,1)

    def test_model_unavailable_never_silently_falls_back(self):
        transport=Mock(side_effect=OllamaError("unavailable"))
        with self.assertRaises(OllamaError):self.service(transport).run(SOURCE_ID)
        self.assertEqual(transport.call_count,1)

    def test_explicit_fallback_is_labeled_and_warning_preserved(self):
        transport=Mock(side_effect=OllamaError("unavailable"))
        result=self.service(transport,fallback_to_mock=True).run(SOURCE_ID)
        self.assertEqual(result.provider,"mock:fallback-from-ollama:llama3.2:3b")
        self.assertIn("not real LLM output"," ".join(result.warnings))
        self.assertEqual(transport.call_count,1)

    def test_correction_failure_retains_real_provider_and_original_claims(self):
        bad={"id":"c1","text":"Fictional","paragraph_id":"p999","evidence_quote":"Invented"}
        transport=Mock(side_effect=[envelope([bad]),OllamaError("failure")])
        result=self.service(transport,fallback_to_mock=True).run(SOURCE_ID)
        self.assertTrue(result.provider.startswith("ollama:"))
        self.assertEqual(result.correction.status,"failed")
        self.assertTrue(result.correction.initial_findings)

    def test_new_jesper_findings_are_preserved(self):
        text=self.source.paragraphs[0].text
        transport=Mock(return_value=envelope([{"id":"c1","text":"Usikkert: "+text,"paragraph_id":"p1","evidence_quote":text}]))
        result=self.service(transport).run(SOURCE_ID)
        self.assertIn("uncertain_claim",{f.code.value for f in result.verification.findings})

    def test_cli_provider_flags_route_to_real_service_and_save_json(self):
        service=self.service()
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"result.json"
            with patch("hamar_agent.runtime.create_service",return_value=service) as factory,redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["--source",SOURCE_ID,"--provider","ollama","--model","llama3.2:3b","--output",str(output)]),0)
            self.assertEqual(factory.call_args.args,("ollama",))
            self.assertEqual(output.read_text(encoding="utf-8"),stdout.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())["provider"],"ollama:llama3.2:3b")

    def test_cli_strict_provider_error_produces_no_result(self):
        service=self.service(Mock(side_effect=OllamaError("unavailable")))
        with patch("hamar_agent.runtime.create_service",return_value=service),redirect_stdout(io.StringIO()) as stdout,redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as raised:
            main(["--source",SOURCE_ID,"--provider","ollama"])
        self.assertEqual(raised.exception.code,2)
        self.assertEqual(stdout.getvalue(),"")

    def test_portal_uses_actual_provider_and_correct_citation_ids(self):
        answer=PortalService(self.service()).answer("vann")
        self.assertEqual(answer["answer_status"],"evidence_checked")
        self.assertTrue(answer["result"]["provider"].startswith("ollama:"))
        self.assertIn(answer["result"]["claims"][0]["paragraph_id"],{c["paragraph_id"] for c in answer["citations"]})
        self.assertNotIn("mock",answer["message"])

    def test_portal_explicit_mock_fallback_is_honest(self):
        answer=PortalService(self.service(Mock(side_effect=OllamaError("unavailable")),fallback_to_mock=True)).answer("vann")
        self.assertEqual(answer["answer_status"],"demo")
        self.assertIn("mock",answer["message"])
        self.assertTrue(answer["result"]["provider"].startswith("mock:"))

    def test_web_run_answer_and_download_share_provider(self):
        app=WebApplication(self.service())
        headers={"Host":"127.0.0.1:8000","Origin":"http://127.0.0.1:8000","Content-Type":"application/json","X-Hamar-Token":app.token}
        run=json.loads(app.dispatch("POST","/api/run",headers,json.dumps({"source_id":SOURCE_ID}).encode()).body)
        self.assertTrue(run["result"]["provider"].startswith("ollama:"))
        response=app.dispatch("POST","/api/answer",headers,b'{"query":"vann"}')
        self.assertEqual(response.status,200)
        answer=json.loads(response.body)
        download=app.dispatch("GET","/api/results/"+answer["run_id"],headers)
        self.assertEqual(json.loads(download.body),answer["answer"])

    def test_server_startup_selects_provider_without_network_in_tests(self):
        from hamar_agent.web import main as web_main
        service=self.service()
        with patch("hamar_agent.runtime.create_service",return_value=service),patch("hamar_agent.web.create_server") as server,redirect_stdout(io.StringIO()):
            server.return_value.__enter__.return_value.serve_forever.side_effect=KeyboardInterrupt
            self.assertEqual(web_main(["--provider","ollama","--model","llama3.2:3b","--empty-index"]),0)
            self.assertIs(server.call_args.kwargs["service"],service)
            self.assertIs(server.call_args.kwargs["portal"].workflow,service)

    def test_invalid_provider_settings_fail_before_inference(self):
        with self.assertRaises(ValueError):create_service("unknown")
        with self.assertRaises(ValueError):create_service("mock",fallback_to_mock=True)
        with self.assertRaises(ValueError):create_service("ollama",timeout=999)
