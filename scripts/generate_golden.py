"""Generate the synthetic golden image set + labels.

Deterministic (fixed seed). Each image is crafted to be cleanly separable by the
stub backend's colour/skin heuristics and the real deterministic checks, so the
golden set runs offline in CI and asserts BOTH band and the exact reason string.

Run:  python scripts/generate_golden.py
Output: tests/golden/images/*.jpg  and  tests/golden/labels.csv
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden" / "images"
LABELS = Path(__file__).resolve().parents[1] / "tests" / "golden" / "labels.csv"

W, H = 512, 384
RNG = np.random.default_rng(20260706)

SKIN = (222, 184, 135)   # a warm skin tone the stub's heuristic recognises
SKIN2 = (198, 156, 120)


def _noise(arr: np.ndarray, amp: int = 10) -> np.ndarray:
    """Add mild high-frequency noise so 'photo' images have broadband spectra
    (keeps the recapture FFT check from false-firing) and real detail (sharpness)."""
    n = RNG.integers(-amp, amp + 1, size=arr.shape)
    return np.clip(arr.astype(int) + n, 0, 255).astype(np.uint8)


def _save(img: Image.Image, name: str) -> None:
    img.save(OUT_DIR / name, format="JPEG", quality=90)


def make_meeting() -> Image.Image:
    """A rich-coloured room with two people (skin tones): sharp, unique, real."""
    img = Image.new("RGB", (W, H), (176, 158, 132))
    d = ImageDraw.Draw(img)
    # Wall / floor / a window with varied colours -> many distinct colours.
    d.rectangle([0, 0, W, int(H * 0.6)], fill=(198, 186, 160))
    d.rectangle([0, int(H * 0.6), W, H], fill=(120, 96, 70))
    d.rectangle([40, 40, 180, 170], fill=(120, 170, 210))   # window
    d.rectangle([300, 60, 470, 200], fill=(150, 60, 60))     # picture frame
    # A table.
    d.rectangle([120, 250, 400, 320], fill=(90, 66, 48))
    # Two seated people: bodies (clothing) + heads/hands (skin).
    for cx, shirt in ((190, (60, 90, 150)), (330, (150, 70, 120))):
        d.rectangle([cx - 55, 190, cx + 55, 300], fill=shirt)      # torso
        d.ellipse([cx - 34, 96, cx + 34, 168], fill=SKIN)          # head
        d.ellipse([cx - 60, 250, cx - 24, 290], fill=SKIN2)        # hand
        d.ellipse([cx + 24, 250, cx + 60, 290], fill=SKIN2)        # hand
    arr = _noise(np.asarray(img), amp=8)
    return Image.fromarray(arr)


def make_blurred(meeting: Image.Image) -> Image.Image:
    """The meeting scene, too blurred to assess (Laplacian variance below floor)
    but with the skin regions still present so it reads 'too blurred', not 'no people'."""
    return meeting.filter(ImageFilter.GaussianBlur(radius=7))


def make_landscape() -> Image.Image:
    """Outdoor scene, no people. Cool tones only (no skin), broadband, sharp."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    # Sky gradient (blue -> pale), avoiding any warm/skin tones.
    for y in range(H):
        t = y / H
        if t < 0.6:
            arr[y, :] = (int(90 + 90 * t), int(150 + 60 * t), 225)
        else:
            arr[y, :] = (70, int(150 - 60 * (t - 0.6)), 70)  # green ground
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    d.polygon([(60, 230), (200, 90), (330, 230)], fill=(120, 130, 140))   # grey mountain
    d.polygon([(280, 230), (430, 120), (500, 230)], fill=(100, 110, 120))
    d.ellipse([380, 40, 440, 100], fill=(245, 245, 245))                  # white sun
    # Varied vegetation/terrain (cool + neutral tones, never skin) so the scene
    # is colour-diverse — a broadband real photo, not a flat graphic.
    d.polygon([(0, 384), (120, 250), (240, 384)], fill=(46, 110, 58))     # dark-green hill
    d.polygon([(240, 384), (360, 260), (512, 384)], fill=(64, 140, 72))   # light-green hill
    trees = ((90, (30, 90, 45)), (200, (40, 120, 60)), (360, (24, 80, 40)), (450, (52, 130, 66)))
    for x, col in trees:
        d.ellipse([x - 26, 250, x + 26, 320], fill=col)                   # tree canopies
        d.rectangle([x - 6, 300, x + 6, 350], fill=(86, 66, 40))          # trunk (neutral brown)
    d.line([(0, 360), (512, 330)], fill=(150, 150, 158), width=10)        # grey path
    d.rectangle([150, 300, 175, 320], fill=(70, 90, 200))                # blue flowers (not skin)
    d.rectangle([300, 310, 325, 330], fill=(180, 170, 60))               # olive shrub
    return Image.fromarray(_noise(np.asarray(img), amp=12))


