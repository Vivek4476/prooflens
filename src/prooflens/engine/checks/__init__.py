"""Deterministic + vision checks. Each `run(...)` returns a CheckOutcome."""

from . import blur, exif, recapture, relevance, uniqueness

__all__ = ["exif", "blur", "uniqueness", "recapture", "relevance"]
