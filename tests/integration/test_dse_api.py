# tests/integration/test_dse_api.py
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant():
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


@pytest.fixture
def repo():
    r = InMemoryRepo([_tenant()])
    r.replace_hierarchy(
        "t1",
        [
            {
                "agent_id": "A1", "agent_name": "Asha Verma",
                "sm": "Sam", "rsm": "Ravi", "srsm": "Sr1",
                "zonal_head": "ZoneN", "branch": "North", "city": "Delhi",
                "valid_from": date(2026, 1, 1),
            },
            {
                # No agent_name -> honest fallback to id.
                "agent_id": "A2", "agent_name": None,
                "sm": "Sam", "rsm": "Ravi", "srsm": "Sr1",
                "zonal_head": "ZoneN", "branch": "North", "city": "Delhi",
                "valid_from": date(2026, 1, 1),
            },
        ],
        "up1",
    )
    return r


@pytest.fixture
def client(repo):
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
    return TestClient(app, raise_server_exceptions=False)


def _dt(d: date, hour: int = 12) -> str:
    return datetime(d.year, d.month, d.day, hour, tzinfo=UTC).isoformat()


def _seed_results(repo, rep_id: str, entries: list[tuple[date, str]]) -> None:
    for i, (day, band) in enumerate(entries):
        reason_code = {"Clear": "clear", "Doubtful": "too_blurred", "Suspect": "recycled"}[band]
        repo.results.append(ResultView(
            id=f"{rep_id}-{i}", created_at=_dt(day), tenant_id="t1",
            band=band, score=10.0 if band == "Suspect" else 90.0,
            reason="r", reason_code=reason_code, rubric_version="v3", rep_id=rep_id,
        ))


# --- search -----------------------------------------------------------------


def test_search_finds_by_name_case_insensitive(client):
    r = client.get("/v1/dse", params={"q": "asha"})
    assert r.status_code == 200
    body = r.json()
    assert [x["agent_id"] for x in body["results"]] == ["A1"]
    assert body["results"][0]["name"] == "Asha Verma"
    assert body["results"][0]["branch"] == "North"
    assert body["results"][0]["sm"] == "Sam"


def test_search_finds_by_agent_id_case_insensitive(client):
    r = client.get("/v1/dse", params={"q": "a2"})
    assert r.status_code == 200
    body = r.json()
    assert [x["agent_id"] for x in body["results"]] == ["A2"]
    # No agent_name -> honest fallback to the id itself.
    assert body["results"][0]["name"] == "A2"


def test_search_empty_query_returns_results_capped(client):
    r = client.get("/v1/dse")
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 2


def test_search_no_match_returns_empty_list(client):
    r = client.get("/v1/dse", params={"q": "nobody-like-this"})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_empty_query_orders_by_activity(client, repo):
    # Empty q -> "most active first" (by result count). A2 has more results
    # than A1, so it must lead despite sorting after A1 alphabetically.
    _seed_results(repo, "A1", [(date(2026, 6, 1), "Clear")])
    _seed_results(repo, "A2", [
        (date(2026, 6, 1), "Clear"),
        (date(2026, 6, 2), "Suspect"),
        (date(2026, 6, 3), "Suspect"),
    ])
    r = client.get("/v1/dse")
    ids = [x["agent_id"] for x in r.json()["results"]]
    assert ids == ["A2", "A1"]  # most-active first, not alphabetical


def test_search_caps_results_at_limit(repo):
    # More matching agents than the cap -> only _SEARCH_LIMIT returned.
    from prooflens.api.dse import _SEARCH_LIMIT

    r = InMemoryRepo([_tenant()])
    rows = [
        {
            "agent_id": f"AGT{i:03d}", "agent_name": f"Agent {i}",
            "sm": "Sam", "rsm": "Ravi", "srsm": "Sr1",
            "zonal_head": "ZoneN", "branch": "North", "city": "Delhi",
            "valid_from": date(2026, 1, 1),
        }
        for i in range(_SEARCH_LIMIT + 10)
    ]
    r.replace_hierarchy("t1", rows, "up-many")
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: r
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: r.get_tenant_by_slug("dev")
    c = TestClient(app, raise_server_exceptions=False)

    body = c.get("/v1/dse", params={"q": "agt"}).json()  # matches all by id
    assert len(body["results"]) == _SEARCH_LIMIT


# --- scorecard ----------------------------------------------------------


def test_scorecard_unknown_agent_404(client):
    r = client.get("/v1/dse/NOPE")
    assert r.status_code == 404


