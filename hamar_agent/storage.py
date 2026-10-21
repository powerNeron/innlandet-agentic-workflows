"""Save result JSON without replacing existing filesystem entries."""
from pathlib import Path

from .schemas import Result


def save_result(result: Result, destination: Path) -> Path:
    """Serialize before exclusive creation; require an existing parent directory.

    A failed write may leave a partial new file. Never remove or replace it here.
    Saving preserves evidence status and does not establish factual correctness.
    """
    payload = result.to_json()
    # Pre-encode too: serialization/encoding failures must not create a file.
    payload.encode("utf-8")
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    return destination
