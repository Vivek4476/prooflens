from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant():
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _repo():
    return InMemoryRepo([_tenant()])


def _row(agent, vf, **kw):
    base = {"agent_id": agent, "sm": None, "rsm": None, "srsm": None,
            "zonal_head": None, "branch": None, "city": None, "valid_from": vf}
    base.update(kw)
    return base


def _result(rep_id, days_ago):
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return ResultView(id="x", created_at=ts, tenant_id="t1", band="Clear",
                      score=90.0, reason="r", reason_code="clear", rubric_version="v3",
                      rep_id=rep_id)


def test_replace_and_get_hierarchy_rows():
    repo = _repo()
    repo.replace_hierarchy("t1", [_row("A1", date(2026, 1, 1), branch="North")], "u1")
    rows = repo.get_hierarchy_rows("t1")
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "A1" and rows[0]["branch"] == "North"
    assert rows[0]["upload_id"] == "u1"


def test_replace_hierarchy_is_atomic_replace_and_normalizes_agent():
    repo = _repo()
    repo.replace_hierarchy("t1", [_row("  a1 ", date(2026, 1, 1))], "u1")
    repo.replace_hierarchy("t1", [_row("B2", date(2026, 2, 1))], "u2")
    rows = repo.get_hierarchy_rows("t1")
    assert [r["agent_id"] for r in rows] == ["B2"]        # u1 fully replaced
    repo.replace_hierarchy("t1", [_row(" a1 ", date(2026, 1, 1))], "u3")
    assert repo.get_hierarchy_rows("t1")[0]["agent_id"] == "A1"   # normalized on store


def test_hierarchy_status_match_rate_over_last_90_days():
    repo = _repo()
    # Results: A1 (matched), A2 (matched), A3 (unmapped), one old (ignored).
    repo.results.extend([
        _result("A1", 1), _result("A2", 10), _result("A3", 20),
        _result("A1", 5),                # duplicate rep -> distinct counts once
        _result("A9", 200),              # older than 90d -> excluded
    ])
    repo.replace_hierarchy("t1", [
        _row("A1", date(2026, 1, 1), valid_from=date(2026, 1, 1)),
        _row("A2", date(2026, 1, 2), valid_from=date(2026, 1, 2)),
    ], "u1")
    st = repo.hierarchy_status("t1")
    assert st["upload_id"] == "u1"
    assert st["row_count"] == 2
    assert st["matched"] == 2 and st["unmapped"] == 1      # A1,A2 matched; A3 unmapped
    assert st["match_rate"] == round(2 / 3, 3)


def test_hierarchy_status_empty_hierarchy():
    repo = _repo()
    repo.results.append(_result("A1", 1))
    st = repo.hierarchy_status("t1")
    assert st == {"upload_id": None, "valid_from": None, "row_count": 0,
                  "match_rate": 0.0, "matched": 0, "unmapped": 1}
