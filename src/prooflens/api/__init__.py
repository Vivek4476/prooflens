"""HTTP surface (FastAPI).

Phase 2 adds POST /v1/webhooks/lsq/{tenant_slug} (per-tenant signature
verification + event-id idempotency: ack fast, enqueue, return). Phase 3 adds
tenant admin CRUD and /healthz /readyz /metrics.
"""
