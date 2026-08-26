"""Deterministic, plain-language summary of a decision — no LLM call.

Built from the fired reason_code and the per-check outcomes so it is free,
instant, and testable. Copilot is additive: callers fall back to verdict.reason.
"""
from __future__ import annotations

import textwrap

from .types import Verdict

# reason_code -> a plain-language clause explaining the driver.
_REASON_CLAUSE = {
    "clear": "the capture looks like a genuine meeting",
    "recycled": "the image is a near-duplicate of earlier submissions (reused imagery)",
    "screen_recapture": "the frame is a photo of a screen, not a live camera capture",
    "designed_graphic": "the image is a designed graphic / screenshot, not a photo",
    "no_people_or_irrelevant": "no people are present or the scene is irrelevant to a visit",
    "not_a_visit": "the scene does not read as a customer visit",
    "single_person": "only one person is visible, so a two-party meeting can't be confirmed",
    "no_visit_context": "people are present but no meeting interaction is evident",
    "too_blurred": "the image is too blurred to assess",
    "no_content_analysis": "the vision check was unavailable, so it was not graded",
}


def _evidence(verdict: Verdict) -> str:
    """The most informative available check summary, if any."""
    for c in (verdict.checks or []):
        if c.available and c.summary:
            return c.summary.strip().rstrip(".")
    return ""


def summarize_decision(verdict: Verdict) -> str:
    try:
        clause = _REASON_CLAUSE.get(verdict.reason_code, (verdict.reason or "").lower())
        if verdict.band == "Unassessed":
            body = f"Not graded — {clause}."
        else:
            body = f"Scored {verdict.band} because {clause}."
        ev = _evidence(verdict)
        if ev:
            body = f"{body} Detail: {ev}."
        return textwrap.shorten(body, width=400, placeholder="…")
    except Exception:
        return (getattr(verdict, "reason", "") or "")[:400]
