"""Offline scorecard for known synthetic verifier cases (not semantic truth)."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hamar_agent.sources import load_source
from hamar_agent.summarize import MockScenario, MockSummarizer
from hamar_agent.verify import verify_response


SOURCE_ID = "synthetic-verification-demo"
EXPECTED = {
    MockScenario.MISSING_CITATION: "missing_citation",
    MockScenario.INVALID_PARAGRAPH: "invalid_paragraph_id",
    MockScenario.FABRICATED_QUOTE: "fabricated_evidence",
    MockScenario.CHANGED_NUMBER: "unsupported_number",
    MockScenario.UNSUPPORTED_STATEMENT: "potentially_unsupported",
    MockScenario.UNCERTAIN_CLAIM: "uncertain_claim",
    MockScenario.CONFLICTING_CLAIMS: "conflicting_claims",
    MockScenario.MALFORMED_OUTPUT: "malformed_output",
}


def main() -> int:
    source = load_source(SOURCE_ID)
    cases = []
    for scenario, expected in EXPECTED.items():
        report = verify_response(source, MockSummarizer(scenario).response_payload(source))
        detected = expected in {finding.code.value for finding in report.findings}
        cases.append({"scenario": scenario.value, "expected_finding": expected, "detected": detected})
    detected_count = sum(case["detected"] for case in cases)
    print(json.dumps({
        "source_id": SOURCE_ID,
        "known_issue_cases": len(cases),
        "expected_issue_detection_rate": round(detected_count / len(cases), 3),
        "cases": cases,
        "limitation": "Synthetic injected-error detection only; not a measure of model quality, semantic entailment, or truth.",
    }, ensure_ascii=False, indent=2))
    return 0 if detected_count == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
