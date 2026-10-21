"""Read a synthetic fixture and print mock claims to stdout."""
import argparse
from pathlib import Path
from .sources import load_fixture  # Preserve the original import entry point.
from .summarize import MockSummarizer
from .workflow import run_workflow
from .storage import save_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Save JSON to a new file; parent must exist")
    args = parser.parse_args(argv)
    try:
        source = load_fixture(args.fixture)
        result = run_workflow(
            source.id, MockSummarizer(), provider="mock", loader=lambda _: source,
        )
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
