"""Pure, DB-free seed-data generation for the realistic-demo dataset (Analytics
v4, Pain 3, Task 9). No DB or network import — every function here is a plain
transformation from inputs to values, fully unit-testable offline.

A later runnable script (Task 10, ``scripts/seed-realistic.py``) owns reading
``DATABASE_URL``, calling ``repo.replace_hierarchy(...)`` and
``repo.record_result(..., source="seed")``; this module only produces the pure
data that script will persist.

Determinism: every function that needs randomness takes an injected
``random.Random`` instance. Nothing here calls module-level ``random.*`` or
``datetime.now()`` — callers own the RNG and the "today" reference so runs are
reproducible given the same seed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random

from prooflens.engine.types import Verdict
from prooflens.engine.verdicts import BAND_CLEAR, BAND_DOUBTFUL, BAND_SUSPECT, REASON_TEXT, Reason
from prooflens.service.ids import normalize_id
from prooflens.vision.rubric import RUBRIC_VERSION

# ---------------------------------------------------------------------------
# Agent pool
# ---------------------------------------------------------------------------


def generate_agent_pool(hierarchy_csv_path: str | Path) -> list[str]:
    """Read the sample-hierarchy CSV and return its normalized agent_ids.

    Uses the same ``normalize_id`` as webhook ingestion and hierarchy upload
    (``service/ids.py``), so results generated against this pool line up
    exactly with the uploaded hierarchy — ``hierarchy_status()``'s match rate
    reads ~100%, not "unmapped". Order is preserved (minus blanks), duplicates
    are NOT de-duplicated here (a hierarchy row per agent is expected to be
    unique, but this function only normalizes — it does not validate)."""
    path = Path(hierarchy_csv_path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        agent_ids = [normalize_id(row.get("agent_id")) for row in reader]
    return [a for a in agent_ids if a is not None]


# ---------------------------------------------------------------------------
# Timestamps — weekday-biased, working-hours clustered
# ---------------------------------------------------------------------------

_WORKDAY_START_HOUR = 9
_WORKDAY_END_HOUR = 19  # ~7pm
_MIDDAY_HOUR = 13.5     # triangular mode, a little after lunch


def sample_timestamp(day: date, rng: Random) -> datetime:
    """One timestamp on ``day``, clustered in working hours (~9am-7pm,
    triangular around midday) regardless of weekday/weekend — the caller
    (``generate_seed_plan``) is responsible for varying *how many* timestamps
    it draws per day (the weekday/weekend volume bias), not this function."""
    hour = rng.triangular(_WORKDAY_START_HOUR, _WORKDAY_END_HOUR, _MIDDAY_HOUR)
    total_seconds = (hour - _WORKDAY_START_HOUR) * 3600.0
    return datetime(day.year, day.month, day.day, _WORKDAY_START_HOUR) + timedelta(
        seconds=total_seconds
    )


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5  # Saturday=5, Sunday=6


def daily_record_count(
    day: date, records_per_day_range: tuple[int, int], rng: Random
) -> int:
    """How many records to generate on ``day``. Weekends get a materially
    lighter (but non-zero) fraction of a weekday's volume — 10-20% of what a
    weekday in the same range would draw, sampled per call so repeated seeds
    aren't suspiciously identical."""
    lo, hi = records_per_day_range
    weekday_count = rng.randint(lo, hi)
    if not is_weekend(day):
        return weekday_count
    weekend_fraction = rng.uniform(0.10, 0.20)
    return max(1, round(weekday_count * weekend_fraction))


# ---------------------------------------------------------------------------
# Verdict sampling
# ---------------------------------------------------------------------------

# Target band mix (fractions of total). Sampled per-run within these ranges
# rather than hardcoded so repeated seeds don't look suspiciously identical.
_SUSPECT_RANGE = (0.02, 0.05)
_DOUBTFUL_RANGE = (0.08, 0.12)

# Reasons plausible within each non-Clear band, weighted per the brief:
# integrity signals (recycled / screen_recapture / designed_graphic /
# no_people_or_irrelevant) dominate Suspect; quality/transparency signals
# (too_blurred / no_content_analysis) dominate Doubtful. Weights are a rough
# guide from REASON_PRIORITY's relative plausibility, not a hard rule.
_SUSPECT_REASON_WEIGHTS: tuple[tuple[Reason, float], ...] = (
    (Reason.RECYCLED, 3.0),
    (Reason.SCREEN_RECAPTURE, 2.5),
    (Reason.DESIGNED_GRAPHIC, 2.5),
    (Reason.NO_PEOPLE_OR_IRRELEVANT, 2.5),
    (Reason.NOT_A_VISIT, 1.0),
    (Reason.SINGLE_PERSON, 0.5),
)
_DOUBTFUL_REASON_WEIGHTS: tuple[tuple[Reason, float], ...] = (
    (Reason.TOO_BLURRED, 3.0),
    (Reason.NO_CONTENT_ANALYSIS, 2.5),
    (Reason.NO_VISIT_CONTEXT, 1.5),
    (Reason.SINGLE_PERSON, 1.0),
)

