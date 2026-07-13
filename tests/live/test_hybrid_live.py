"""Opt-in end-to-end hybrid call against Cloudflare. Skipped unless
CF_ACCOUNT_ID + CF_API_TOKEN are set AND RUN_LIVE_VISION=1.
Run: RUN_LIVE_VISION=1 PYTHONPATH=src python -m pytest tests/live/test_hybrid_live.py -v
"""
from __future__ import annotations

import io
import os

import pytest

from prooflens import config

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_VISION") != "1"
    or not os.getenv("CF_ACCOUNT_ID")
    or not os.getenv("CF_API_TOKEN"),
    reason="live vision test is opt-in (set RUN_LIVE_VISION=1 + CF creds)",
)


def _tiny_scene_jpeg() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 240), (135, 206, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 170, 320, 240], fill=(60, 160, 60))
    d.rectangle([90, 110, 190, 175], fill=(200, 60, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_hybrid_scores_a_real_image():
    backend = config.Settings().build_vision_backend("hybrid")
    out = backend.assess(_tiny_scene_jpeg())
    assert out.backend == "hybrid"
    assert 0 <= out.plausibility <= 100
    assert out.scene_description  # perception populated
