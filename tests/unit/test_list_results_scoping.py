"""list_results must return only the requested tenant's rows."""

from __future__ import annotations

from datetime import UTC, datetime

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant(tid: str) -> TenantView:
    return TenantView(id=tid, slug=tid, webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


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
