"""Read a synthetic fixture and print mock claims to stdout."""
import argparse
import json
from pathlib import Path
from .schemas import Paragraph, Result, Source
from .summarize import MockSummarizer


def load_fixture(path: Path) -> Source:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture must be a JSON object")
    if data.get("synthetic") is not True:
        raise ValueError("fixture must be explicitly labeled synthetic: true")
    if data.get("url") is not None:
        raise ValueError("synthetic fixtures must not identify a live source URL")
    return Source(
        id=data["id"], title=data["title"], synthetic=True,
        paragraphs=tuple(Paragraph(**p) for p in data["paragraphs"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = load_fixture(args.fixture)
        result = Result(source, MockSummarizer().summarize(source))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Invalid synthetic fixture: {exc}\n")
    print(result.to_json(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
