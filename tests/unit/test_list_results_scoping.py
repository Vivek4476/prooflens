"""list_results must return only the requested tenant's rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.engine.types import CheckOutcome, Verdict
from prooflens.service.hierarchy import node_match
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant(tid: str) -> TenantView:
    return TenantView(id=tid, slug=tid, webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _verdict(band: str = "Clear") -> Verdict:
    return Verdict(
        band=band, score=80.0, reason="x", reason_code="clear",
        rubric_version="v3",
        checks=[CheckOutcome(
            name="content", available=True, score=80.0, summary="s",
            metric=None, data={}, latency_ms=1.0,
        )],
    )


@pytest.fixture
def _repo_with_hierarchy() -> InMemoryRepo:
    repo = InMemoryRepo([TenantView(
        id="t1", slug="dev", webhook_secret="s",
        field_map={}, scoring=ScoringConfig(), vision_backend="stub",
    )])
    d = datetime.now(UTC).date() - timedelta(days=40)
    repo.replace_hierarchy("t1", [
        {"agent_id": "A1", "sm": "SM-North", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": d},
        {"agent_id": "A2", "sm": "SM-South", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "South", "city": None, "valid_from": d},
    ], "u1")
    repo.record_result("t1", None, _verdict(), rep_id="A1")
    repo.record_result("t1", None, _verdict(), rep_id="A2")
    return repo


def _hier_rows() -> list[dict]:
    d = datetime.now(UTC).date() - timedelta(days=40)
    return [
        {"agent_id": "A1", "sm": "SM-North", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": d},
        {"agent_id": "A2", "sm": "SM-South", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "South", "city": None, "valid_from": d},
    ]


def _seed(repo: InMemoryRepo, tid: str, n: int) -> None:
    for i in range(n):
        repo.results.append(ResultView(
            id=f"{tid}-{i}",
            created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
            tenant_id=tid, band="Clear", score=90.0, reason="r",
            reason_code="clear", rubric_version="v3", rep_id="A1",
        ))


def test_list_results_isolates_by_tenant():
    repo = InMemoryRepo([_tenant("t1"), _tenant("t2")])
    _seed(repo, "t1", 3)
    _seed(repo, "t2", 5)

    items, total = repo.list_results(tenant_id="t1", limit=50, offset=0)
    assert total == 3
    assert all(r.tenant_id == "t1" for r in items)

    items2, total2 = repo.list_results(tenant_id="t2", limit=50, offset=0)
    assert total2 == 5
    assert all(r.tenant_id == "t2" for r in items2)

    # An unknown tenant sees nothing.
    _, total3 = repo.list_results(tenant_id="nope", limit=50, offset=0)
    assert total3 == 0


# ---------------------------------------------------------------------------
# node_match pure helper tests
# ---------------------------------------------------------------------------

def test_node_match_true_when_rep_in_node() -> None:
    rows = _hier_rows()
    day = datetime.now(UTC).date()
    assert node_match(rows, "A1", day, "branch", "North") is True
    assert node_match(rows, "A2", day, "branch", "North") is False


def test_node_match_false_for_unmapped_rep() -> None:
    assert node_match(_hier_rows(), "GHOST", datetime.now(UTC).date(), "branch", "North") is False


# ---------------------------------------------------------------------------
# InMemoryRepo.list_results dim+node filter tests
# ---------------------------------------------------------------------------

def test_list_results_filters_by_node(_repo_with_hierarchy: InMemoryRepo) -> None:
    repo = _repo_with_hierarchy
    items, total = repo.list_results(tenant_id="t1", limit=50, offset=0, dim="branch", node="North")
    assert total == 1
    assert all(r.rep_id == "A1" for r in items)  # normalize_id uppercases


def test_list_results_no_filter_unchanged(_repo_with_hierarchy: InMemoryRepo) -> None:
    _, total = _repo_with_hierarchy.list_results(tenant_id="t1", limit=50, offset=0)
    assert total == 2
