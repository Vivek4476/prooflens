"""The persistence seam: a Repo protocol + an in-memory implementation.

The Postgres implementation lives in prooflens.db.repo and delegates to the real
SKIP-LOCKED queue. Both satisfy this protocol, so the API/worker code is
storage-agnostic and testable fully offline.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from ..engine.hashstore import InMemoryHashStore
from ..engine.types import HashStore, Verdict
from .views import JobView, ResultView, TenantView


def processing_ms(verdict: Verdict) -> float:
    """Total wall-clock across all checks the pipeline ran (for the metric)."""
    return round(sum((c.latency_ms or 0.0) for c in verdict.checks), 1)


@runtime_checkable
class Repo(Protocol):
    hash_store: HashStore

    def get_tenant_by_slug(self, slug: str) -> TenantView | None: ...
    def get_tenant(self, tenant_id: str) -> TenantView | None: ...

    def enqueue(self, tenant_id: str, event_id: str, payload: dict) -> tuple[str, bool]:
        """Return (job_id, created). created=False for a duplicate event id."""
        ...

    def claim_batch(self, limit: int) -> list[JobView]: ...
    def complete(self, job_id: str) -> None: ...
    def fail(self, job_id: str, error: Exception) -> None: ...

    def record_result(
        self,
        tenant_id: str,
        job_id: str | None,
        verdict: Verdict,
        *,
        opportunity_id: str | None = None,
        rep_id: str | None = None,
    ) -> str:
        """Persist a result and return its id. job_id None => a direct /v1/score."""
        ...

    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
    ) -> tuple[list[ResultView], int]:
        """Newest-first page of results + total matching count.
        review="pending" => undecided only; other value => exact review_status match."""
        ...

    def get_result(self, result_id: str) -> ResultView | None:
        """A single stored result by id, or None if it doesn't exist."""
        ...

    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        """Record a moderator decision on a result; write an audit event.
        Returns the updated view, or None if result_id is unknown."""
        ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class InMemoryRepo:
    """Dict/list-backed Repo for tests and local dev. Not concurrency-safe."""

    def __init__(self, tenants: list[TenantView] | None = None):
        self.hash_store: HashStore = InMemoryHashStore()
        self._tenants: dict[str, TenantView] = {t.id: t for t in (tenants or [])}
        self._by_slug: dict[str, TenantView] = {t.slug: t for t in (tenants or [])}
        self._jobs: dict[str, JobView] = {}
        self._by_event: dict[tuple[str, str], str] = {}
        self._queued: list[str] = []
        self._status: dict[str, str] = {}
        self.results: list[ResultView] = []
        self.audit_log: list[dict] = []
        self._ids = itertools.count(1)

    def add_tenant(self, tenant: TenantView) -> None:
        self._tenants[tenant.id] = tenant
        self._by_slug[tenant.slug] = tenant

    def get_tenant_by_slug(self, slug: str) -> TenantView | None:
        return self._by_slug.get(slug)

    def get_tenant(self, tenant_id: str) -> TenantView | None:
        return self._tenants.get(tenant_id)

    def enqueue(self, tenant_id: str, event_id: str, payload: dict) -> tuple[str, bool]:
        key = (tenant_id, event_id)
        if key in self._by_event:
            return self._by_event[key], False
        job_id = str(next(self._ids))
        self._jobs[job_id] = JobView(
            id=job_id, tenant_id=tenant_id, event_id=event_id, payload=payload
        )
        self._by_event[key] = job_id
        self._queued.append(job_id)
        self._status[job_id] = "queued"
        return job_id, True

    def claim_batch(self, limit: int) -> list[JobView]:
        claimed: list[JobView] = []
        while self._queued and len(claimed) < limit:
            job_id = self._queued.pop(0)
            self._status[job_id] = "in_progress"
            job = self._jobs[job_id]
            job.attempts += 1
            claimed.append(job)
        return claimed

    def complete(self, job_id: str) -> None:
        self._status[job_id] = "done"

    def fail(self, job_id: str, error: Exception) -> None:
        job = self._jobs[job_id]
        if job.attempts >= job.max_attempts:
            self._status[job_id] = "dead_letter"
        else:
            self._status[job_id] = "queued"
            self._queued.append(job_id)  # immediate re-queue (no backoff in-memory)

    def record_result(
        self,
        tenant_id: str,
        job_id: str | None,
        verdict: Verdict,
        *,
        opportunity_id: str | None = None,
        rep_id: str | None = None,
    ) -> str:
        rid = str(next(self._ids))
        self.results.append(
            ResultView(
                id=rid,
                created_at=datetime.now(UTC).isoformat(),
                tenant_id=tenant_id,
                band=verdict.band,
                score=verdict.score,
                reason=verdict.reason,
                reason_code=verdict.reason_code,
                rubric_version=verdict.rubric_version,
                checks=[c.to_dict() for c in verdict.checks],
                processing_ms=processing_ms(verdict),
                source="webhook" if job_id else "direct",
                opportunity_id=opportunity_id,
                rep_id=rep_id,
            )
        )
        return rid

    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
    ) -> tuple[list[ResultView], int]:
        rows = [r for r in self.results if band is None or r.band == band]
        if review == "pending":
            rows = [r for r in rows if r.review_status is None]
        elif review:
            rows = [r for r in rows if r.review_status == review]
        rows = list(reversed(rows))  # newest first
        return rows[offset : offset + limit], len(rows)

    def get_result(self, result_id: str) -> ResultView | None:
        return next((r for r in self.results if r.id == result_id), None)

    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        view = next((r for r in self.results if r.id == result_id), None)
        if view is None:
            return None
        view.review_status = decision
        view.review_note = note
        view.reviewed_at = datetime.now(UTC).isoformat()
        view.reviewer = reviewer
        self.audit_log.append({
            "event": "review.decision",
            "tenant_id": view.tenant_id,
            "job_id": None,
            "detail": {"result_id": result_id, "decision": decision, "note": note, "reviewer": reviewer},
        })
        return view

    def commit(self) -> None:  # no-op in memory
        pass

    def rollback(self) -> None:  # no-op in memory
        pass

    # --- test helper ---
    def status(self, job_id: str) -> str:
        return self._status.get(job_id, "unknown")
