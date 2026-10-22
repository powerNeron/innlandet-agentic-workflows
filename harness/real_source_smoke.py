"""Opt-in local Ollama smoke over the already approved municipal catalog."""
import argparse
import json
import math
from pathlib import Path
import socket
import statistics
import time
from unittest.mock import patch

from hamar_agent.real_sources import create_municipal_service
from hamar_agent.portal import PortalService
from hamar_agent.storage import save_result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-local-llm",action="store_true")
    parser.add_argument("--catalog",type=Path,default=Path("output/municipal-catalog.json"))
    parser.add_argument("--approvals",type=Path,default=Path("docs/approved-service-pages.json"))
    parser.add_argument("--output",type=Path,required=True,help="New directory for actual run evidence")
    args=parser.parse_args(argv)
    if not args.enable_local_llm:parser.error("Explicit --enable-local-llm required")
    args.output.mkdir(exist_ok=False)
    original=socket.socket.connect
    def local_only(sock,address):
        if address[0]!="127.0.0.1" or address[1]!=11434:raise AssertionError("External/paid APIs forbidden in local smoke")
        return original(sock,address)
    rows=[]
    latency_samples=[]
    service=create_municipal_service([args.catalog],args.approvals,model="llama3.2:3b",timeout=90)
    with patch.object(socket.socket,"connect",local_only):
        for source in service.sources():
            started=time.monotonic()
            try:
                result=service.run(source["id"])
                assert not result.source.synthetic and result.provider=="ollama:llama3.2:3b"
                assert not result.verification.has_findings
                assert all(c.text==c.evidence_quote==next(p.text for p in result.source.paragraphs if p.id==c.paragraph_id) for c in result.claims)
                assert result.source_provenance and all(item["url"].startswith("https://www.hamar.kommune.no/") for item in result.source_provenance)
                save_result(result,args.output/(source["id"]+".json"))
                latency=getattr(result,"provider_latency_ms",None)
                if latency is not None:latency_samples.append(int(latency))
                rows.append({"case":"source:"+source["id"],"pass":True,"claims":len(result.claims),"grounded_claims":len(result.claims),"citations_valid":True,"corrections":result.correction.attempts,"provider_latency_ms":latency,"seconds":round(time.monotonic()-started,3)})
            except (OSError,RuntimeError,ValueError,AssertionError):
                rows.append({"case":"source:"+source["id"],"pass":False,"seconds":round(time.monotonic()-started,3)})
        portal=PortalService(service)
        search_results={}
        queries=("vanntrykk","parkering","SFO","bibliotek","luftkvalitet","SFO")
        for ordinal,query in enumerate(queries):
            started=time.monotonic()
            try:
                answer=portal.answer(query)
                assert answer["answer_status"]=="evidence_checked" and answer["result"] is not None
                assert answer["citations"] and all(c["url"].startswith("https://www.hamar.kommune.no/") for c in answer["citations"])
                claims=answer["result"]["claims"]
                citation_paragraphs={c["paragraph_id"] for c in answer["citations"]}
                assert all(claim["paragraph_id"] in citation_paragraphs for claim in claims)
                assert all(claim["evidence_status"]=="exact_match" for claim in claims)
                latency=answer.get("provider_latency_ms")
                if latency is not None:latency_samples.append(int(latency))
                signature=tuple((c["paragraph_id"],c["text"],c["evidence_quote"]) for c in claims)
                if query=="SFO":
                    if query in search_results:
                        assert signature==search_results[query],"Repeated SFO query changed its verified claim/citation signature"
                        case="consistency:SFO-repeat"
                    else:
                        search_results[query]=signature
                        case="search:SFO"
                else:case="search:"+query
                if case!="consistency:SFO-repeat":
                    with (args.output/("search-"+query+".json")).open("x",encoding="utf-8") as stream:json.dump(answer,stream,ensure_ascii=False,indent=2)
                rows.append({"case":case,"pass":True,"claims":len(claims),"grounded_claims":len(claims),"citations_valid":True,"provider_latency_ms":latency,"seconds":round(time.monotonic()-started,3)})
            except (OSError,RuntimeError,ValueError,AssertionError):rows.append({"case":"search:"+query,"pass":False,"seconds":round(time.monotonic()-started,3)})
        phrase_cases=(
            ("Hvem får gratis SFO-tid i Hamar?","evidence_checked","hamar-sfo"),
            ("Hva gjelder for gratis SFO?","evidence_checked","hamar-sfo"),
            ("Hvordan søker jeg om SFO?","insufficient_evidence","hamar-sfo"),
            ("Hva kan jeg bygge uten å søke?","evidence_checked","hamar-byggesak"),
            ("Bygge uten søknad","evidence_checked","hamar-byggesak"),
            ("Hvordan søker jeg om byggetillatelse?","insufficient_evidence","hamar-byggesak"),
            ("Hva koster parkering i Hamar?","insufficient_evidence","hamar-parkering"),
        )
        for ordinal,(query,expected,source_id) in enumerate(phrase_cases,1):
            started=time.monotonic()
            try:
                with patch.object(service.summarizer,"summarize",wraps=service.summarizer.summarize) as generation:
                    answer=portal.answer(query)
                assert answer["answer_status"]==expected and source_id in {c["source_id"] for c in answer["citations"]}
                assert all(c["url"].startswith("https://www.hamar.kommune.no/") for c in answer["citations"])
                if expected=="insufficient_evidence":
                    assert answer["result"] is None and generation.call_count==0
                else:
                    result=answer["result"]
                    assert result["provider"]=="ollama:llama3.2:3b" and not result["verification"]["findings"]
                    assert result["correction"]["attempts"]<=1
                    citation_ids={c["paragraph_id"] for c in answer["citations"]}
                    paragraphs={p.id:p.text for p in service.index.documents[source_id].source.paragraphs}
                    assert result["claims"] and all(c["paragraph_id"] in citation_ids and c["text"]==c["evidence_quote"]==paragraphs[c["paragraph_id"].split(":",1)[1]] for c in result["claims"])
                    latency=answer.get("provider_latency_ms")
                    if latency is not None:latency_samples.append(int(latency))
                with (args.output/f"question-{ordinal}.json").open("x",encoding="utf-8") as stream:json.dump(answer,stream,ensure_ascii=False,indent=2)
                rows.append({"case":f"required-question:{ordinal}","pass":True,"expected_status":expected,
                             "answer_status":answer["answer_status"],"source_id":source_id,
                             "ollama_invoked":bool(generation.call_count),"claims":len((answer.get("result") or {}).get("claims",[])),
                             "citations_valid":True,"provider_latency_ms":answer.get("provider_latency_ms"),
                             "seconds":round(time.monotonic()-started,3)})
            except (OSError,RuntimeError,ValueError,AssertionError,KeyError,TypeError):
                rows.append({"case":f"required-question:{ordinal}","pass":False,"expected_status":expected,
                             "source_id":source_id,"seconds":round(time.monotonic()-started,3)})
        started=time.monotonic()
        try:
            with patch.object(service.summarizer,"summarize",wraps=service.summarizer.summarize) as generation:
                privacy=portal.answer("Synthetic Example lives at Example Street 12")
            assert privacy["answer_status"]=="input_rejected" and privacy["query"]=="" and not privacy["citations"] and generation.call_count==0
            rows.append({"case":"privacy:synthetic-personal-input","pass":True,"answer_status":privacy["answer_status"],
                         "ollama_invoked":False,"citations_valid":True,"seconds":round(time.monotonic()-started,3)})
        except (OSError,RuntimeError,ValueError,AssertionError):
            rows.append({"case":"privacy:synthetic-personal-input","pass":False,"seconds":round(time.monotonic()-started,3)})
        started=time.monotonic()
        try:
            refusal=portal.answer("service")
            assert refusal["answer_status"]=="insufficient_evidence" and refusal["result"] is None and not refusal["citations"]
            rows.append({"case":"refusal:insufficient-evidence","pass":True,"answer_status":refusal["answer_status"],"claims":0,"citations_valid":True,"seconds":round(time.monotonic()-started,3)})
        except (OSError,RuntimeError,ValueError,AssertionError):rows.append({"case":"refusal:insufficient-evidence","pass":False,"seconds":round(time.monotonic()-started,3)})
    ordered=sorted(latency_samples)
    p95=ordered[max(0,math.ceil(.95*len(ordered))-1)] if ordered else None
    summary={"provider":"ollama:llama3.2:3b","real_model":True,"tests":len(rows),"passing":sum(row["pass"] for row in rows),
             "grounded_claims":sum(row.get("grounded_claims",0) for row in rows),
             "citation_checks_passed":sum(row.get("citations_valid",False) for row in rows),
             "insufficient_evidence_refusals":sum(row.get("answer_status")=="insufficient_evidence" for row in rows),
             "consistency_cases":sum(row.get("case")=="consistency:SFO-repeat" for row in rows),
             "provider_latency_ms":{"n":len(ordered),"median":statistics.median(ordered) if ordered else None,"p95_nearest_rank":p95,"min":min(ordered) if ordered else None,"max":max(ordered) if ordered else None},
             "limitations":["This measures exact excerpt grounding and one repeated SFO answer, not semantic factual accuracy or human-rated relevance.","Small sequential sample; no concurrent Ollama load or accuracy confidence interval."],"rows":rows}
    with (args.output/"summary.json").open("x",encoding="utf-8") as stream:json.dump(summary,stream,ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if all(row["pass"] for row in rows) else 1


if __name__=="__main__":raise SystemExit(main())
