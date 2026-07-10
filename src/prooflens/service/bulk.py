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

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import anyio

from ..lsq.base import LSQClient
from .repo import Repo

RepoFactory = Callable[[], tuple[Repo, Callable[[], None]]]

# Small fixed concurrency cap: never load/fetch the whole folder into memory
# at once (Render has OOM'd before on unbounded concurrency — see scoring.py).
BULK_CONCURRENCY = 4

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
        # dict preserves insertion order, so the first key is the oldest job.
        while len(self._jobs) > MAX_RETAINED_JOBS:
            del self._jobs[next(iter(self._jobs))]
        return job

    def get(self, job_id: str) -> BulkJob | None:
        return self._jobs.get(job_id)

    def active_count(self) -> int:
        """Jobs not yet done (queued or running) — the in-flight fan-out."""
        return sum(1 for j in self._jobs.values() if j.status != "done")


# Process-wide singleton registry (mirrors the process-wide score concurrency
# limiter in api/scoring.py — Phase 1 is single-instance by design).
registry = BulkJobRegistry()


async def run_bulk_job(
    job: BulkJob,
    rows: list[BulkRow],
    *,
    tenant_slug: str,
    lsq: LSQClient,
    repo_factory: RepoFactory,
    backend: str | None = None,
) -> None:
    """Fetch -> score -> record_result for every row, bounded by a small
    concurrency cap. Fail-open per row; never raises (a row's exception is
    caught and recorded as that row's error, and the batch continues).

    ``repo_factory()`` must return a fresh ``(Repo, close)`` pair for the
    caller's storage backend (e.g. a new PostgresRepo/session in production,
    or the same InMemoryRepo instance with a no-op close in tests) — one call
    per row, so concurrent rows never share a single mutable session.
    """
    job.status = "running"
    semaphore = asyncio.Semaphore(BULK_CONCURRENCY)
    # Preallocate slots so results stay in row order regardless of completion order.
    job.results = [
        BulkRowResult(image_url=r.image_url, rep_id=r.rep_id, opportunity_id=r.opportunity_id)
        for r in rows
    ]

    async def _process(index: int, row: BulkRow) -> None:
        async with semaphore:
            out = job.results[index]
            try:
                data = await anyio.to_thread.run_sync(lsq.fetch_image, row.image_url)
                repo, close = repo_factory()
                try:
                    # Imported here to avoid a circular import at module load.
                    # _score_limiter is the SAME process-wide CapacityLimiter
                    # /v1/score uses: bulk scorings must share it so their memory
                    # spikes queue behind (not stack on top of) live scoring —
                    # BULK_CONCURRENCY only bounds rows within one job, not bulk
                    # jobs against each other or against live traffic (the exact
                    # unbounded-concurrency OOM scoring.py guards against).
                    from ..api.scoring import _score_limiter, score_bytes

                    tenant_view = repo.get_tenant_by_slug(tenant_slug)
                    if tenant_view is None:
                        raise RuntimeError(f"unknown tenant {tenant_slug!r}")
                    payload = await anyio.to_thread.run_sync(
                        lambda: score_bytes(
                            data,
                            tenant_view=tenant_view,
                            backend=backend,
                            repo=repo,
                            rep_id=row.rep_id,
                            opportunity_id=row.opportunity_id,
                            source="bulk",
                        ),
                        limiter=_score_limiter,
                    )
                    repo.commit()
                    # data (image bytes) is discarded here — never stored, only
                    # the hash + verdict persisted (inside score_bytes/record_result).
                    out.band = payload["band"]
                    out.score = int(round(payload["score"]))
                    out.reason_code = payload["reason_code"]
                    out.result_id = payload["result_id"]
                except Exception:
                    repo.rollback()
                    raise
                finally:
                    close()
            except Exception as exc:  # noqa: BLE001 — fail-open: record, keep going
                out.error = str(exc)[:500]
            finally:
                job.processed += 1

    async with anyio.create_task_group() as tg:
        for i, row in enumerate(rows):
            tg.start_soon(_process, i, row)

    job.status = "done"
