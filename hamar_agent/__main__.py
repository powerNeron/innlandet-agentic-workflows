"""Read a synthetic fixture and print mock claims to stdout."""
import argparse
from pathlib import Path
from .sources import load_fixture  # Preserve the original import entry point.
from .summarize import MockSummarizer
from .workflow import run_workflow  # Retained import for existing callers.
from .application import WorkflowService
from .storage import save_result


def main(argv: list[str] | None = None, *, service: WorkflowService | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fixture", type=Path)
    inputs.add_argument("--source", help="Approved synthetic source ID")
    parser.add_argument("--output", type=Path, help="Save JSON to a new file; parent must exist")
    parser.add_argument("--provider", choices=("mock", "ollama"), default="mock")
    parser.add_argument("--model", help="Installed Ollama model; never downloaded automatically")
    parser.add_argument("--ollama-timeout", type=float, default=45.0)
    parser.add_argument("--fallback-to-mock", action="store_true", help="Explicit, labeled fallback on Ollama failure")
    args = parser.parse_args(argv)
    try:
        if service is None:
            if args.provider == "mock" and not args.fallback_to_mock:
                service = WorkflowService(summarizer=MockSummarizer(), provider="mock")
            else:
                from .runtime import create_service
                service = create_service(args.provider, model=args.model, timeout=args.ollama_timeout,
                                         fallback_to_mock=args.fallback_to_mock)
        result = (service.run_prepared(load_fixture(args.fixture)) if args.fixture is not None
                  else service.run(args.source))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(2, f"Invalid synthetic fixture: {exc}\n")
    try:
        if args.output is not None:
            save_result(result, args.output)
        payload = result.to_json()
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        parser.exit(2, f"Unable to save or serialize result: {exc}\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
