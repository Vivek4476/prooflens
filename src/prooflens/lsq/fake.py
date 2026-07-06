"""FakeLSQClient — the in-memory LSQ used by all tests and local dev.

Records every custom-field write per opportunity, preserving write order, so a
test can assert the three fields were written as (band, score, reason). Makes no
network calls.
"""

from __future__ import annotations

from .base import FieldUpdate


class FakeLSQClient:
    is_real = False

    def __init__(self) -> None:
        # opportunity_id -> ordered list of (field_id, value) as written
        self.writes: dict[str, list[tuple[str, str]]] = {}

    def update_custom_fields(self, opportunity_id: str, updates: list[FieldUpdate]) -> None:
        log = self.writes.setdefault(opportunity_id, [])
        for u in updates:
            log.append((u.field_id, u.value))

    # --- test helpers ---
    def fields(self, opportunity_id: str) -> dict[str, str]:
        """Final value of each field for an opportunity."""
        return {fid: val for fid, val in self.writes.get(opportunity_id, [])}

    def order(self, opportunity_id: str) -> list[str]:
        """The field ids in the order they were written."""
        return [fid for fid, _ in self.writes.get(opportunity_id, [])]