# Score ranges per band, per docs/VERDICT_COPY.md: Clear >= 70, Doubtful
# 40-69, Suspect < 40. Sampled with light noise, never pinned to a boundary.
_CLEAR_SCORE_RANGE = (70.0, 99.0)
_DOUBTFUL_SCORE_RANGE = (40.0, 69.0)
_SUSPECT_SCORE_RANGE = (1.0, 39.0)


def _weighted_choice(rng: Random, weights: tuple[tuple[Reason, float], ...]) -> Reason:
    total = sum(w for _, w in weights)
    pick = rng.uniform(0.0, total)
    running = 0.0
    for reason, w in weights:
        running += w
        if pick <= running:
            return reason
    return weights[-1][0]  # pragma: no cover - float rounding fallback


def sample_verdict(rng: Random) -> Verdict:
    """Draw one realistic Verdict: a band from the target mix, then (for
    Suspect/Doubtful) a plausible reason_code and a score consistent with the
    band's range. Always builds ``reason``/``reason_code`` from the real
    ``REASON_TEXT``/``Reason`` vocabulary in engine/verdicts.py — never a
    hand-typed string — so a future copy change can't silently desync the
    seed data from the live product copy."""
    suspect_frac = rng.uniform(*_SUSPECT_RANGE)
    doubtful_frac = rng.uniform(*_DOUBTFUL_RANGE)
    roll = rng.random()

    if roll < suspect_frac:
        band = BAND_SUSPECT
        reason_code = _weighted_choice(rng, _SUSPECT_REASON_WEIGHTS)
        score = rng.uniform(*_SUSPECT_SCORE_RANGE)
    elif roll < suspect_frac + doubtful_frac:
        band = BAND_DOUBTFUL
        reason_code = _weighted_choice(rng, _DOUBTFUL_REASON_WEIGHTS)
        score = rng.uniform(*_DOUBTFUL_SCORE_RANGE)
    else:
        band = BAND_CLEAR
        reason_code = Reason.CLEAR
        score = rng.uniform(*_CLEAR_SCORE_RANGE)

    return Verdict(
        score=round(score, 2),
        band=band,
        reason=REASON_TEXT[reason_code],
        reason_code=reason_code.value,
        checks=[],
        rubric_version=RUBRIC_VERSION,
    )


# ---------------------------------------------------------------------------
# Top-level seed plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedRecord:
    created_at: datetime
    rep_id: str
    verdict: Verdict
    opportunity_id: str


def generate_seed_plan(
    days: int,
    records_per_day_range: tuple[int, int],
    agent_pool: list[str],
    rng: Random,
    *,
    start_day: date | None = None,
) -> list[SeedRecord]:
    """The top-level pure generator: ``days`` of activity ending on
    ``start_day + days - 1`` (``start_day`` defaults to a fixed anchor so
    callers that omit it still get deterministic output for a given ``rng``
    seed and ``days``), each day contributing a weekday-biased record count,
    each record's timestamp from ``sample_timestamp``, each ``rep_id`` drawn
    from ``agent_pool``, each ``opportunity_id`` a synthetic but stable id.

    Requires a non-empty ``agent_pool`` (raises ``ValueError`` otherwise —
    there is no meaningful seed plan with zero agents to attribute records
    to)."""
    if not agent_pool:
        raise ValueError("agent_pool must be non-empty")
    if days <= 0:
        raise ValueError("days must be positive")

    anchor = start_day if start_day is not None else date(2026, 1, 1)
    records: list[SeedRecord] = []
    counter = 0

    for offset in range(days):
        day = anchor + timedelta(days=offset)
        count = daily_record_count(day, records_per_day_range, rng)
        for _ in range(count):
            created_at = sample_timestamp(day, rng)
            rep_id = rng.choice(agent_pool)
            verdict = sample_verdict(rng)
            opportunity_id = f"OPP-{counter:06d}"
            counter += 1
            records.append(
                SeedRecord(
                    created_at=created_at,
                    rep_id=rep_id,
                    verdict=verdict,
                    opportunity_id=opportunity_id,
                )
            )

    return records


__all__ = [
    "SeedRecord",
    "daily_record_count",
    "generate_agent_pool",
    "generate_seed_plan",
    "is_weekend",
    "sample_timestamp",
    "sample_verdict",
]
