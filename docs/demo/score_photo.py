#!/usr/bin/env python3
"""Score real photos through the full ProofLens pipeline using the live GitHub
Models vision backend — the demo's "genuine vs fraud" driver.

Drop real, non-customer photos anywhere and pass their paths. Genuine field /
meeting / site photos should score high (Clear); AI-generated, stock-studio,
screenshots, or photos-of-a-screen should be caught (Suspect/Doubtful).

Prereqs:
    - .env.local has GITHUB_MODELS_TOKEN (and VISION_BACKEND=github)
    - venv active

Run:
    GITHUB_MODELS_TOKEN=... PYTHONPATH=src python docs/demo/score_photo.py path/to/*.jpg

Or score the committed synthetic fraud samples to prove the catch side offline-ish:
    GITHUB_MODELS_TOKEN=... PYTHONPATH=src python docs/demo/score_photo.py docs/demo/assets/*.jpg
"""
from __future__ import annotations

import sys
from pathlib import Path

from prooflens import config
from prooflens.engine import DEFAULT_SCORING, EngineContext, InMemoryHashStore, score

BAND_ICON = {"Clear": "✅", "Doubtful": "⚠️ ", "Suspect": "🚫", "Unassessed": "❔"}


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    backend = config.Settings().build_vision_backend("github")
    print(f"backend={backend.name}  model={backend.model}\n" + "=" * 72)
    for p in paths:
        path = Path(p)
        if not path.is_file():
            print(f"skip (not a file): {p}")
            continue
        ctx = EngineContext(
            tenant_id="dev", vision=backend,
            hash_store=InMemoryHashStore(), scoring=DEFAULT_SCORING,
        )
        v = score(path.read_bytes(), ctx)
        content = next((c for c in v.checks if c.name in ("content", "relevance")), None)
        saw = ""
        if content and content.data:
            saw = content.data.get("scene_description") or content.data.get("summary") or ""
        icon = BAND_ICON.get(v.band, "  ")
        print(f"{icon} {path.name}")
        print(f"    score={v.score:<6} band={v.band:<11} reason={v.reason}")
        if saw:
            print(f"    vision saw: {saw[:120]}")
        print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
