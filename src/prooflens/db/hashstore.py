"""Postgres-backed HashStore — the service adapter satisfying engine.HashStore.

Stores only the dHash + trail, never images, and is strictly tenant-scoped.

Phase 1 keeps the nearest-neighbour search simple: fetch the tenant's recent
hashes and compute Hamming distance in Python. This is correct and fine at
current volumes.
TODO(scale): replace with a bit-sliced index / BK-tree, or store the dHash as a
BIGINT and use a popcount(x # y) expression, once a tenant's hash count is large.
"""

from __future__ import annotations

from ..engine.hashstore import hamming_hex
from ..engine.types import HashMatch
from .models import ImageHash

# Cap the candidate scan so a hot tenant can't make a single lookup unbounded.
_MAX_CANDIDATES = 50_000


class PostgresHashStore:
    """Implements the engine's HashStore protocol against the image_hashes table."""

    def __init__(self, session):
        self._session = session

    def nearest(self, tenant_id: str, dhash_hex: str) -> HashMatch | None:
        rows = (
            self._session.query(ImageHash)
            .filter(ImageHash.tenant_id == tenant_id)
            .order_by(ImageHash.id.desc())
            .limit(_MAX_CANDIDATES)
            .all()
        )
        best: HashMatch | None = None
        for row in rows:
            dist = hamming_hex(dhash_hex, row.dhash)
            if best is None or dist < best.distance:
                best = HashMatch(
                    distance=dist,
                    dhash=row.dhash,
                    rep_id=row.rep_id,
                    opportunity_id=row.opportunity_id,
                    created_at=row.created_at.isoformat() if row.created_at else None,
                )
                if dist == 0:
                    break
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
        self._session.add(
            ImageHash(
                tenant_id=tenant_id,
                dhash=dhash_hex,
                rep_id=rep_id,
                opportunity_id=opportunity_id,
                captured_at=captured_at,
            )
        )
        self._session.flush()
