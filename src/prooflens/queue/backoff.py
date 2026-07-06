"""Exponential backoff with full jitter."""

from __future__ import annotations

import random


def backoff_seconds(
    attempts: int,
    *,
    base: float,
    maximum: float,
    retry_after: float | None = None,
) -> float:
    """Delay before the next attempt.

    Honours an explicit ``retry_after`` (e.g. from a 429) when larger. Otherwise
    exponential (base * 2^(attempts-1)) capped at ``maximum``, with full jitter
    to avoid thundering herds.
    """
    exp = min(maximum, base * (2 ** max(0, attempts - 1)))
    jittered = random.uniform(0, exp)  # full jitter
    if retry_after is not None:
        return max(retry_after, jittered)
    return jittered
