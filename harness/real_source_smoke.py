"""Opt-in local Ollama smoke over the already approved municipal catalog."""
import argparse
import json
from pathlib import Path
import socket
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
    service=create_municipal_service([args.catalog],args.approvals,model="llama3.2:3b",timeout=90)
    with patch.object(socket.socket,"connect",local_only):
        for source in service.sources():
            started=time.monotonic()
            try:
                result=service.run(source["id"])
                assert not result.source.synthetic and result.provider=="ollama:llama3.2:3b"
                assert not result.verification.has_findings
                assert all(c.text==c.evidence_quote==next(p.text for p in result.source.paragraphs if p.id==c.paragraph_id) for c in result.claims)
                save_result(result,args.output/(source["id"]+".json"))
                rows.append({"source":source["id"],"pass":True,"claims":len(result.claims),"corrections":result.correction.attempts,"seconds":round(time.monotonic()-started,3)})
            except (OSError,RuntimeError,ValueError,AssertionError):
                rows.append({"source":source["id"],"pass":False,"seconds":round(time.monotonic()-started,3)})
        portal=PortalService(service)
        for query in ("vanntrykk","parkering","SFO","bibliotek","luftkvalitet"):
            started=time.monotonic()
            try:
                answer=portal.answer(query)
                assert answer["answer_status"]=="evidence_checked" and answer["result"] is not None
                assert answer["citations"] and all(c["url"].startswith("https://www.hamar.kommune.no/") for c in answer["citations"])
                with (args.output/("search-"+query+".json")).open("x",encoding="utf-8") as stream:json.dump(answer,stream,ensure_ascii=False,indent=2)
                rows.append({"query":query,"pass":True,"claims":len(answer["result"]["claims"]),"seconds":round(time.monotonic()-started,3)})
            except (OSError,RuntimeError,ValueError,AssertionError):rows.append({"query":query,"pass":False,"seconds":round(time.monotonic()-started,3)})
    summary={"provider":"ollama:llama3.2:3b","real_model":True,"tests":len(rows),"passing":sum(row["pass"] for row in rows),"rows":rows}
    with (args.output/"summary.json").open("x",encoding="utf-8") as stream:json.dump(summary,stream,ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False))
    return 0 if all(row["pass"] for row in rows) else 1


if __name__=="__main__":raise SystemExit(main())
