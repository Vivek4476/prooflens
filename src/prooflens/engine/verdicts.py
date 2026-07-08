"""Verdict vocabulary — the single source of truth for band names and reason strings.

This module IS policy. The fusion layer may emit reasons ONLY from ``REASON_TEXT``
below; golden tests import these same constants so a copy change that shifts an
outcome fails CI unless the golden expectation is updated in the same PR.

Rules for every reason string (enforced by tests in tests/unit/test_verdict_copy.py):
  * <= 90 characters
  * plain language a first-time reader understands
  * names the evidence, never an internal check name
  * never relies on colour to convey meaning

See docs/VERDICT_COPY.md for the human-facing specification.
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Bands — the decision driver. Written back to LSQ FIRST (before score/reason).
# ---------------------------------------------------------------------------
BAND_CLEAR = "Clear"
BAND_DOUBTFUL = "Doubtful"
BAND_SUSPECT = "Suspect"

BANDS = (BAND_SUSPECT, BAND_DOUBTFUL, BAND_CLEAR)


class Reason(StrEnum):
    """Every terminal outcome ProofLens can report. One member per failure mode."""

    CLEAR = "clear"
    RECYCLED = "recycled"
    SCREEN_RECAPTURE = "screen_recapture"
    DESIGNED_GRAPHIC = "designed_graphic"
    NO_PEOPLE_OR_IRRELEVANT = "no_people_or_irrelevant"
    NOT_A_VISIT = "not_a_visit"
    SINGLE_PERSON = "single_person"
    NO_VISIT_CONTEXT = "no_visit_context"
    TOO_BLURRED = "too_blurred"
    NO_CONTENT_ANALYSIS = "no_content_analysis"


# The ONLY strings the fusion layer is allowed to surface as `reason`.
REASON_TEXT: dict[Reason, str] = {
    Reason.CLEAR: "Clear — no capture-integrity issues found.",
    Reason.RECYCLED: "Recycled image — matches a photo already submitted for this account.",
    Reason.SCREEN_RECAPTURE: "Photo of another screen — screen edge and glare detected.",
    Reason.DESIGNED_GRAPHIC: "Designed graphic or screenshot, not a photo of a live scene.",
    Reason.NO_PEOPLE_OR_IRRELEVANT: "No people or relevant scene detected in the photo.",
    Reason.NOT_A_VISIT: "Not a customer visit — the scene shows no meeting or client interaction.",
    Reason.SINGLE_PERSON: "Only one person in view — not evidence of a customer meeting.",
    Reason.NO_VISIT_CONTEXT: "No visit in progress — the photo shows no interaction or visit.",
    Reason.TOO_BLURRED: "Too blurred to assess — please retake in better light.",
    Reason.NO_CONTENT_ANALYSIS: "Scored without content analysis — vision check unavailable.",
}

# Concise labels for aggregate surfaces (charts, group rows). Full sentences in
# REASON_TEXT remain the verdict surface; these are for counts/legends (spec §0e).
REASON_SHORT_LABEL: dict[Reason, str] = {
    Reason.CLEAR: "Clear",
    Reason.RECYCLED: "Recycled image",
    Reason.SCREEN_RECAPTURE: "Photo of a screen",
    Reason.DESIGNED_GRAPHIC: "Designed graphic",
    Reason.NO_PEOPLE_OR_IRRELEVANT: "No people in scene",
    Reason.NOT_A_VISIT: "Not a visit",
    Reason.SINGLE_PERSON: "Only one person",
    Reason.NO_VISIT_CONTEXT: "No visit in progress",
    Reason.TOO_BLURRED: "Too blurred",
    Reason.NO_CONTENT_ANALYSIS: "Scored without content check",
}

# When more than one failure mode fires, the most decision-critical wins.
# Fraud/integrity signals outrank quality signals; quality outranks "clear".
REASON_PRIORITY: tuple[Reason, ...] = (
    Reason.RECYCLED,
    Reason.SCREEN_RECAPTURE,
    Reason.DESIGNED_GRAPHIC,
    Reason.NO_PEOPLE_OR_IRRELEVANT,
    Reason.NOT_A_VISIT,
    Reason.SINGLE_PERSON,
    Reason.NO_VISIT_CONTEXT,
    Reason.TOO_BLURRED,
    Reason.NO_CONTENT_ANALYSIS,
    Reason.CLEAR,
)


def reason_text(reason: Reason) -> str:
    return REASON_TEXT[reason]


def most_severe(reasons: list[Reason]) -> Reason:
    """Pick the highest-priority reason from those that fired (default CLEAR)."""
    fired = set(reasons)
    for r in REASON_PRIORITY:
        if r in fired:
            return r
    return Reason.CLEAR
