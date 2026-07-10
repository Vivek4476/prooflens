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
        aborting the batch.

        SSRF GATE (Phase 3, REQUIRED before RealLSQClient makes a network
        call): ``image_url`` comes from an operator-uploaded CSV — it is
        attacker-influenceable. A real implementation MUST validate the URL
        before fetching: allow only https, resolve the host and reject
        loopback/link-local/private ranges (127.0.0.0/8, ::1, 169.254.0.0/16
        incl. 169.254.169.254, 10/8, 172.16/12, 192.168/16), and ideally
        pin to the tenant's expected LSQ/S3 host allowlist. FakeLSQClient
        makes no network call, so there is no SSRF today — this gate exists
        so Phase 3 cannot inherit the gap silently."""
        ...
