"""Tests for the deterministic checks (the vision call is never made here)."""

import io
import os

import pytest

from checks import sharpness, uniqueness, metadata, person
from checks.types import CheckResult


def _img_bytes(color=(180, 180, 180), size=(320, 240), noise=False):
    from PIL import Image
    import random

    img = Image.new("RGB", size, color)
    if noise:
        px = img.load()
        rnd = random.Random(1234)
        for x in range(0, size[0], 2):
            for y in range(0, size[1], 2):
                v = rnd.randint(0, 255)
                px[x, y] = (v, v, v)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92)
    return out.getvalue()


# ---------------------------------------------------------------- sharpness
def test_sharpness_flat_image_is_blurry():
    res = sharpness.run(_img_bytes(noise=False))
    assert isinstance(res, CheckResult)
    if not res.available:
        pytest.skip("OpenCV not installed")
    # A flat color image has near-zero Laplacian variance => low score.
    assert res.score < 50
    assert res.metric is not None


def test_sharpness_noisy_image_is_sharp():
    res = sharpness.run(_img_bytes(noise=True))
    if not res.available:
        pytest.skip("OpenCV not installed")
    assert res.score > 50


# ---------------------------------------------------------------- uniqueness
def test_uniqueness_first_then_duplicate(tmp_path, monkeypatch):
    # Point the store at a throwaway DB.
    import store

    db = str(tmp_path / "t.db")
    monkeypatch.setattr(store, "DB_PATH", db)

    data = _img_bytes(color=(123, 200, 50), noise=True)

    first = uniqueness.run(data, remember=True)
    if not first.available:
        pytest.skip("imagehash/Pillow not installed")
    assert first.passed is True
    assert first.score == 100.0  # nothing seen before

    second = uniqueness.run(data, remember=False)
    assert second.passed is False  # exact duplicate
    assert second.score == 0.0
    assert second.metric == 0.0  # hamming distance 0


# ---------------------------------------------------------------- metadata
def test_metadata_absent_when_no_exif():
    res = metadata.run(_img_bytes())
    if not res.available:
        pytest.skip("Pillow not installed")
    # Freshly generated JPEG has no EXIF => not passed, low-ish score.
    assert res.passed is False
    assert res.score <= 50


# ---------------------------------------------------------------- person
def test_person_on_blank_image_finds_nobody():
    res = person.run(_img_bytes())
    if not res.available:
        pytest.skip("OpenCV not installed")
    assert res.passed is False
    assert res.metric == 0.0
