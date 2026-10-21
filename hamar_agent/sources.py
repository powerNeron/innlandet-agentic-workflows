"""Explicit, local-only approvals. No URL fetching or automatic approval."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .schemas import Paragraph, Source


@dataclass(frozen=True)
class SourceApproval:
    source_id: str
    path: Path
    sha256: str
    rationale: str


_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "water-synthetic.json"
APPROVED_SOURCES: Mapping[str, SourceApproval] = MappingProxyType({
    "synthetic-water-demo": SourceApproval(
        "synthetic-water-demo", _FIXTURE,
        "b7b501132edcc07221b4f5e73089d1569bd34d8e205b51f0a5616803df310ab1",
        "Reviewed fictional, non-personal fixture; not Hamar municipal facts.",
    ),
})
MAX_FIXTURE_BYTES = 64 * 1024


def load_source(
    source_id: str, *, registry: Mapping[str, SourceApproval] = APPROVED_SOURCES,
) -> Source:
    """Resolve approval before opening a file; registry is trusted configuration."""
    if source_id not in registry:
        raise ValueError("source is not approved")
    approval = registry[source_id]
    if approval.source_id != source_id:
        raise ValueError("source approval ID mismatch")
    # Bound memory use; the reviewed digest must match before decoding/parsing.
    with approval.path.open("rb") as stream:
        raw = stream.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES:
        raise ValueError("approved fixture exceeds size limit")
    if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != approval.sha256:
        raise ValueError("fixture content changed; review and approval required")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture must be a JSON object")
    if data.get("synthetic") is not True:
        raise ValueError("fixture must be explicitly labeled synthetic: true")
    if data.get("url") is not None:
        raise ValueError("synthetic fixtures must not identify a live source URL")
    if data.get("id") != source_id:
        raise ValueError("fixture source ID does not match approval")
    if not isinstance(data.get("paragraphs"), list):
        raise ValueError("fixture paragraphs must be a list")
    return Source(
        id=data["id"], title=data["title"], synthetic=True,
        paragraphs=tuple(Paragraph(**p) for p in data["paragraphs"]),
    )


def load_fixture(
    path: Path, *, registry: Mapping[str, SourceApproval] = APPROVED_SOURCES,
) -> Source:
    """Compatibility path entry point: reject unapproved paths before reading."""
    requested = Path(path).resolve()
    for source_id, approval in registry.items():
        if requested == approval.path.resolve():
            return load_source(source_id, registry=registry)
    raise ValueError("fixture path is not approved")
