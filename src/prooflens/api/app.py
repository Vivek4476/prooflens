"""FastAPI app: the LSQ webhook + health probes.

The webhook acks fast: verify the per-tenant signature, enqueue idempotently on
the event id, and return. A duplicate event id returns 200 without reprocessing.
Scoring happens later in the worker (fail-open: an upload is never blocked).

Storage is injected via the ``get_repo`` dependency so the whole flow is
testable offline with an InMemoryRepo; production yields a PostgresRepo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Request

from ..service.repo import Repo
from .schemas import WebhookAck, WebhookPayload
from .security import SIGNATURE_HEADER, verify


def get_repo() -> Iterator[Repo]:
    """Production dependency: a Postgres-backed repo, committed per request.

    Imports the DB layer lazily so the API module is import-safe without psycopg,
    and so tests (which override this dependency) never touch the database.
    """
    from ..db.base import session_scope
    from ..db.repo import PostgresRepo

    session = session_scope()
    repo = PostgresRepo(session)
    try:
        yield repo
        repo.commit()
    except Exception:
        repo.rollback()
        raise
    finally:
        session.close()


def create_app() -> FastAPI:
    app = FastAPI(title="ProofLens", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict:
        # Phase 3 wires a real DB ping here.
        return {"status": "ready"}

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
