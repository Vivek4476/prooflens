#!/usr/bin/env python3
"""Bake-off CLI — compare every configured vision backend over a folder.

Usage:
    python compare.py <folder>

The folder should contain images. Labels are read from a sibling `labels.csv`
(filename,label) if present, where label is `good` (genuine meeting proof) or
`bad` (screen photo / graphic / meme / no people / irrelevant). If no labels
file exists, the table still prints latency + cost, just without accuracy.

For each backend whose key/SDK is available, prints:
  accuracy, false-positive rate, avg latency, approx cost/photo.

A backend is skipped (not failed) if its key isn't set — so you can run this
with whatever you have configured.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

from config import COST_PER_PHOTO_USD, THRESHOLDS
from vision import ALL_BACKENDS, get_backend

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _load_labels(folder: str) -> Dict[str, str]:
    path = os.path.join(folder, "labels.csv")
    labels: Dict[str, str] = {}
    if not os.path.exists(path):
        return labels
    with open(path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            name, label = row[0].strip(), row[1].strip().lower()
            if name.lower() in {"filename", "file", "name"}:
                continue  # header
            labels[name] = label
    return labels


def _list_images(folder: str) -> List[str]:
    out = []
    for fn in sorted(os.listdir(folder)):
        if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
            out.append(fn)
    return out


def _verdict_is_good(verdict: dict) -> bool:
    """Apply the same accept logic the app uses for the content gate."""
    if verdict.get("looks_like_photo_of_a_screen"):
        return False
    if verdict.get("is_designed_graphic"):
        return False
    if verdict.get("is_meme_or_screenshot"):
        return False
    return int(verdict.get("meeting_plausibility", 0)) >= THRESHOLDS.meeting_plausibility_gate


def _available_backends() -> List[str]:
    available = []
    for name in ALL_BACKENDS:
        try:
            get_backend(name)
            available.append(name)
        except Exception as exc:
            print(f"  · skipping '{name}': {exc}")
    return available


def run_backend(name: str, folder: str, files: List[str],
                labels: Dict[str, str]) -> Optional[dict]:
    try:
        backend = get_backend(name)
    except Exception as exc:
        print(f"  · skipping '{name}': {exc}")
        return None

    n = 0
    correct = 0
    fp = 0          # predicted good, actually bad
    fp_denom = 0    # number actually bad
    total_latency = 0.0

    for fn in files:
        with open(os.path.join(folder, fn), "rb") as f:
            data = f.read()
        t0 = time.perf_counter()
        verdict = backend.assess(data)
        total_latency += time.perf_counter() - t0
        n += 1

        pred_good = _verdict_is_good(verdict)
        label = labels.get(fn)
        if label in {"good", "bad"}:
            actual_good = label == "good"
            if pred_good == actual_good:
                correct += 1
            if not actual_good:
                fp_denom += 1
                if pred_good:
                    fp += 1

    labelled = sum(1 for fn in files if labels.get(fn) in {"good", "bad"})
    return {
        "backend": name,
        "model": getattr(backend, "model", name),
        "n": n,
        "labelled": labelled,
        "accuracy": (correct / labelled) if labelled else None,
        "fp_rate": (fp / fp_denom) if fp_denom else None,
        "avg_latency": (total_latency / n) if n else 0.0,
        "cost_per_photo": COST_PER_PHOTO_USD.get(name, 0.0),
    }


def _fmt_pct(x: Optional[float]) -> str:
    return f"{x * 100:5.1f}%" if x is not None else "   n/a"


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    folder = argv[1]
    if not os.path.isdir(folder):
        print(f"Not a folder: {folder}")
        return 1

    files = _list_images(folder)
    if not files:
        print(f"No images found in {folder}")
        return 1
    labels = _load_labels(folder)

    print(f"\nProofLens bake-off · {len(files)} image(s), "
          f"{len(labels)} labelled · folder: {folder}\n")

    rows = []
    for name in ALL_BACKENDS:
        row = run_backend(name, folder, files, labels)
        if row:
            rows.append(row)

    if not rows:
        print("No backends available (set API keys or run with stub).")
        return 1

    # Table
    header = f"{'backend':<10} {'model':<22} {'acc':>7} {'fp-rate':>8} {'lat/img':>9} {'$/photo':>9}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['backend']:<10} {str(r['model'])[:22]:<22} "
            f"{_fmt_pct(r['accuracy']):>7} {_fmt_pct(r['fp_rate']):>8} "
            f"{r['avg_latency']*1000:>7.0f}ms ${r['cost_per_photo']:>7.4f}"
        )
    print()
    if not labels:
        print("(No labels.csv found — accuracy/fp-rate are n/a. Add one to score quality.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
