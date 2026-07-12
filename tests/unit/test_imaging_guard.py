"""Decompression-bomb guard on the shared decode helpers."""

from __future__ import annotations

import io

import pytest

from prooflens.engine.checks import _imaging

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _jpeg(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 120, 120)).save(buf, format="JPEG")
    return buf.getvalue()


def test_within_budget_true_for_small_image():
    assert _imaging.within_pixel_budget(_jpeg(64, 64)) is True


def test_within_budget_false_over_budget(monkeypatch):
    monkeypatch.setattr(_imaging, "MAX_IMAGE_PIXELS", 100)  # 10x10 px budget
    assert _imaging.within_pixel_budget(_jpeg(64, 64)) is False


def test_unreadable_bytes_pass_through():
    # Not an image — let the real decoder decide; the guard must not false-reject.
    assert _imaging.within_pixel_budget(b"not an image at all") is True


@pytest.mark.skipif(not _imaging.CV2_AVAILABLE, reason="cv2 not installed")
def test_load_gray_rejects_oversized(monkeypatch):
    monkeypatch.setattr(_imaging, "MAX_IMAGE_PIXELS", 100)
    assert _imaging.load_gray(_jpeg(64, 64)) is None  # bounded, no full decode
    # A within-budget image still decodes normally.
    assert _imaging.load_gray(_jpeg(8, 8)) is not None
