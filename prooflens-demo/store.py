"""
SQLite-backed hash store for the uniqueness check.

We store ONLY the perceptual hash and a small fake "trail" (lead / rep / time)
so the demo can simulate "have we seen this before, and from whom?". We never
store the image itself.

NOTE: the lead/rep/time trail here is fabricated for the demo. In the real LSQ
service this would come from the upload context. -- TODO: wire to real trail.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from config import DB_PATH


@dataclass
class HashMatch:
    distance: int
    phash: str
    lead: str
    rep: str
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hashes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                phash       TEXT NOT NULL,
                lead        TEXT,
                rep         TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def _hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex hash strings."""
    if len(a) != len(b):
        # Different hash sizes — treat as maximally distant.
        return max(len(a), len(b)) * 4
    xor = int(a, 16) ^ int(b, 16)
    return bin(xor).count("1")


def nearest(phash: str) -> Optional[HashMatch]:
    """Return the closest stored hash to `phash`, or None if the store is empty."""
    init_db()
    best: Optional[HashMatch] = None
    with _connect() as conn:
        rows = conn.execute(
            "SELECT phash, lead, rep, created_at FROM hashes"
        ).fetchall()
    for row in rows:
        dist = _hamming_hex(phash, row["phash"])
        if best is None or dist < best.distance:
            best = HashMatch(
                distance=dist,
                phash=row["phash"],
                lead=row["lead"] or "—",
                rep=row["rep"] or "—",
                created_at=row["created_at"],
            )
    return best


def remember(phash: str, lead: str = "demo-lead", rep: str = "demo-rep") -> None:
    """Persist a hash + fake trail. Never stores the image."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO hashes (phash, lead, rep) VALUES (?, ?, ?)",
            (phash, lead, rep),
        )
        conn.commit()


def count() -> int:
    init_db()
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM hashes").fetchone()["n"]
