"""Synchronous scoring + read API for the frontend (additive, reuses the engine).

- POST /v1/score        : multipart image -> Verdict (persists a Result row).
- GET  /v1/results      : paginated, newest-first, optional band filter.
- GET  /v1/analytics/summary : aggregates computed from the results store.

These add NO business logic: /v1/score calls the same pure engine the worker
uses; the read endpoints read the same results table the worker writes. See
frontend/BACKEND_REQUIREMENTS.md.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Literal

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from ..config import get_settings
from ..engine import EngineContext, score
from ..engine.types import Verdict
from ..engine.verdicts import REASON_TEXT, Reason
from ..service.repo import Repo, processing_ms
from ..vision.unavailable import UnavailableVision
from .date_range import fill_series, resolve_range
from .deps import get_repo

router = APIRouter(tags=["scoring"])

DEFAULT_TENANT = "dev"  # seeded by scripts/seed_dev_tenant.py / the migrate service

REVIEWER = "Demo Operator"  # placeholder identity until SSO/RBAC (M4)

# Bound how many image scorings run concurrently in this process. Each one
# transiently allocates decode buffers + FFT arrays; on a small instance a
# handful of large images running at once (the threadpool default is ~40) stack
# their spikes into an OOM. Excess requests QUEUE on this limiter — fail-open:
# they wait a moment, they are never rejected.
_SCORE_CONCURRENCY = 2
_score_limiter = anyio.CapacityLimiter(_SCORE_CONCURRENCY)


class ReviewBody(BaseModel):
    decision: Literal["approve", "reject", "false_positive", "escalate"]
    note: str | None = None


@router.post("/v1/score")
async def score_image(
    image: UploadFile = File(...),
    tenant: str = Form(DEFAULT_TENANT),
    backend: str | None = Form(None),
    repo: Repo = Depends(get_repo),
) -> dict:
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    # Offload the whole blocking pipeline — including the synchronous vision HTTP
    # call — to a worker thread. On a single-worker server, running it on the
    # event loop blocked health-check probes during a multi-second inference, so
    # the platform killed the instance mid-request (the 502s we saw on Render).
    # The limiter caps concurrent scorings so their memory spikes can't stack.
    return await anyio.to_thread.run_sync(
        _score_direct, data, tenant, backend, repo, limiter=_score_limiter
    )


def _score_direct(data: bytes, tenant: str, backend: str | None, repo: Repo) -> dict:
    tenant_view = repo.get_tenant_by_slug(tenant)
    if tenant_view is None:
        raise HTTPException(
            status_code=404, detail=f"unknown tenant {tenant!r} (seed a tenant first)"
        )

    settings = get_settings()
    # Direct scoring is operator-driven: the request override wins, else the env
    # VISION_BACKEND. "Demo Model" (stub) always works; anything else is Live AI.
    explicit = backend is not None            # operator named a backend on THIS request
    requested = (backend or settings.vision_backend or "groq").strip().lower()
    # "live_ai" now means the operator EXPLICITLY asked for a non-stub backend, so
    # a misconfiguration should surface loudly (503). The configured default degrades
    # quietly to Doubtful instead (fail-open: score & flag, never block).
    live_ai = explicit and requested != "stub"

    try:
        vision = settings.build_vision_backend(requested)
    except Exception as exc:  # noqa: BLE001
        if explicit:
            # They asked for this specific backend and it's misconfigured — say so.
            raise HTTPException(
                status_code=503, detail=f"Live AI ({requested}) is unavailable: {exc}"
            ) from exc
        # Default path: don't block, don't fake a Clear. Degrade to an unavailable
        # vision so fusion caps the verdict to Doubtful (review).
        vision = UnavailableVision(f"{requested} unavailable: {exc}")

    # Defer hash-remembering until we know the verdict is a keeper: a failed Live
    # AI call must not poison the duplicate store (which would make a retry look
    # like a duplicate and skip the model entirely).
    ctx = EngineContext(
        tenant_id=tenant_view.id,
        vision=vision,
        hash_store=repo.hash_store,
        scoring=tenant_view.scoring,
        remember_hash=False,
    )
    verdict = score(data, ctx)

    # If Live AI was explicitly requested but the model call FAILED (as opposed to
    # being skipped by a cheap hard gate), surface the exact provider error rather
    # than returning a verdict the model never actually produced.
    if live_ai:
        content = next((c for c in verdict.checks if c.name == "content"), None)
        if content is not None and not content.available and (content.data or {}).get("error"):
            detail = (content.data or {}).get("detail") or content.summary
            raise HTTPException(
                status_code=503, detail=f"Live AI ({vision.name}) is unavailable: {detail}"
            )

    # Keeper verdict — remember the hash now, then persist.
    _remember_hash(ctx, verdict)
    result_id = repo.record_result(tenant_view.id, None, verdict)

    payload = verdict.to_dict()
    payload["result_id"] = result_id
    payload["processing_ms"] = processing_ms(verdict)
    payload["backend"] = vision.name
    payload["backend_is_real"] = vision.is_real
    payload["backend_note"] = None
    return payload


def _remember_hash(ctx: EngineContext, verdict: Verdict) -> None:
    """Persist this image's dHash after a kept verdict (mirrors the pipeline's own
    remember step, deferred here via remember_hash=False)."""
    uniq = next((c for c in verdict.checks if c.name == "uniqueness"), None)
    dhash = (uniq.data or {}).get("dhash") if uniq else None
    if dhash:
        ctx.hash_store.remember(
            ctx.tenant_id,
            dhash,
            rep_id=ctx.rep_id,
            opportunity_id=ctx.opportunity_id,
            captured_at=ctx.captured_at,
        )


@router.get("/v1/results")
def list_results(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    band: str | None = Query(None),
    review: str | None = Query(None),
    repo: Repo = Depends(get_repo),
) -> dict:
    items, total = repo.list_results(limit=limit, offset=offset, band=band, review=review)
    return {
        "items": [r.to_dict() for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/v1/results/{result_id}")
def get_result(result_id: str, repo: Repo = Depends(get_repo)) -> dict:
    """A single stored verdict with its full evidence — the Verdict Detail view."""
    result = repo.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"no result {result_id!r}")
    return result.to_dict()


@router.post("/v1/results/{result_id}/review")
def review_result(
    result_id: str, body: ReviewBody, repo: Repo = Depends(get_repo)
) -> dict:
    """Record a moderator decision on a stored verdict (writes an audit event)."""
    view = repo.record_review(result_id, body.decision, body.note, REVIEWER)
    if view is None:
        raise HTTPException(status_code=404, detail=f"no result {result_id!r}")
    return view.to_dict()


@router.get("/v1/analytics/summary")
def analytics_summary(
    repo: Repo = Depends(get_repo),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    # Cheap at demo scale: aggregate the recent results in Python.
    try:
        start, end = resolve_range(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, total = repo.list_results(limit=5000, offset=0, start=start, end=end)

    bands = Counter(r.band for r in items)
    reason_counts = Counter(r.reason_code for r in items)
    scores = [r.score for r in items]
    proc = [r.processing_ms for r in items if r.processing_ms]

    today = datetime.now(UTC).date().isoformat()
    images_today = sum(1 for r in items if (r.created_at or "").startswith(today))

    # Per-day series (band mix + avg score), oldest -> newest, gap-filled.
    by_day: dict[str, list] = {}
    for r in items:
        by_day.setdefault((r.created_at or "")[:10], []).append(r)
    series = fill_series(by_day, start, end)

    # Reason codes are always from the fixed vocabulary; map to the verbatim text.
    top_reasons = [
        {"reason_code": code, "reason": REASON_TEXT[Reason(code)], "count": n}
        for code, n in reason_counts.most_common()
    ]

    return {
        "total": total,
        "images_today": images_today,
        "band_distribution": {b: bands.get(b, 0) for b in ("Clear", "Doubtful", "Suspect")},
        "suspect_pct": round(100 * bands.get("Suspect", 0) / total, 1) if total else 0.0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "avg_processing_ms": round(sum(proc) / len(proc), 1) if proc else 0.0,
        "duplicates_caught": reason_counts.get(Reason.RECYCLED.value, 0),
        "top_reasons": top_reasons,
        "series": series,
    }
