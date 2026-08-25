"""Opt-in end-to-end NVIDIA vision call. Skipped unless
NVIDIA_API_KEY is set AND RUN_LIVE_VISION=1.
Run: RUN_LIVE_VISION=1 PYTHONPATH=src python -m pytest tests/live/test_nvidia_live.py -v
"""
from __future__ import annotations

import io
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_VISION") != "1" or not os.getenv("NVIDIA_API_KEY"),
    reason="live vision test is opt-in (set RUN_LIVE_VISION=1 + NVIDIA_API_KEY)",
)

# Capture the key at module import time, before the hermetic fixture blanks it.
_KEY = os.getenv("NVIDIA_API_KEY", "")


def _tiny_scene_jpeg() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 240), (135, 206, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 170, 320, 240], fill=(60, 160, 60))
    d.rectangle([90, 110, 190, 175], fill=(200, 60, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_nvidia_scores_a_real_image():
    from prooflens.vision.nvidia_backend import NvidiaBackend

    backend = NvidiaBackend(api_key=_KEY)
    out = backend.assess(_tiny_scene_jpeg())
    assert out.backend == "nvidia"
    assert out.model == "meta/llama-3.2-90b-vision-instruct"
    assert 0 <= out.plausibility <= 100
    assert out.scene_description  # perception populated
