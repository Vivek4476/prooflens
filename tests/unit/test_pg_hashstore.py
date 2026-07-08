"""PostgresHashStore contract — offline, no live database.

The nearest-neighbour Hamming search now runs server-side (a Postgres
``bit_count`` popcount over the XOR of two ``bit(64)`` casts), so the distance
maths can't be exercised without Postgres. What we CAN pin offline is the seam
around that query: the SQL is issued with the right parameters and its row is
mapped into a ``HashMatch`` unchanged. A tiny fake session stands in for the
SQLAlchemy session and returns a canned row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from prooflens.db.hashstore import PostgresHashStore
from prooflens.engine.types import HashMatch


@dataclass
class _Row:
    dhash: str
    rep_id: str | None
    opportunity_id: str | None
    created_at: datetime | None
    distance: int


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Records the last execute() call and returns a preset row."""

    def __init__(self, row):
        self._row = row
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params
        return _FakeResult(self._row)


def test_nearest_passes_tenant_and_probe_and_maps_row():
    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    row = _Row(
        dhash="ffffffffffffffff",
        rep_id="rep-1",
        opportunity_id="opp-9",
        created_at=created,
        distance=3,
    )
    session = _FakeSession(row)
    store = PostgresHashStore(session)

    match = store.nearest("tenant-a", "fffffffffffffffe")

    # Query is tenant-scoped and probes with the supplied hash.
    assert session.last_params == {"tenant_id": "tenant-a", "probe": "fffffffffffffffe"}
    sql = str(session.last_sql).lower()
    assert "bit_count" in sql and "order by distance asc, id desc" in sql and "limit 1" in sql

    # Row maps straight through to HashMatch, created_at isoformatted.
    assert match == HashMatch(
        distance=3,
        dhash="ffffffffffffffff",
        rep_id="rep-1",
        opportunity_id="opp-9",
        created_at=created.isoformat(),
    )


def test_nearest_returns_none_when_no_rows():
    store = PostgresHashStore(_FakeSession(None))
    assert store.nearest("tenant-a", "0000000000000000") is None


def test_nearest_handles_missing_created_at():
    row = _Row("00", None, None, None, 0)
    match = PostgresHashStore(_FakeSession(row)).nearest("t", "00")
    assert match is not None and match.created_at is None
