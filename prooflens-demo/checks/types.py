"""Shared result type for deterministic checks."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    name: str
    passed: bool            # did this check pass its own bar?
    score: float            # 0-100 contribution from this check
    reason: str             # short human-readable summary
    detail: str = ""        # extra detail / raw numbers
    available: bool = True   # False => optional dep missing; result is neutral
    metric: Optional[float] = None  # raw underlying number, if any

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # JSON-friendly: expose "pass" as the API field name.
        d["pass"] = d.pop("passed")
        return d
