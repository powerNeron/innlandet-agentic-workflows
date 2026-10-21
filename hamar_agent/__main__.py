"""Read a synthetic fixture and print mock claims to stdout."""
import argparse
from pathlib import Path
from .sources import load_fixture  # Preserve the original import entry point.
from .summarize import MockSummarizer
from .workflow import run_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = load_fixture(args.fixture)
        result = run_workflow(
            source.id, MockSummarizer(), provider="mock", loader=lambda _: source,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(2, f"Invalid synthetic fixture: {exc}\n")
    print(result.to_json(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
