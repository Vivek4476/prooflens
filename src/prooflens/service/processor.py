"""Per-job application logic: image bytes -> Verdict -> ordered LSQ write-back.

Pure application code: depends only on the Repo/LSQ protocols and the pure
engine, so it runs identically against the in-memory and Postgres repos.
"""

from __future__ import annotations

import base64

from ..config import Settings
from ..engine import EngineContext, Verdict, score
from ..engine.verdicts import Reason
from ..lsq.base import FieldUpdate, LSQClient
from ..queue.errors import FatalError
from .repo import Repo
from .views import JobView, TenantView


def _resolve_image_bytes(payload: dict) -> bytes:
    b64 = payload.get("image_base64")
    if b64:
        try:
            return base64.b64decode(b64)
        except Exception as exc:  # noqa: BLE001
            raise FatalError(f"invalid base64 image: {exc}") from exc
    if payload.get("image_url"):
        # TODO(LSQ): fetch-by-reference — auth + image endpoint unknown (see README).
        raise FatalError("image arrived by reference; RealLSQ image fetch is a Phase 3 TODO")
    raise FatalError("webhook payload has no image_base64 or image_url")


def _ordered_updates(tenant: TenantView, verdict: Verdict) -> list[FieldUpdate]:
    """Band, score, reason — in that order (band is the decision-driver)."""
    fm = tenant.field_map
    return [
        FieldUpdate(fm["band"], verdict.band),
        FieldUpdate(fm["score"], str(verdict.score)),
        FieldUpdate(fm["reason"], verdict.reason),
    ]


def process_job(job: JobView, *, repo: Repo, lsq: LSQClient, settings: Settings) -> Verdict:
    tenant = repo.get_tenant(job.tenant_id)
    if tenant is None:
        raise FatalError(f"unknown tenant {job.tenant_id}")

    image_bytes = _resolve_image_bytes(job.payload)
    # Never call a paid backend implicitly: the tenant chooses (default stub).
    backend = settings.build_vision_backend(tenant.vision_backend)

    ctx = EngineContext(
        tenant_id=tenant.id,
        vision=backend,
        hash_store=repo.hash_store,
        scoring=tenant.scoring,
        rep_id=job.payload.get("rep_id"),
        opportunity_id=job.payload.get("opportunity_id"),
        captured_at=job.payload.get("captured_at"),
    )
    verdict = score(image_bytes, ctx)

    # Write the three fields back to LSQ IN ORDER: band, score, reason.
    opportunity_id = job.payload.get("opportunity_id")
    if opportunity_id:
        lsq.update_custom_fields(opportunity_id, _ordered_updates(tenant, verdict))

    repo.record_result(tenant.id, job.id, verdict)
    # A verdict is always producible (fail-open): NO_CONTENT_ANALYSIS is a valid
    # outcome, not an error.
    assert verdict.reason_code in {r.value for r in Reason}
    return verdict
