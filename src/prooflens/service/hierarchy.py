"""Pure effective-dated hierarchy resolver + node vocabulary.

A result maps to the hierarchy row whose agent_id equals the result's rep_id
(normalized on both sides) and whose valid_from is the LATEST date on or before
the result's scored date. No match -> None (the "Unmapped" node). Effective-
dated so org changes never rewrite historical reports."""

from __future__ import annotations

from datetime import date

from .ids import normalize_id

# The six org levels a result can be grouped by, coarse -> fine is not implied.
NODE_FIELDS: tuple[str, ...] = ("sm", "rsm", "srsm", "zonal_head", "branch", "city")


def resolve_node(rows: list[dict], agent_id: str | None, scored_date: date) -> dict | None:
    """Return the effective hierarchy row for this agent at scored_date, or None.

    rows: hierarchy rows as dicts, each with at least "agent_id" (str) and
    "valid_from" (datetime.date). Picks the row with the latest valid_from that
    is <= scored_date among rows matching the normalized agent_id."""
    key = normalize_id(agent_id)
    if key is None:
        return None
    best: dict | None = None
    for row in rows:
        if normalize_id(row.get("agent_id")) != key:
            continue
        vf = row["valid_from"]
        if vf > scored_date:
            continue
        if best is None or vf > best["valid_from"]:
            best = row
    return best


def agent_display_name(rows: list[dict], rep_id: str | None) -> str:
    """The DSE's display name for `rep_id`: the hierarchy's `agent_name` when any
    row for this agent carries one (across all effective-dated versions, newest
    first — a name is a slow-changing fact, not effective-dated like the org
    chain), else the normalized agent_id itself (honest fallback, never blank)."""
    key = normalize_id(rep_id)
    if key is None:
        return rep_id or ""
    candidates = [row for row in rows if normalize_id(row.get("agent_id")) == key]
    candidates.sort(key=lambda r: r["valid_from"], reverse=True)
    for row in candidates:
        name = row.get("agent_name")
        if name:
            return str(name)
    return key
