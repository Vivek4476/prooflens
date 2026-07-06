"""Golden-set regression — the reason vocabulary is policy.

For every labelled image we assert BOTH the band AND the exact human-readable
reason string. Any rubric/fusion/copy change that shifts an outcome fails here
unless the golden expectation is updated in the same PR. Fully offline (stub
backend, in-memory store).
"""

from __future__ import annotations

import pytest

from prooflens.engine import REASON_TEXT, InMemoryHashStore, Reason
from prooflens.vision import get_backend
from tests.helpers import IMAGES_DIR, load_labels, score_image

pytestmark = pytest.mark.golden

LABELS = load_labels()


@pytest.mark.parametrize("row", LABELS, ids=[r["filename"] for r in LABELS])
def test_golden_band_and_reason(row):
    backend = get_backend("stub")
    store = InMemoryHashStore()

    # Seed the shared store with prerequisite images (e.g. the duplicate pair).
    for seed in filter(None, (row["seed_with"] or "").split(",")):
        score_image(IMAGES_DIR / seed.strip(), store=store, backend=backend)

    verdict = score_image(IMAGES_DIR / row["filename"], store=store, backend=backend)

    expected_code = row["expected_reason_code"]
    expected_reason = REASON_TEXT[Reason(expected_code)]

    assert verdict.band == row["expected_band"], (
        f"{row['filename']}: band {verdict.band!r} != {row['expected_band']!r} "
        f"(score={verdict.score}, reason={verdict.reason_code})"
    )
    assert verdict.reason_code == expected_code, (
        f"{row['filename']}: reason_code {verdict.reason_code!r} != {expected_code!r}"
    )
    assert verdict.reason == expected_reason, (
        f"{row['filename']}: reason string drifted from the vocabulary"
    )


def test_every_image_has_a_verdict():
    files = {p.name for p in IMAGES_DIR.glob("*.jpg")}
    labelled = {r["filename"] for r in LABELS}
    assert files == labelled, f"unlabelled or missing golden images: {files ^ labelled}"
