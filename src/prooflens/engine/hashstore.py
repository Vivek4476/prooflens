"""In-memory HashStore — the default for the CLI, golden set and unit tests.

Stores only the 8-byte dHash (as hex) plus a (tenant, rep, opportunity, time)
trail. Never stores images. The Postgres-backed store used by the service lives
in prooflens.db and satisfies the same protocol.
"""

from __future__ import annotations

from .types import HashMatch


def hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex hash strings."""
    if len(a) != len(b):
        return max(len(a), len(b)) * 4
    return bin(int(a, 16) ^ int(b, 16)).count("1")


class InMemoryHashStore:
    """A dict-backed store keyed by tenant. Not persistent — process-local."""

    def __init__(self) -> None:
        # tenant_id -> list of (dhash_hex, rep_id, opportunity_id, captured_at)
        self._rows: dict[str, list[tuple[str, str | None, str | None, str | None]]] = {}

    def nearest(self, tenant_id: str, dhash_hex: str) -> HashMatch | None:
        best: HashMatch | None = None
        for stored, rep, opp, at in self._rows.get(tenant_id, []):
            dist = hamming_hex(dhash_hex, stored)
            if best is None or dist < best.distance:
                best = HashMatch(
                    distance=dist, dhash=stored, rep_id=rep, opportunity_id=opp, created_at=at
                )
        return best

    def remember(
        self,
        tenant_id: str,
        dhash_hex: str,
        *,
        rep_id: str | None = None,
        opportunity_id: str | None = None,
        captured_at: str | None = None,
    ) -> None:
        self._rows.setdefault(tenant_id, []).append(
            (dhash_hex, rep_id, opportunity_id, captured_at)
        )
