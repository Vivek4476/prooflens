"""Postgres-backed Repo — the production implementation of the application seam.

Delegates the queue to the real SELECT ... FOR UPDATE SKIP LOCKED drain in
prooflens.queue and tenant resolution to prooflens.tenants. Satisfies the same
Repo protocol as InMemoryRepo, so the API/worker code is unchanged.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from ..engine.types import Verdict
from ..queue import queue as q
from ..service.views import JobView, ResultView, TenantView
from ..tenants.service import resolve_scoring
from .hashstore import PostgresHashStore
from .models import AuditLog, Hierarchy, Job, Result, Tenant


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
        source: str | None = None,
    ) -> str:
        from ..service.ids import normalize_id

        row = Result(
            tenant_id=uuid.UUID(tenant_id),
            job_id=uuid.UUID(job_id) if job_id else None,
            rep_id=normalize_id(rep_id),
            opportunity_id=opportunity_id,
            band=verdict.band,
            score=int(round(verdict.score)),
            reason=verdict.reason,
            reason_code=verdict.reason_code,
            rubric_version=verdict.rubric_version,
            checks=[c.to_dict() for c in verdict.checks],
            source=source or ("webhook" if job_id else "direct"),
        )
        self._session.add(row)
        self._session.flush()
        return str(row.id)

    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        from ..service.ids import normalize_id

        query = self._session.query(Result)
        if band:
            query = query.filter(Result.band == band)
        if reason is not None:
            query = query.filter(Result.reason_code == reason)
        if rep_id is not None:
            query = query.filter(Result.rep_id == normalize_id(rep_id))
        if review == "pending":
            query = query.filter(Result.review_status.is_(None))
        elif review:
            query = query.filter(Result.review_status == review)
        if start is not None:
            query = query.filter(Result.created_at >= start)
        if end is not None:
            query = query.filter(Result.created_at < end)
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
        views = [self._to_view(r, jobs.get(r.job_id) if r.job_id else None) for r in rows]
        return views, total

    def get_result(self, result_id: str) -> ResultView | None:
        try:
            rid = uuid.UUID(result_id)
        except (ValueError, AttributeError):
            return None  # not a valid id => treat as not found, not a 500
        row = self._session.get(Result, rid)
        if row is None:
            return None
        job = self._session.get(Job, row.job_id) if row.job_id else None
        return self._to_view(row, job)

    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        try:
            rid = uuid.UUID(result_id)
        except (ValueError, AttributeError):
            return None
        row = self._session.get(Result, rid)
        if row is None:
            return None
        row.review_status = decision
        row.review_note = note
        row.reviewed_at = datetime.now(UTC)
        row.reviewer = reviewer
        self._session.add(AuditLog(
            tenant_id=row.tenant_id,
            job_id=row.job_id,
            event="review.decision",
            detail={
                "result_id": str(row.id), "decision": decision,
                "note": note, "reviewer": reviewer,
            },
        ))
        self._session.flush()
        job = self._session.get(Job, row.job_id) if row.job_id else None
        return self._to_view(row, job)

    def replace_hierarchy(self, tenant_id: str, rows: list[dict], upload_id: str) -> None:
        from ..service.ids import normalize_id

        tid = uuid.UUID(tenant_id)
        self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).delete()
        for r in rows:
            self._session.add(Hierarchy(
                tenant_id=tid,
                agent_id=normalize_id(r.get("agent_id")),
                agent_name=r.get("agent_name") or None,
                sm=r.get("sm"), rsm=r.get("rsm"), srsm=r.get("srsm"),
                zonal_head=r.get("zonal_head"), branch=r.get("branch"), city=r.get("city"),
                valid_from=r["valid_from"], upload_id=upload_id,
            ))
        self._session.flush()

    def get_hierarchy_rows(self, tenant_id: str) -> list[dict]:
        tid = uuid.UUID(tenant_id)
        rows = self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).all()
        return [{
            "agent_id": h.agent_id, "agent_name": h.agent_name,
            "sm": h.sm, "rsm": h.rsm, "srsm": h.srsm,
            "zonal_head": h.zonal_head, "branch": h.branch, "city": h.city,
            "valid_from": h.valid_from, "upload_id": h.upload_id,
        } for h in rows]

    def hierarchy_status(self, tenant_id: str) -> dict:
        from ..service.ids import normalize_id

        tid = uuid.UUID(tenant_id)
        rows = self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).all()
        cutoff = datetime.now(UTC) - timedelta(days=90)
        result_reps = (
            self._session.query(Result.rep_id)
            .filter(
                Result.tenant_id == tid,
                Result.rep_id.isnot(None),
                Result.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
        rep_ids = {normalize_id(r[0]) for r in result_reps if normalize_id(r[0]) is not None}
        agents = {normalize_id(h.agent_id) for h in rows}
        matched = sum(1 for rid in rep_ids if rid in agents)
        unmapped = len(rep_ids) - matched
        total = matched + unmapped
        upload_id = rows[0].upload_id if rows else None
        valid_from = max((h.valid_from for h in rows), default=None)
        return {
            "upload_id": upload_id,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "row_count": len(rows),
            "match_rate": round(matched / total, 3) if total else 0.0,
            "matched": matched,
            "unmapped": unmapped,
        }

    @staticmethod
    def _to_view(r: Result, job: Job | None) -> ResultView:
        # Prefer the promoted columns; fall back to the originating job payload
        # only for legacy rows the backfill did not reach (defence in depth).
        payload = (job.payload or {}) if job else {}
        rep_id = r.rep_id if r.rep_id is not None else payload.get("rep_id")
        opportunity_id = (
            r.opportunity_id if r.opportunity_id is not None else payload.get("opportunity_id")
        )
        return ResultView(
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
            # Prefer the stored column (set by the migration backfill / this
            # repo going forward); fall back to the job_id derivation only for
            # legacy rows the backfill somehow missed.
            source=r.source if r.source else ("webhook" if r.job_id else "direct"),
            opportunity_id=opportunity_id,
            rep_id=rep_id,
            review_status=r.review_status,
            review_note=r.review_note,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            reviewer=r.reviewer,
        )

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