def make_screenshot() -> Image.Image:
    """A flat UI mock-up: few, flat colours -> reads as a designed graphic/screenshot."""
    img = Image.new("RGB", (W, H), (240, 242, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 56], fill=(38, 78, 156))            # header bar
    d.rectangle([24, 96, W - 24, 150], fill=(255, 255, 255))  # input row
    d.rectangle([24, 176, W - 24, 230], fill=(255, 255, 255))
    d.rectangle([24, 256, 180, 320], fill=(38, 156, 96))      # button
    d.rectangle([300, 256, W - 24, 320], fill=(220, 224, 230))
    return img


def make_screen_recapture(landscape: Image.Image) -> Image.Image:
    """A scene photographed off another screen: dark bezel + bright interior +
    a fine sinusoidal pixel grid (moire) + a specular glare blob."""
    canvas = Image.new("RGB", (W, H), (14, 14, 16))  # dark bezel
    inner = landscape.resize((int(W * 0.78), int(H * 0.78)))
    ox, oy = (W - inner.width) // 2, (H - inner.height) // 2
    canvas.paste(inner, (ox, oy))
    arr = np.asarray(canvas).astype(np.int32)
    # Sinusoidal screen-door grid over the whole frame -> sharp FFT peaks (moire).
    yy, xx = np.mgrid[0:H, 0:W]
    grid = (28 * np.sin(2 * np.pi * xx / 3.0) * np.sin(2 * np.pi * yy / 3.0)).astype(np.int32)
    arr = np.clip(arr + grid[:, :, None], 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.ellipse([330, 60, 470, 170], fill=(255, 255, 255))  # specular glare blob
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    meeting = make_meeting()
    landscape = make_landscape()

    _save(meeting, "meeting.jpg")
    _save(make_blurred(meeting), "blurred.jpg")
    _save(landscape, "landscape.jpg")
    _save(make_screenshot(), "screenshot.jpg")
    _save(make_screen_recapture(landscape), "screen_recapture.jpg")

    # Near/exact-duplicate pair: b is a re-save of a -> identical dHash.
    # Exact re-upload: identical bytes -> dHash Hamming distance 0 -> hard gate.
    dup_bytes = io.BytesIO()
    meeting.save(dup_bytes, format="JPEG", quality=90)
    (OUT_DIR / "duplicate_a.jpg").write_bytes(dup_bytes.getvalue())
    (OUT_DIR / "duplicate_b.jpg").write_bytes(dup_bytes.getvalue())

    # labels.csv — expected band + reason_code per image. duplicate_a is scored
    # first (to seed the store), duplicate_b must then read as recycled.
    # Columns: filename, expected_band, expected_reason_code, seed_with, note.
    # `seed_with` lists images scored first into the SAME tenant hash store, so the
    # duplicate pair reproduces a real re-upload; every other image uses a fresh store.
    rows = [
        ("meeting.jpg", "Clear", "clear", "", "rich real scene with people"),
        ("blurred.jpg", "Doubtful", "too_blurred", "", "meeting scene, unreadable"),
        ("landscape.jpg", "Suspect", "no_people_or_irrelevant", "", "outdoor, no people"),
        ("screenshot.jpg", "Suspect", "designed_graphic", "", "flat UI mock-up"),
        ("screen_recapture.jpg", "Suspect", "screen_recapture", "", "photographed off a screen"),
        ("duplicate_a.jpg", "Clear", "clear", "", "first upload of the pair"),
        ("duplicate_b.jpg", "Suspect", "recycled", "duplicate_a.jpg", "exact re-upload"),
    ]
    with open(LABELS, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["filename", "expected_band", "expected_reason_code", "seed_with", "note"])
        writer.writerows(rows)

    print(f"wrote {len(rows)} golden images to {OUT_DIR}")
    print(f"wrote labels to {LABELS}")


if __name__ == "__main__":
    main()
