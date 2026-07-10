"""Bulk photo-scoring service (Phase 1, additive — see the design spec at
docs/superpowers/specs/2026-07-10-bulk-upload-design.md).

An operator uploads an LSQ export (rows of {image_url, rep_id?, opportunity_id?});
this module fetches each image server-side (LSQ images are private — see
``LSQClient.fetch_image``), scores it through the SAME engine core /v1/score
uses (``api.scoring.score_bytes``), and persists a normal ``Result`` row with
``source="bulk"`` plus the row's rep/opportunity attribution.

Fail-open per row: a fetch or scoring error is caught, recorded as
``{"error": ...}`` for that row, and the batch continues — one bad row never
aborts the job. Throttled: a small fixed concurrency cap (never the whole
batch fetched/held in memory at once). Images are never stored — only the
hash + verdict persist, exactly as for /v1/score.

Job state lives in an in-memory registry keyed by job_id (Phase 1: single
instance; Phase 3 seam is a durable queue, noted in BACKEND_REQUIREMENTS.md).
Results ALSO persist as normal Result rows via record_result, so they show up
in analytics/history/review regardless of the registry's lifetime (process
restart loses in-flight job progress, not the scored data).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import anyio

from ..lsq.base import LSQClient
from ..service.views import TenantView
from .repo import Repo

RepoFactory = Callable[[], tuple[Repo, Callable[[], None]]]

# Per-job cap on rows processed concurrently — never fan out the whole batch at
# once (Render has OOM'd before on unbounded concurrency — see scoring.py).
BULK_CONCURRENCY = 4

# Process-wide cap on concurrent image FETCHES across ALL bulk jobs. Each fetch
# holds a full image's bytes in memory; the per-job BULK_CONCURRENCY bounds rows
# within one job but not jobs against each other, so without this up to
# MAX_INFLIGHT_JOBS × BULK_CONCURRENCY fetches could stack. Mirrors the
# _score_limiter pattern that bounds decodes (scoring is capped by that limiter).
BULK_FETCH_CONCURRENCY = 6
_fetch_limiter = anyio.CapacityLimiter(BULK_FETCH_CONCURRENCY)

JobStatus = Literal["queued", "running", "done"]


@dataclass
class BulkRow:
    image_url: str
    rep_id: str | None = None
    opportunity_id: str | None = None


@dataclass
class BulkRowResult:
    image_url: str
    rep_id: str | None = None
    opportunity_id: str | None = None
    band: str | None = None
    score: int | None = None
    reason_code: str | None = None
    result_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_url": self.image_url,
            "rep_id": self.rep_id,
            "opportunity_id": self.opportunity_id,
            "band": self.band,
            "score": self.score,
            "reason_code": self.reason_code,
            "result_id": self.result_id,
            "error": self.error,
        }


@dataclass
class BulkJob:
    id: str
    total: int
    label: str | None = None
    status: JobStatus = "queued"
    processed: int = 0
    results: list[BulkRowResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "processed": self.processed,
            "total": self.total,
            "results": [r.to_dict() for r in self.results],
        }


# Keep at most this many jobs in the in-memory registry. A long-lived process
# would otherwise retain every job (rows + per-row results) forever; evict the
# oldest once over the cap. Phase 3's durable queue removes this ceiling.
MAX_RETAINED_JOBS = 200

# Cap concurrent in-flight (queued/running) bulk jobs. Each running job fans out
# fetches + scorings; without this a caller could loop POST /v1/bulk-score and
# spawn unbounded background jobs (compounding the OOM surface even with the
# shared score limiter). Over this cap the endpoint rejects with 429.
MAX_INFLIGHT_JOBS = 3


class BulkJobRegistry:
    """In-memory job store keyed by job_id. Not persisted — Phase 1 scope
    (see the module docstring + BACKEND_REQUIREMENTS.md Phase 3 seam)."""

    def __init__(self) -> None:
        self._jobs: dict[str, BulkJob] = {}

    def create(self, total: int, label: str | None = None) -> BulkJob:
        job_id = str(uuid.uuid4())
        job = BulkJob(id=job_id, total=total, label=label)
        self._jobs[job_id] = job
        if len(self._jobs) > MAX_RETAINED_JOBS:
            # Evict oldest DONE jobs only — never drop a queued/running job a
            # client is still polling (that would 404 a live job). In-flight
            # jobs are bounded by MAX_INFLIGHT_JOBS, so there are always enough
            # done jobs to fall back under the cap. dict preserves insertion
            # order, so iterating yields oldest-first.
            for jid in list(self._jobs):
                if len(self._jobs) <= MAX_RETAINED_JOBS:
                    break
                if jid != job_id and self._jobs[jid].status == "done":
                    del self._jobs[jid]
        return job

    def get(self, job_id: str) -> BulkJob | None:
        return self._jobs.get(job_id)

    def active_count(self) -> int:
        """Jobs not yet done (queued or running) — the in-flight fan-out."""
        return sum(1 for j in self._jobs.values() if j.status != "done")


# Process-wide singleton registry (mirrors the process-wide score concurrency
# limiter in api/scoring.py — Phase 1 is single-instance by design).
registry = BulkJobRegistry()


def _score_and_record_row(
    data: bytes,
    row: BulkRow,
    tenant_view: TenantView,
    backend: str | None,
    repo_factory: RepoFactory,
) -> dict[str, Any]:
    """Synchronous score + persist for one row, run inside a worker thread.

    Everything blocking (a fresh repo/session, the vision call, the DB write,
    commit/close) stays OFF the event loop — running these on the loop would
    stall health-check probes and concurrent scoring, the exact Render
    502/OOM-kill scenario /v1/score offloads to avoid. ``score_bytes`` is the
    SAME core /v1/score uses; the image bytes are discarded on return (only the
    hash + verdict persist)."""
    from ..api.scoring import score_bytes

    repo, close = repo_factory()
    try:
        payload = score_bytes(
            data,
            tenant_view=tenant_view,
            backend=backend,
            repo=repo,
            rep_id=row.rep_id,
            opportunity_id=row.opportunity_id,
            source="bulk",
        )
        repo.commit()
        return payload
    except Exception:
        repo.rollback()
        raise
    finally:
        close()


async def run_bulk_job(
    job: BulkJob,
    rows: list[BulkRow],
    *,
    tenant_slug: str,
    lsq: LSQClient,
    repo_factory: RepoFactory,
    backend: str | None = None,
) -> None:
    """Fetch -> score -> record_result for every row, bounded by concurrency
    limiters. Fail-open per row; never raises (a row's exception is caught and
    recorded as that row's error, and the batch continues).

    Fetches share a process-wide ``_fetch_limiter``; scoring shares the
    process-wide ``_score_limiter`` /v1/score uses — so neither stacks memory
    spikes across bulk jobs or against live traffic. ``repo_factory()`` returns
    a fresh ``(Repo, close)`` pair per row, off the event loop, so concurrent
    rows never share a mutable session.
    """
    # _score_limiter is the SAME process-wide CapacityLimiter /v1/score uses.
    # Imported inside the function (not at module load) to keep the import graph
    # acyclic and lazy. Once per job, not per row.
    from ..api.scoring import _score_limiter

    job.status = "running"
    # Preallocate slots so results stay in row order regardless of completion order.
    job.results = [
        BulkRowResult(image_url=r.image_url, rep_id=r.rep_id, opportunity_id=r.opportunity_id)
        for r in rows
    ]

    # Resolve the tenant ONCE for the whole batch, off the event loop. TenantView
    # is a detached snapshot, safe to reuse across each row's own repo/session.
    def _resolve_tenant() -> TenantView | None:
        repo, close = repo_factory()
        try:
            return repo.get_tenant_by_slug(tenant_slug)
        finally:
            close()

    tenant_view = await anyio.to_thread.run_sync(_resolve_tenant)
    if tenant_view is None:
        for out in job.results:
            out.error = f"unknown tenant {tenant_slug!r}"
        job.processed = len(job.results)
        job.status = "done"
        return

    semaphore = anyio.Semaphore(BULK_CONCURRENCY)

    async def _process(index: int, row: BulkRow) -> None:
        async with semaphore:
            out = job.results[index]
            try:
                data = await anyio.to_thread.run_sync(
                    lsq.fetch_image, row.image_url, limiter=_fetch_limiter
                )
                payload = await anyio.to_thread.run_sync(
                    _score_and_record_row,
                    data,
                    row,
                    tenant_view,
                    backend,
                    repo_factory,
                    limiter=_score_limiter,
                )
                out.band = payload["band"]
                out.score = int(round(payload["score"]))
                out.reason_code = payload["reason_code"]
                out.result_id = payload["result_id"]
            except Exception as exc:  # noqa: BLE001 — fail-open: record, keep going
                out.error = str(exc)[:500]
            finally:
                job.processed += 1

    async with anyio.create_task_group() as tg:
        for i, row in enumerate(rows):
            tg.start_soon(_process, i, row)

    job.status = "done"
