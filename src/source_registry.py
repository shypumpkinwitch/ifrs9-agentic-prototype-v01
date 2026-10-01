from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schemas import Candidate, DataValidationError, EvidenceChunk, GuidanceLink


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _require_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise DataValidationError(f"{label} must contain a JSON list.")
    if not all(isinstance(item, dict) for item in payload):
        raise DataValidationError(f"Every {label} item must be a JSON object.")
    return payload


def _validate_unique(items: list[Any], attribute: str, label: str) -> None:
    values = [getattr(item, attribute) for item in items]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise DataValidationError(f"Duplicate {label}: {', '.join(duplicates)}")


def load_candidates(path: str | Path) -> list[Candidate]:
    records = _require_list(_read_json(Path(path)), "candidate registry")
    candidates = [Candidate.from_dict(record) for record in records]
    _validate_unique(candidates, "candidate_id", "candidate IDs")
    return candidates


def load_corpus(path: str | Path) -> list[EvidenceChunk]:
    records = _require_list(_read_json(Path(path)), "corpus")
    chunks = [EvidenceChunk.from_dict(record) for record in records]
    _validate_unique(chunks, "chunk_id", "chunk IDs")
    return chunks


def load_guidance_links(path: str | Path) -> list[GuidanceLink]:
    records = _require_list(_read_json(Path(path)), "guidance registry")
    links = [GuidanceLink.from_dict(record) for record in records]
    _validate_unique(links, "guidance_id", "guidance IDs")
    return links


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_canonical_json(path: str | Path) -> str:
    """Reproduce the historical freeze's parsed-JSON content hash.

    The historical serializer sorted object keys, preserved Unicode, and emitted a
    non-indented JSON string using Python's default separators.
    """
    payload = _read_json(Path(path))
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_private_corpus_read_only(
    path: str | Path, *, expected_count: int | None = 76
) -> tuple[list[EvidenceChunk], str]:
    """Load and hash a private corpus without opening it for writing."""
    corpus_path = Path(path).expanduser().resolve(strict=True)
    before = hash_file(corpus_path)
    chunks = load_corpus(corpus_path)
    if expected_count is not None and len(chunks) != expected_count:
        raise DataValidationError(
            f"Expected {expected_count} private corpus records, found {len(chunks)}."
        )
    after = hash_file(corpus_path)
    if before != after:
        raise RuntimeError("Private corpus changed during read; refusing to continue.")
    return chunks, before
