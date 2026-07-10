"""search_hierarchy + result_counts_by_rep on InMemoryRepo."""

from __future__ import annotations

from datetime import UTC, date, datetime

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _repo() -> InMemoryRepo:
    r = InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                                 scoring=ScoringConfig(), vision_backend="stub")])
    r.replace_hierarchy("t1", [
        {"agent_id": "A1", "agent_name": "Asha Verma", "sm": "Sam", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": date(2026, 1, 1)},
        {"agent_id": "A2", "agent_name": "50%_special", "sm": "Sam", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": date(2026, 1, 1)},
    ], "up1")
    return r


def test_search_by_name_and_id():
    r = _repo()
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "asha", 25)] == ["A1"]
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "a2", 25)] == ["A2"]


def test_like_metacharacters_match_literally():
    # "%_" must match the literal name "50%_special", not act as wildcards.
    r = _repo()
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "%_special", 25)] == ["A2"]


def test_search_limit_caps():
    r = _repo()
    assert len(r.search_hierarchy("t1", "", 1)) == 1  # empty q matches all, capped


def test_result_counts_by_rep_scoped_and_counted():
    r = _repo()
    ts = datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat()
    for i, rep in enumerate(["A1", "A1", "A2"]):
        r.results.append(ResultView(id=f"x{i}", created_at=ts,
                                    tenant_id="t1", band="Clear", score=90.0, reason="r",
                                    reason_code="clear", rubric_version="v3", rep_id=rep))
    # a different tenant's row must not count
    r.results.append(ResultView(id="y", created_at=ts,
                                tenant_id="t2", band="Clear", score=90.0, reason="r",
                                reason_code="clear", rubric_version="v3", rep_id="A1"))
    counts = r.result_counts_by_rep("t1", None, None)
    assert counts == {"A1": 2, "A2": 1}