def test_scorecard_returns_chain_and_name(client, repo):
    _seed_results(repo, "A1", [(date(2026, 6, 1), "Clear")])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["agent_id"] == "A1"
    assert body["name"] == "Asha Verma"
    assert body["chain"] == {
        "sm": "Sam", "rsm": "Ravi", "srsm": "Sr1",
        "zone": "ZoneN", "branch": "North", "city": "Delhi",
    }


def test_scorecard_missing_agent_name_falls_back_to_id(client, repo):
    _seed_results(repo, "A2", [(date(2026, 6, 1), "Clear")])
    r = client.get("/v1/dse/A2", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.status_code == 200
    assert r.json()["name"] == "A2"


def test_scorecard_totals_and_band_distribution(client, repo):
    _seed_results(repo, "A1", [
        (date(2026, 6, 1), "Clear"),
        (date(2026, 6, 2), "Suspect"),
        (date(2026, 6, 3), "Suspect"),
        (date(2026, 6, 4), "Doubtful"),
    ])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-05"})
    body = r.json()
    assert body["total"] == 4
    assert body["band_distribution"] == {"Clear": 1, "Doubtful": 1, "Suspect": 2, "Unassessed": 0}
    assert body["suspect_rate"] == 0.5
    assert body["avg_score"] == round((90 + 10 + 10 + 90) / 4, 1)


def test_scorecard_trend_has_per_bucket_entries(client, repo):
    _seed_results(repo, "A1", [
        (date(2026, 6, 1), "Suspect"),
        (date(2026, 6, 3), "Clear"),
    ])
    r = client.get("/v1/dse/A1", params={
        "from": "2026-06-01", "to": "2026-06-04", "bucket": "daily",
    })
    body = r.json()
    trend = body["trend"]
    by_label = {t["bucket_label"]: t for t in trend}
    assert by_label["2026-06-01"]["suspect"] == 1
    assert by_label["2026-06-01"]["total"] == 1
    assert by_label["2026-06-01"]["suspect_rate"] == 1.0
    assert by_label["2026-06-02"]["total"] == 0
    assert by_label["2026-06-03"]["total"] == 1
    assert "incomplete" in by_label["2026-06-01"]


def test_scorecard_recent_only_flagged_latest_first(client, repo):
    _seed_results(repo, "A1", [
        (date(2026, 6, 1), "Clear"),
        (date(2026, 6, 2), "Suspect"),
        (date(2026, 6, 3), "Doubtful"),
    ])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-04"})
    recent = r.json()["recent"]
    assert len(recent) == 2
    assert recent[0]["band"] == "Doubtful"   # newest first
    assert recent[1]["band"] == "Suspect"
    assert all(item["band"] != "Clear" for item in recent)


def test_scorecard_top_reasons_shape(client, repo):
    _seed_results(repo, "A1", [
        (date(2026, 6, 1), "Suspect"),
        (date(2026, 6, 2), "Suspect"),
    ])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-03"})
    top = r.json()["top_reasons"]
    assert top[0] == {"reason_code": "recycled", "short_label": "Recycled image", "count": 2}


def test_scorecard_agent_with_hierarchy_row_but_no_results_in_range_is_not_404(client):
    # A1 exists in the hierarchy but has zero results anywhere -> honest zeros,
    # not a 404 (it's a real DSE, just with no activity).
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["band_distribution"] == {"Clear": 0, "Doubtful": 0, "Suspect": 0, "Unassessed": 0}
    assert body["suspect_rate"] == 0.0
    assert body["recent"] == []


def test_scorecard_lowercase_agent_id_normalizes(client, repo):
    _seed_results(repo, "A1", [(date(2026, 6, 1), "Clear")])
    r = client.get("/v1/dse/a1", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.status_code == 200
    assert r.json()["agent_id"] == "A1"


def test_scorecard_truncated_flag_false_for_small(client, repo):
    _seed_results(repo, "A1", [(date(2026, 6, 1), "Clear")])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.json()["truncated"] is False


def test_scorecard_truncated_flag_true_when_over_cap(client, repo, monkeypatch):
    from prooflens.api import dse as dse_mod
    monkeypatch.setattr(dse_mod, "_SCORECARD_LIMIT", 2)
    _seed_results(repo, "A1", [
        (date(2026, 6, 1), "Clear"), (date(2026, 6, 2), "Clear"), (date(2026, 6, 3), "Clear"),
    ])  # 3 results > cap of 2
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-05"})
    assert r.status_code == 200
    assert r.json()["truncated"] is True


def test_search_uses_repo_and_still_finds_by_name(client):
    # Regression: the reworked search still returns the seeded agents by name.
    body = client.get("/v1/dse", params={"q": "asha"}).json()
    assert [x["agent_id"] for x in body["results"]] == ["A1"]
    assert body["results"][0]["name"] == "Asha Verma"
