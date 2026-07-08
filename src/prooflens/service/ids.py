"""One shared ID-normalization rule, used at BOTH webhook ingestion and
hierarchy upload so a rep_id always compares equal regardless of source
casing/whitespace. Single source of truth (spec §0c)."""

from __future__ import annotations


def normalize_id(s: str | None) -> str | None:
    """Canonical form of a rep/agent id: trimmed + upper-cased. Blank/None -> None."""
    if s is None:
        return None
    stripped = s.strip()
    return stripped.upper() if stripped else None
