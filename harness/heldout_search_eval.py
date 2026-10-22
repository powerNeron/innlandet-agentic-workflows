"""Run the separately stored synthetic search/citation holdout case offline."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hamar_agent.application import WorkflowService
from hamar_agent.portal import PortalService
from hamar_agent.schemas import Paragraph, Source
from hamar_agent.search import SearchIndex, index_document


CASE_FILE = Path(__file__).resolve().parents[1] / "eval" / "heldout" / "hamar-search-case.json"


def evaluate(case_path: Path = CASE_FILE) -> dict:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    if case.get("synthetic") is not True or not case.get("case_id"):
        raise ValueError("Holdout case must be explicitly synthetic and identified")
    docs = []
    for item in case["documents"]:
        source = Source(item["id"], item["title"],
                        tuple(Paragraph(p["id"], p["text"]) for p in item["paragraphs"]), True)
        docs.append(index_document(source, item["category"]))

    index = SearchIndex(docs)
    workflow = WorkflowService(provider="mock")
    portal = PortalService(workflow, index=index)
    hits = index.search(case["query"])
    answer = portal.answer(case["query"])
    unsupported = portal.answer(case["unsupported_query"])
    passed = bool(hits and hits[0].document.source.id == case["expected_source_id"]
                  and answer["answer_status"] == "demo"
                  and any(c["paragraph_id"] == case["expected_paragraph_id"] for c in answer["citations"])
                  and unsupported["answer_status"] == "insufficient_evidence"
                  and unsupported["result"] is None)
    return {
        "case_id": case["case_id"],
        "synthetic": True,
        "provider": "mock",
        "passed": passed,
        "top_source_id": hits[0].document.source.id if hits else None,
        "answer_status": answer["answer_status"],
        "citation_paragraph_ids": [c["paragraph_id"] for c in answer["citations"]],
        "unsupported_status": unsupported["answer_status"],
        "limitation": case["limitation"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new, exclusive JSON evidence file")
    args = parser.parse_args(argv)
    result = evaluate()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
