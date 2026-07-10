"""FakeLSQClient records ordered custom-field writes."""

from __future__ import annotations

import pytest

from prooflens.lsq import BAD_FETCH_MARKER, FakeLSQClient, FieldUpdate


def test_records_writes_in_order():
    lsq = FakeLSQClient()
    lsq.update_custom_fields(
        "opp-1",
        [FieldUpdate("F_BAND", "Clear"), FieldUpdate("F_SCORE", "89.0"),
         FieldUpdate("F_REASON", "all good")],
    )
    assert lsq.order("opp-1") == ["F_BAND", "F_SCORE", "F_REASON"]
    assert lsq.fields("opp-1") == {"F_BAND": "Clear", "F_SCORE": "89.0", "F_REASON": "all good"}


def test_is_labelled_not_real():
    assert FakeLSQClient().is_real is False


def test_fetch_image_returns_scorable_bytes():
    data = FakeLSQClient().fetch_image("https://lsq.example/photo.jpg")
    assert isinstance(data, bytes)
    assert len(data) > 0
    # A real (decodable) image, not a placeholder blob — the bulk service scores
    # it through the same engine /v1/score uses.
    assert data[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_fetch_image_raises_for_bad_fetch_marker():
    lsq = FakeLSQClient()
    with pytest.raises(Exception):  # noqa: B017 — any exception, fail-open is the caller's job
        lsq.fetch_image(f"https://lsq.example/{BAD_FETCH_MARKER}/photo.jpg")


def test_fetch_image_is_deterministic_per_url():
    lsq = FakeLSQClient()
    # Same URL -> identical bytes (stable, cacheable).
    assert lsq.fetch_image("https://lsq.example/one.jpg") == lsq.fetch_image("https://lsq.example/one.jpg")
    # Different URLs -> different bytes, so a bulk batch doesn't all dedupe as recycled.
    assert lsq.fetch_image("https://lsq.example/one.jpg") != lsq.fetch_image("https://lsq.example/two.jpg")
