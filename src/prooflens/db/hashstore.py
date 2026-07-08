"""Postgres-backed HashStore — the service adapter satisfying engine.HashStore.

Stores only the dHash + trail, never images, and is strictly tenant-scoped.

Nearest-neighbour search is done entirely server-side: the 64-bit dHash is
stored as 16 hex chars, so the Hamming distance is the popcount of the XOR of
the two hashes. Postgres computes that as ``bit_count(a # b)`` over ``bit(64)``
casts, and we order by that distance (ties broken toward the most recent row)
and return only the closest one. This avoids loading a tenant's whole hash
history into Python — a single indexed scan returns exactly one row.

The Python semantics this replaces: iterate rows newest-first, keep the row with
the smallest Hamming distance, ties resolved to the first seen (i.e. the most
recent, highest ``id``). The ``ORDER BY distance ASC, id DESC LIMIT 1`` below is
exactly that, so authenticity scoring is unchanged.
"""

from __future__ import annotations

from sqlalchemy import text

from ..engine.types import HashMatch
from .models import ImageHash

# The nearest-neighbour query. ``('x' || lpad(h, 16, '0'))::bit(64)`` turns the
# 16-hex-char dHash into a 64-bit bit string; ``a # b`` is XOR and
# ``bit_count(...)`` (Postgres 14+) is the popcount, i.e. the Hamming distance.
# Ordering ``distance ASC, id DESC`` reproduces the old "smallest distance, ties
# to the most recent" behaviour, and LIMIT 1 returns just the closest row.
_NEAREST_SQL = text(
    """
    SELECT
        dhash,
        rep_id,
        opportunity_id,
        created_at,
        bit_count(
            ('x' || lpad(dhash, 16, '0'))::bit(64)
            # ('x' || lpad(:probe, 16, '0'))::bit(64)
        ) AS distance
    FROM image_hashes
    WHERE tenant_id = :tenant_id
    ORDER BY distance ASC, id DESC
    LIMIT 1
    """
)


class PostgresHashStore:
    """Implements the engine's HashStore protocol against the image_hashes table."""

    def __init__(self, session):
        self._session = session

    def nearest(self, tenant_id: str, dhash_hex: str) -> HashMatch | None:
        row = self._session.execute(
            _NEAREST_SQL, {"tenant_id": tenant_id, "probe": dhash_hex}
        ).first()
        if row is None:
            return None
        return HashMatch(
            distance=int(row.distance),
            dhash=row.dhash,
            rep_id=row.rep_id,
            opportunity_id=row.opportunity_id,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )

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
