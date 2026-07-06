"""Generate a varied, mutually-distinct demo image set for the leadership demo.

Unlike the golden set (which is tuned for offline stub tests and includes a
near-duplicate pair), these images are all distinct so scoring them yields a
realistic spread of verdicts — plus ONE intentional duplicate to demonstrate
recycled-image detection.

Run:  python scripts/generate_demo_images.py
Output: demo_images/*.jpg   (git-ignored; consumed by frontend seed:demo)
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "demo_images"
W, H = 512, 384


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(1000 + seed)


def _noise(arr: np.ndarray, rng, amp: int = 9) -> np.ndarray:
    n = rng.integers(-amp, amp + 1, size=arr.shape)
    return np.clip(arr.astype(int) + n, 0, 255).astype(np.uint8)


def _skin(rng) -> tuple[int, int, int]:
    base = rng.choice([(222, 184, 135), (198, 156, 120), (168, 124, 96), (236, 200, 160)])
    return tuple(int(x) for x in base)


def meeting(seed: int) -> Image.Image:
    """A real room with people. Strong structural variation (floor height, window
    /frame/furniture presence & position, people count & placement) so distinct
    seeds have distinct perceptual hashes — no accidental duplicates."""
    rng = _rng(seed)
    wall = tuple(int(x) for x in rng.integers(150, 210, 3))
    floor = tuple(
        int(x) for x in (rng.integers(70, 120), rng.integers(55, 95), rng.integers(45, 80))
    )
    img = Image.new("RGB", (W, H), wall)
    d = ImageDraw.Draw(img)
    floor_y = int(H * float(rng.uniform(0.5, 0.68)))
    d.rectangle([0, floor_y, W, H], fill=floor)

    if rng.random() < 0.7:  # window
        wx, wy = int(rng.integers(10, 120)), int(rng.integers(24, 60))
        ww, wh = int(rng.integers(90, 160)), int(rng.integers(90, 150))
        d.rectangle(
            [wx, wy, wx + ww, wy + wh],
            fill=(int(rng.integers(110, 150)), int(rng.integers(160, 200)), 210),
        )
    if rng.random() < 0.7:  # wall frame / poster
        fx, fy = int(rng.integers(250, 360)), int(rng.integers(40, 90))
        d.rectangle([fx, fy, fx + int(rng.integers(80, 150)), fy + int(rng.integers(70, 130))],
                    fill=tuple(int(x) for x in rng.integers(80, 170, 3)))
    if rng.random() < 0.5:  # a table / couch block
        tx = int(rng.integers(40, 220))
        tw, th = int(rng.integers(160, 300)), int(rng.integers(40, 90))
        d.rectangle(
            [tx, floor_y - 10, tx + tw, floor_y + th],
            fill=tuple(int(x) for x in rng.integers(70, 120, 3)),
        )

    people = int(rng.integers(1, 5))
    xs = sorted(rng.uniform(0.12, 0.88, size=people) * W)
    for cx in xs:
        cx = int(cx)
        head_y = int(rng.integers(80, 150))
        w = int(rng.integers(38, 58))
        shirt = tuple(int(x) for x in rng.integers(45, 195, 3))
        sk = _skin(rng)
        d.rectangle([cx - w, head_y + 55, cx + w, min(H, head_y + 190)], fill=shirt)
        hr = int(rng.integers(28, 38))
        d.ellipse([cx - hr, head_y, cx + hr, head_y + int(hr * 1.9)], fill=sk)
        d.ellipse([cx - w - 6, head_y + 130, cx - w + 26, head_y + 168], fill=sk)
        d.ellipse([cx + w - 26, head_y + 130, cx + w + 6, head_y + 168], fill=sk)
    return Image.fromarray(_noise(np.asarray(img), rng, 8))


def landscape(seed: int) -> Image.Image:
    rng = _rng(seed)
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    sky_r, sky_g = int(rng.integers(80, 130)), int(rng.integers(150, 190))
    g1 = int(rng.integers(40, 80))
    for y in range(H):
        t = y / H
        if t < 0.6:
            arr[y, :] = (int(sky_r + 60 * t), int(sky_g + 40 * t), 225)
        else:
            arr[y, :] = (g1, int(140 - 50 * (t - 0.6)), g1 + 10)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    for _ in range(int(rng.integers(1, 4))):  # mountains, varied
        mx = int(rng.integers(60, 460))
        mh_ = int(rng.integers(90, 170))
        d.polygon([(mx - 140, 232), (mx, mh_), (mx + 140, 232)],
                  fill=tuple(int(x) for x in rng.integers(95, 155, 3)))
    for _ in range(int(rng.integers(2, 8))):  # trees, varied count/pos
        x = int(rng.integers(20, 492))
        col = (int(rng.integers(20, 60)), int(rng.integers(90, 140)), int(rng.integers(45, 85)))
        r = int(rng.integers(18, 34))
        d.ellipse([x - r, 250, x + r, 250 + int(r * 2.4)], fill=col)
        d.rectangle([x - 5, 305, x + 5, 350], fill=(86, 66, 40))
    if rng.random() < 0.6:
        sx = int(rng.integers(340, 450))
        sr = int(rng.integers(45, 70))
        d.ellipse([sx, 36, sx + sr, 36 + sr], fill=(245, 245, 245))
    return Image.fromarray(_noise(np.asarray(img), rng, 11))


def screenshot(seed: int) -> Image.Image:
    rng = _rng(seed)
    bg = tuple(int(x) for x in rng.integers(235, 248, 3))
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    header = (int(rng.integers(30, 60)), int(rng.integers(60, 120)), int(rng.integers(140, 190)))
    hh = int(rng.integers(40, 72))
    d.rectangle([0, 0, W, hh], fill=header)
    ry = hh + int(rng.integers(20, 50))
    for _ in range(int(rng.integers(2, 5))):  # varied number of rows
        d.rectangle([24, ry, W - 24, ry + 42], fill=(255, 255, 255))
        ry += int(rng.integers(56, 80))
    accent = (int(rng.integers(30, 70)), int(rng.integers(130, 180)), int(rng.integers(90, 130)))
    bx = int(rng.integers(24, 80))
    d.rectangle([bx, H - 70, bx + int(rng.integers(120, 170)), H - 24], fill=accent)
    return img


def blurred(seed: int) -> Image.Image:
    return meeting(seed).filter(ImageFilter.GaussianBlur(radius=7))


def screen(seed: int) -> Image.Image:
    rng = _rng(seed)
    canvas = Image.new("RGB", (W, H), (14, 14, 16))
    inner = landscape(seed).resize((int(W * 0.78), int(H * 0.78)))
    canvas.paste(inner, ((W - inner.width) // 2, (H - inner.height) // 2))
    arr = np.asarray(canvas).astype(np.int32)
    yy, xx = np.mgrid[0:H, 0:W]
    grid = (28 * np.sin(2 * np.pi * xx / 3.0) * np.sin(2 * np.pi * yy / 3.0)).astype(np.int32)
    arr = np.clip(arr + grid[:, :, None], 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    gx = int(rng.integers(300, 380))
    d.ellipse([gx, 60, gx + 140, 170], fill=(255, 255, 255))
    return img


def _save(img: Image.Image, name: str) -> None:
    img.save(OUT / name, format="JPEG", quality=90)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()

    # (factory, count, seed_base) — meetings are the legit majority (mostly Clear).
    plan = [
        (meeting, 14, 0),
        (screenshot, 4, 100),
        (landscape, 4, 200),
        (blurred, 3, 300),
        (screen, 2, 400),
    ]
    n = 0
    for factory, count, base in plan:
        for i in range(count):
            _save(factory(base + i), f"{factory.__name__}_{i:02d}.jpg")
            n += 1

    # One intentional exact duplicate (re-upload) to demonstrate recycled.
    dup = io.BytesIO()
    meeting(0).save(dup, format="JPEG", quality=90)
    (OUT / "reupload_of_meeting_00.jpg").write_bytes(dup.getvalue())
    n += 1

    print(f"wrote {n} demo images to {OUT}")


if __name__ == "__main__":
    main()
