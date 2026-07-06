"""Postgres-backed Repo — the production implementation of the application seam.

Delegates the queue to the real SELECT ... FOR UPDATE SKIP LOCKED drain in
prooflens.queue and tenant resolution to prooflens.tenants. Satisfies the same
Repo protocol as InMemoryRepo, so the API/worker code is unchanged.
"""

from __future__ import annotations

import uuid

from ..engine.types import Verdict
from ..queue import queue as q
from ..service.views import JobView, ResultView, TenantView
from ..tenants.service import resolve_scoring
from .hashstore import PostgresHashStore
from .models import Job, Result, Tenant


def _tenant_view(t: Tenant) -> TenantView:
    return TenantView(
        id=str(t.id),
        slug=t.slug,
        webhook_secret=t.webhook_secret,
        field_map=dict(t.field_map or {}),
        scoring=resolve_scoring(t),
        vision_backend=t.vision_backend,
    )


def _job_view(j: Job) -> JobView:
    return JobView(
        id=str(j.id),
        tenant_id=str(j.tenant_id),
        event_id=j.event_id,
        payload=dict(j.payload or {}),
        attempts=j.attempts,
        max_attempts=j.max_attempts,
    )


class PostgresRepo:
    """Wraps a SQLAlchemy session. One instance per worker loop / request."""

    def __init__(self, session):
        self._session = session
        self.hash_store = PostgresHashStore(session)

    def get_tenant_by_slug(self, slug: str) -> TenantView | None:
        t = self._session.query(Tenant).filter(
            Tenant.slug == slug, Tenant.active.is_(True)
        ).one_or_none()
        return _tenant_view(t) if t else None

    def get_tenant(self, tenant_id: str) -> TenantView | None:
        t = self._session.get(Tenant, uuid.UUID(tenant_id))
        return _tenant_view(t) if t else None

    def enqueue(self, tenant_id: str, event_id: str, payload: dict) -> tuple[str, bool]:
        tid = uuid.UUID(tenant_id)
        existing = (
            self._session.query(Job)
            .filter(Job.tenant_id == tid, Job.event_id == event_id)
            .one_or_none()
        )
        if existing is not None:
            return str(existing.id), False
        job = q.enqueue(self._session, tenant_id=tid, event_id=event_id, payload=payload)
        return str(job.id), True

    def claim_batch(self, limit: int) -> list[JobView]:
        return [_job_view(j) for j in q.claim_batch(self._session, limit=limit)]

    def complete(self, job_id: str) -> None:
        job = self._session.get(Job, uuid.UUID(job_id))
        q.complete(self._session, job)

    def fail(self, job_id: str, error: Exception) -> None:
        job = self._session.get(Job, uuid.UUID(job_id))
        q.fail(self._session, job, error)

    def record_result(
        self,
        tenant_id: str,
        job_id: str | None,
        verdict: Verdict,
        *,
        opportunity_id: str | None = None,
        rep_id: str | None = None,
    ) -> str:
        row = Result(
            tenant_id=uuid.UUID(tenant_id),
            job_id=uuid.UUID(job_id) if job_id else None,
            band=verdict.band,
            score=int(round(verdict.score)),
            reason=verdict.reason,
            reason_code=verdict.reason_code,
            rubric_version=verdict.rubric_version,
            checks=[c.to_dict() for c in verdict.checks],
        )
        self._session.add(row)
        self._session.flush()
        return str(row.id)

    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None
    ) -> tuple[list[ResultView], int]:
        query = self._session.query(Result)
        if band:
            query = query.filter(Result.band == band)
        total = query.count()
        rows = (
            query.order_by(Result.created_at.desc()).offset(offset).limit(limit).all()
        )
        # Pull the trail (rep/opportunity) from the originating job when present.
        job_ids = [r.job_id for r in rows if r.job_id is not None]
        jobs = (
            {j.id: j for j in self._session.query(Job).filter(Job.id.in_(job_ids)).all()}
            if job_ids
            else {}
        )
        views: list[ResultView] = []
        for r in rows:
            job = jobs.get(r.job_id) if r.job_id else None
            payload = (job.payload or {}) if job else {}
            views.append(
                ResultView(
                    id=str(r.id),
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    tenant_id=str(r.tenant_id),
                    band=r.band,
                    score=float(r.score),
                    reason=r.reason,
                    reason_code=r.reason_code,
                    rubric_version=r.rubric_version,
                    checks=list(r.checks or []),
                    processing_ms=round(
                        sum(float(c.get("latency_ms") or 0.0) for c in (r.checks or [])), 1
                    ),
                    source="webhook" if r.job_id else "direct",
                    opportunity_id=payload.get("opportunity_id"),
                    rep_id=payload.get("rep_id"),
                )
            )
        return views, total

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
