"""Load the versioned content rubric (the vision prompt IS policy).

The rubric lives in ``rubrics/<version>.yaml`` at the repo root. Every backend
loads it so the prompt and output contract are identical across models, and the
``version`` string is stamped into every Verdict as ``rubric_version``.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml


def _rubrics_dir() -> Path:
    override = os.getenv("PROOFLENS_RUBRICS_DIR")
    if override:
        return Path(override)
    # src/prooflens/vision/rubric.py -> repo root is three parents up from the
    # package root (prooflens/). parents: [vision, prooflens, src, <root>].
    return Path(__file__).resolve().parents[3] / "rubrics"


@functools.cache
def load_rubric(version: str = "v1") -> dict:
    path = _rubrics_dir() / f"{version}.yaml"
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data.get("version") != version:
        raise ValueError(
            f"rubric {path} declares version {data.get('version')!r}, expected {version!r}"
        )
    return data


# Active rubric version. Bumping this requires a new rubrics/<version>.yaml and a
# golden-set review in the same PR.
RUBRIC_VERSION = "v3"

_ACTIVE = load_rubric(RUBRIC_VERSION)
SYSTEM_PROMPT: str = _ACTIVE["system_prompt"]
USER_PROMPT: str = _ACTIVE["user_prompt"]
OUTPUT_FIELDS: tuple[str, ...] = tuple(_ACTIVE["output_fields"])
