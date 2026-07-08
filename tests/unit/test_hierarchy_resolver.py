# tests/unit/test_hierarchy_resolver.py
from __future__ import annotations

from datetime import date

from prooflens.service.hierarchy import NODE_FIELDS, resolve_node


def _row(agent, valid_from, **kw):
    base = {"agent_id": agent, "valid_from": valid_from}
    base.update(kw)
    return base


def test_resolve_none_agent_is_unmapped():
    rows = [_row("A1", date(2026, 1, 1), branch="North")]
    assert resolve_node(rows, None, date(2026, 6, 1)) is None


def test_resolve_no_matching_agent_is_unmapped():
    rows = [_row("A1", date(2026, 1, 1), branch="North")]
    assert resolve_node(rows, "A2", date(2026, 6, 1)) is None


def test_resolve_picks_latest_valid_from_on_or_before_scored_date():
    rows = [
        _row("A1", date(2026, 1, 1), branch="North"),
        _row("A1", date(2026, 5, 1), branch="South"),   # rep moved on May 1
    ]
    # Before the move -> North
    assert resolve_node(rows, "A1", date(2026, 3, 15))["branch"] == "North"
    # On/after the move -> South
    assert resolve_node(rows, "A1", date(2026, 5, 1))["branch"] == "South"
    assert resolve_node(rows, "A1", date(2026, 7, 1))["branch"] == "South"


def test_resolve_before_earliest_valid_from_is_unmapped():
    rows = [_row("A1", date(2026, 5, 1), branch="South")]
    assert resolve_node(rows, "A1", date(2026, 1, 1)) is None


def test_resolve_normalizes_ids_on_both_sides():
    rows = [_row("REP-9", date(2026, 1, 1), branch="North")]
    assert resolve_node(rows, "  rep-9 ", date(2026, 6, 1))["branch"] == "North"


def test_node_fields_are_the_six_levels():
    assert NODE_FIELDS == ("sm", "rsm", "srsm", "zonal_head", "branch", "city")
