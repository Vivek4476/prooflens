"""The persistence seam: a Repo protocol + an in-memory implementation.

The Postgres implementation lives in prooflens.db.repo and delegates to the real
SKIP-LOCKED queue. Both satisfy this protocol, so the API/worker code is
storage-agnostic and testable fully offline.
"""

from __future__ import annotations

import itertools
from typing import Protocol, runtime_checkable

from ..engine.hashstore import InMemoryHashStore
from ..engine.types import HashStore, Verdict
from .views import JobView, TenantView


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
    def record_result(self, tenant_id: str, job_id: str, verdict: Verdict) -> None: ...
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
        self.results: list[tuple[str, str, Verdict]] = []
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

    def record_result(self, tenant_id: str, job_id: str, verdict: Verdict) -> None:
        self.results.append((tenant_id, job_id, verdict))

    def commit(self) -> None:  # no-op in memory
        pass

    def rollback(self) -> None:  # no-op in memory
        pass

    # --- test helper ---
    def status(self, job_id: str) -> str:
        return self._status.get(job_id, "unknown")
