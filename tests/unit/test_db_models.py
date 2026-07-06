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
