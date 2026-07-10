"""Bulk photo-scoring endpoints (Phase 1, additive).

POST /v1/bulk-score        : starts a background job scoring a batch of rows.
GET  /v1/bulk-score/{id}   : job status + per-row results (progress-pollable).

Reuses the same scoring core as /v1/score (``score_bytes``) and the same
Result persistence (``source="bulk"``); adds no new business logic. See
docs/superpowers/specs/2026-07-10-bulk-upload-design.md and
frontend/BACKEND_REQUIREMENTS.md.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..lsq.base import LSQClient
from ..lsq.fake import FakeLSQClient
from ..service.bulk import BulkRow, RepoFactory, registry, run_bulk_job
from ..service.repo import Repo
from .deps import get_repo, get_repo_factory

router = APIRouter(tags=["bulk"])

DEFAULT_TENANT = "dev"

# Hard cap on rows per bulk request. Every row's {url, ids, result} is held in
# memory for the job's lifetime; an uncapped `rows` list lets a single POST
# (bypassing the frontend) allocate arbitrary memory on an instance already
# prone to OOM. Larger exports are split client-side. Phase 3's durable queue
# streams rows and lifts this ceiling.
MAX_BULK_ROWS = 1000


class BulkRowIn(BaseModel):
    image_url: str
    rep_id: str | None = None
    opportunity_id: str | None = None


class BulkScoreRequest(BaseModel):
    rows: list[BulkRowIn] = Field(min_length=1, max_length=MAX_BULK_ROWS)
    label: str | None = None


def get_lsq_client() -> LSQClient:
    # TODO(Phase 3): swap for a per-tenant RealLSQClient once LSQ credentials
    # + fetch-by-reference auth are confirmed (see lsq/real.py TODOs). Every
    # test and local run uses the fake, matching the worker's default.
    return FakeLSQClient()


@router.post("/v1/bulk-score")
def start_bulk_score(
    body: BulkScoreRequest,
    background_tasks: BackgroundTasks,
    repo: Repo = Depends(get_repo),
    lsq: LSQClient = Depends(get_lsq_client),
    repo_factory: RepoFactory = Depends(get_repo_factory),
) -> dict:
    tenant_view = repo.get_tenant_by_slug(DEFAULT_TENANT)
    if tenant_view is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown tenant {DEFAULT_TENANT!r} (seed a tenant first)",
        )

    rows = [
        BulkRow(image_url=r.image_url, rep_id=r.rep_id, opportunity_id=r.opportunity_id)
        for r in body.rows
    ]
    job = registry.create(total=len(rows), label=body.label)

    background_tasks.add_task(
        run_bulk_job,
        job,
        rows,
        tenant_slug=DEFAULT_TENANT,
        lsq=lsq,
        repo_factory=repo_factory,
    )
    return {"job_id": job.id, "total": job.total}


@router.get("/v1/bulk-score/{job_id}")
def get_bulk_score(job_id: str) -> dict:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"no bulk job {job_id!r}")
    return job.to_dict()
