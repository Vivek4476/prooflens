"""Shared, offline test helpers (stub backend, in-memory hash store)."""

from __future__ import annotations

import csv
from pathlib import Path

from prooflens.engine import DEFAULT_SCORING, EngineContext, InMemoryHashStore, score

GOLDEN_DIR = Path(__file__).parent / "golden"
IMAGES_DIR = GOLDEN_DIR / "images"
LABELS_CSV = GOLDEN_DIR / "labels.csv"


def score_image(path: Path, *, store, backend, tenant_id="dev", rep_id=None, opportunity_id=None):
    ctx = EngineContext(
        tenant_id=tenant_id,
        vision=backend,
        hash_store=store,
        scoring=DEFAULT_SCORING,
        rep_id=rep_id,
        opportunity_id=opportunity_id,
    )
    return score(path.read_bytes(), ctx)


def load_labels() -> list[dict]:
    with open(LABELS_CSV, newline="") as fh:
        return list(csv.DictReader(fh))


__all__ = [
    "GOLDEN_DIR",
    "IMAGES_DIR",
    "LABELS_CSV",
    "score_image",
    "load_labels",
    "InMemoryHashStore",
]
