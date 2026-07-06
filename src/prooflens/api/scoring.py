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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ..config import get_settings
from ..engine import EngineContext, score
from ..engine.verdicts import REASON_TEXT, Reason
from ..service.repo import Repo, processing_ms
from .deps import get_repo

router = APIRouter(tags=["scoring"])

DEFAULT_TENANT = "dev"  # seeded by scripts/seed_dev_tenant.py / the migrate service


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

    tenant_view = repo.get_tenant_by_slug(tenant)
    if tenant_view is None:
        raise HTTPException(
            status_code=404, detail=f"unknown tenant {tenant!r} (seed a tenant first)"
        )

    settings = get_settings()
    # Never call a paid backend implicitly: the request/tenant/env chooses it.
    chosen = backend or tenant_view.vision_backend or settings.vision_backend
    vision = settings.build_vision_backend(chosen)

    ctx = EngineContext(
        tenant_id=tenant_view.id,
        vision=vision,
        hash_store=repo.hash_store,
        scoring=tenant_view.scoring,
    )
    verdict = score(data, ctx)
    result_id = repo.record_result(tenant_view.id, None, verdict)

    payload = verdict.to_dict()
    payload["result_id"] = result_id
    payload["processing_ms"] = processing_ms(verdict)
    payload["backend"] = vision.name
    payload["backend_is_real"] = vision.is_real
    return payload


@router.get("/v1/results")
def list_results(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    band: str | None = Query(None),
    repo: Repo = Depends(get_repo),
) -> dict:
    items, total = repo.list_results(limit=limit, offset=offset, band=band)
    return {
        "items": [r.to_dict() for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/v1/analytics/summary")
def analytics_summary(repo: Repo = Depends(get_repo)) -> dict:
    # Cheap at demo scale: aggregate the recent results in Python.
    items, total = repo.list_results(limit=5000, offset=0)

    bands = Counter(r.band for r in items)
    reason_counts = Counter(r.reason_code for r in items)
    scores = [r.score for r in items]
    proc = [r.processing_ms for r in items if r.processing_ms]

    today = datetime.now(UTC).date().isoformat()
    images_today = sum(1 for r in items if (r.created_at or "").startswith(today))

    # Per-day series (band mix + avg score), oldest -> newest.
    by_day: dict[str, list] = {}
    for r in items:
        day = (r.created_at or "")[:10]
        by_day.setdefault(day, []).append(r)
    series = []
    for day in sorted(by_day):
        rows = by_day[day]
        day_scores = [x.score for x in rows]
        series.append({
            "date": day,
            "count": len(rows),
            "clear": sum(1 for x in rows if x.band == "Clear"),
            "doubtful": sum(1 for x in rows if x.band == "Doubtful"),
            "suspect": sum(1 for x in rows if x.band == "Suspect"),
            "avg_score": round(sum(day_scores) / len(day_scores), 1) if day_scores else 0,
        })

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
