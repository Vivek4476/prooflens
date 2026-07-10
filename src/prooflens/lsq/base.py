"""LSQClient protocol — the seam over LeadSquared write-back.

ProofLens writes exactly three custom fields back to the opportunity, IN ORDER:
band, score, reason (the band is the decision-driver). Everything runs against
:class:`FakeLSQClient` in tests and local dev; the RealLSQClient (Phase 3) is
added last, once the LSQ unknowns are confirmed (see README TODOs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FieldUpdate:
    """One custom-field write. `field_id` is the tenant's mapped LSQ field id."""

    field_id: str
    value: str


@runtime_checkable
class LSQClient(Protocol):
    def update_custom_fields(self, opportunity_id: str, updates: list[FieldUpdate]) -> None:
        """Write the given custom fields to the opportunity, preserving order."""
        ...

    def fetch_image(self, image_url: str) -> bytes:
        """Fetch the bytes of a (private, LSQ-hosted) image by URL/reference.

        Used by the bulk-scoring job (Phase 1): the browser cannot reach LSQ's
        private S3/CDN, so the backend fetches server-side with LSQ
        credentials. Raise on any fetch failure — the caller (the bulk
        service) is fail-open and records a per-row error rather than
        aborting the batch."""
        ...
