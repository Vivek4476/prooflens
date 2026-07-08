"""ORM model invariants that don't need a live database."""

from __future__ import annotations

from prooflens.db.models import Job, JobStatus

_EXPECTED = ["queued", "in_progress", "done", "failed", "dead_letter"]


def test_job_status_values_match_migration_enum():
    assert [m.value for m in JobStatus] == _EXPECTED


def test_status_column_persists_values_not_member_names():
    # Regression: SQLAlchemy Enum defaults to member NAMES ("QUEUED"); the
    # Postgres enum from the migration uses lowercase VALUES ("queued"). The
    # column must be configured (values_callable) to emit the values, or every
    # INSERT fails with "invalid input value for enum job_status".
    assert set(Job.__table__.c.status.type.enums) == set(_EXPECTED)


def test_tenant_vision_backend_defaults_to_groq():
    from prooflens.db.models import Tenant
    col = Tenant.__table__.c.vision_backend
    assert col.default.arg == "groq"           # ORM-side default


def test_result_has_rep_and_opportunity_columns():
    from prooflens.db.models import Result
    cols = Result.__table__.c
    assert "rep_id" in cols and "opportunity_id" in cols
    assert cols.rep_id.nullable is True
    assert cols.opportunity_id.nullable is True


def test_results_have_tenant_rep_index():
    from prooflens.db.models import Result
    idx = {i.name: [c.name for c in i.columns] for i in Result.__table__.indexes}
    assert "ix_results_tenant_rep" in idx
    assert idx["ix_results_tenant_rep"] == ["tenant_id", "rep_id"]
