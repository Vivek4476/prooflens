"""FastAPI app: the LSQ webhook + health probes.

The webhook acks fast: verify the per-tenant signature, enqueue idempotently on
the event id, and return. A duplicate event id returns 200 without reprocessing.
Scoring happens later in the worker (fail-open: an upload is never blocked).

Storage is injected via the ``get_repo`` dependency so the whole flow is
testable offline with an InMemoryRepo; production yields a PostgresRepo.
"""

from __future__ import annotations

import json

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from ..service.repo import Repo
from ..telemetry import configure_logging
from ..telemetry import metrics as m
from .admin import router as admin_router
from .deps import get_repo
from .schemas import WebhookAck, WebhookPayload
from .scoring import router as scoring_router
from .security import SIGNATURE_HEADER, verify


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="ProofLens", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(admin_router)
    app.include_router(scoring_router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict:
        # Ready = the database is reachable (the worker/queue depend on it).
        from sqlalchemy import text

        from ..db.base import session_scope

        try:
            session = session_scope()
            try:
                session.execute(text("SELECT 1"))
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"not ready: {exc}") from exc
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics() -> Response:
        # Refresh the queue-depth gauge on scrape; other metrics are pushed live.
        try:
            from ..db.base import session_scope
            from ..queue.queue import depth

            session = session_scope()
            try:
                m.QUEUE_DEPTH.set(depth(session))
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — never let a DB blip break scraping
            pass
        body, content_type = m.render()
        return Response(content=body, media_type=content_type)

    @app.post("/v1/webhooks/lsq/{tenant_slug}", response_model=WebhookAck)
    async def lsq_webhook(
        tenant_slug: str,
        request: Request,
        repo: Repo = Depends(get_repo),
    ) -> WebhookAck:
        body = await request.body()

        tenant = repo.get_tenant_by_slug(tenant_slug)
        if tenant is None:
            raise HTTPException(status_code=404, detail="unknown tenant")

        if not verify(tenant.webhook_secret, body, request.headers.get(SIGNATURE_HEADER)):
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            payload = WebhookPayload.model_validate_json(body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid payload: {exc}") from exc

        job_id, created = repo.enqueue(tenant.id, payload.event_id, payload.model_dump())
        # Ack fast. Duplicate event id -> 200, no reprocess.
        return WebhookAck(status="accepted" if created else "duplicate", job_id=job_id)

    return app


app = create_app()
