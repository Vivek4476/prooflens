"""Deterministic, server-side checks for ProofLens.

Each check exposes `run(image_bytes) -> CheckResult`. Checks degrade gracefully:
if an optional dependency (OpenCV / Pillow / imagehash) is missing, the check
returns `available=False` with a neutral score rather than crashing the request.
"""

from .types import CheckResult
from . import sharpness, uniqueness, person, metadata

__all__ = ["CheckResult", "sharpness", "uniqueness", "person", "metadata"]
