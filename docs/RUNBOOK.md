# ProofLens Runbook

Operational guide for running and troubleshooting ProofLens. Golden rule:
**ProofLens is fail-open.** It never blocks an upload; the worst failure mode is
a delayed or missing score, never a blocked rep. Treat incidents with that
priority — restore scoring, don't panic about uploads.

## Topology

One image, two long-running processes plus a one-shot migrator:

- **api** — `uvicorn prooflens.api.app:app` — webhook + admin + health/metrics.
- **worker** — `python -m prooflens.worker` — drains the queue, scores, writes back.
- **migrate** — `alembic upgrade head` (+ optional seed) — runs on boot, exits.

State lives entirely in **PostgreSQL** (tenants, queue, hash store, results,
audit, DLQ).

## Start / stop

```bash
# Local stack (postgres + migrate + api + worker)
docker compose -f deploy/docker-compose.yml up --build

# Health
curl -s localhost:8000/healthz     # {"status":"ok"} — process is up
curl -s localhost:8000/readyz      # {"status":"ready"} — DB reachable (503 if not)
curl -s localhost:8000/metrics     # Prometheus exposition
```

Migrations run automatically via the `migrate` service before `api`/`worker`
start. To run them by hand: `alembic upgrade head`.

## Configuration & secrets

All via env (never in code). Required in staging/prod:

- `DATABASE_URL`
- `PROOFLENS_SECRET_KEY` — Fernet key for encrypting tenant LSQ creds at rest.
  Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  **Rotating it invalidates existing encrypted credentials** — re-enter each
  tenant's LSQ creds via the admin API after a rotation.
- `PROOFLENS_ADMIN_TOKEN` — bearer token for the admin API.

Never log image bytes or credentials. Logs are structured JSON with a `job_id`
carried end-to-end.

## Monitoring (the four signals)

Scrape `/metrics`:

| Metric | What it tells you |
|---|---|
| `prooflens_queue_depth` | Backlog. Sustained growth ⇒ worker too slow / stuck. |
| `prooflens_check_latency_ms` | Per-check latency. The content (vision) check dominates. |
| `prooflens_vision_call_failures_total` | Vision backend failing ⇒ scores degrade to "scored without content analysis". |
| `prooflens_band_total{tenant,band}` | **Band distribution per tenant — the cheap drift detector.** A sudden shift (e.g. Suspect share spikes) means a rubric/model regression or a real upstream change. |

Suggested alerts: queue depth > N for 10m; vision failure rate > 5%; a tenant's
band mix shifts > X% week-over-week.

## Playbooks

### Queue backing up
1. `curl /metrics | grep queue_depth`. Confirm growth.
2. Check worker logs for repeated `job.failed`.
3. Likely a downstream dependency (vision backend or LSQ). Because retries use
   exponential backoff + jitter, a flapping dependency self-heals; a hard-down
   one fills the DLQ.

### Jobs dead-lettering
Dead-lettered jobs have `status = 'dead_letter'` in `jobs`, with `last_error`.
```sql
SELECT id, tenant_id, event_id, attempts, last_error
FROM jobs WHERE status = 'dead_letter' ORDER BY updated_at DESC LIMIT 50;
```
To replay after fixing the root cause, reset to `queued`, clear the schedule:
```sql
UPDATE jobs SET status='queued', attempts=0, scheduled_at=now(), last_error=NULL
WHERE id = '<job-id>';
```

### Upstream rate limits / overload
- A `429` from a provider honours `Retry-After`.
- A `529` (provider overloaded) backs off but **does not** count against the
  job's retry budget — so a provider outage does not dead-letter healthy jobs.

### Vision backend down
Scores degrade gracefully to **"scored without content analysis"** (band never
Clear). No job is lost; fix the backend and future jobs recover. This is
expected fail-open behaviour, not an outage of ProofLens.

## Data & privacy

ProofLens **never stores images** — only the 8-byte dHash + a `(tenant, rep,
opportunity, timestamp)` trail for the uniqueness check. There is no image blob
to purge. Tenant deletion is a **soft delete** (`active=false`) to preserve the
audit trail.
