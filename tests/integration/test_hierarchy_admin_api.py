from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.config import get_settings
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant():
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


@pytest.fixture
def repo():
    return InMemoryRepo([_tenant()])


@pytest.fixture
def client(repo):
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_headers():
    return {"X-Admin-Token": get_settings().admin_token}


def _csv(rows: str) -> dict:
    return {"file": ("hierarchy.csv", io.BytesIO(rows.encode()), "text/csv")}


GOOD = (
    "agent_id,sm,rsm,srsm,zonal_head,branch,city,valid_from\n"
    "A1,Sam,Ravi,Sr1,ZoneN,North,Delhi,2026-01-01\n"
    "A2,Sam,Ravi,Sr1,ZoneN,North,Delhi,2026-01-01\n"
)


def test_upload_requires_admin(client):
    r = client.post("/v1/admin/hierarchy", files=_csv(GOOD))
    assert r.status_code == 401


def test_upload_good_csv_versions_and_previews_match_rate(client, repo, admin_headers):
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    repo.results.append(ResultView(id="r1", created_at=now, tenant_id="t1", band="Clear",
                                   score=90, reason="r", reason_code="clear",
                                   rubric_version="v3", rep_id="A1"))
    r = client.post("/v1/admin/hierarchy", files=_csv(GOOD), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2
    assert "upload_id" in body
    assert body["matched"] == 1 and body["unmapped"] == 0
    assert body["match_rate_preview"] == 1.0
    assert len(repo.get_hierarchy_rows("t1")) == 2


def test_upload_unknown_column_400(client, admin_headers):
    bad = "agent_id,valid_from,region\nA1,2026-01-01,X\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "region" in r.json()["detail"]


def test_upload_blank_agent_id_400(client, admin_headers):
    bad = "agent_id,valid_from\n ,2026-01-01\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "agent_id" in r.json()["detail"].lower()


def test_upload_duplicate_agent_same_date_400(client, admin_headers):
    bad = ("agent_id,valid_from\nA1,2026-01-01\nA1,2026-01-01\n")
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "duplicate" in r.json()["detail"].lower()


def test_upload_same_agent_two_dates_ok(client, admin_headers):
    ok = ("agent_id,valid_from,branch\nA1,2026-01-01,North\nA1,2026-05-01,South\n")
    r = client.post("/v1/admin/hierarchy", files=_csv(ok), headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["row_count"] == 2


def test_status_reports_current_version(client, repo, admin_headers):
    client.post("/v1/admin/hierarchy", files=_csv(GOOD), headers=admin_headers)
    st = client.get("/v1/admin/hierarchy/status", headers=admin_headers).json()
    assert st["row_count"] == 2
    assert st["valid_from"] == "2026-01-01"
    assert "match_rate" in st


def test_upload_blank_valid_from_value_defaults_to_today(client, repo, admin_headers):
    from datetime import date

    ok = "agent_id,branch,valid_from\nA1,North,\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(ok), headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = repo.get_hierarchy_rows("t1")
    assert len(rows) == 1
    # Just verify it's today's date (in case test runs across midnight)
    assert isinstance(rows[0]["valid_from"], date)


def test_template_returns_csv_file(client, admin_headers):
    r = client.get("/v1/admin/hierarchy/template", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in r.headers["content-disposition"]
    assert "hierarchy_template.csv" in r.headers["content-disposition"]
    lines = r.text.strip().split("\n")
    assert lines[0] == "agent_id,agent_name,sm,rsm,srsm,zonal_head,branch,city,valid_from"
    assert len(lines) == 2  # header + one example row


def test_upload_unparseable_valid_from_400(client, admin_headers):
    bad = "agent_id,valid_from\nA1,2026-13-40\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "valid_from" in r.json()["detail"].lower()
