# ProofLens

Async **image-authenticity scoring** for insurance field-force "proof of
meeting" photos uploaded to LeadSquared (LSQ). A webhook carries the image + rep
id + opportunity id; ProofLens runs a pipeline of independent checks, fuses a
**0–100 score** with a **band** (`Suspect` < 40, `Doubtful` 40–69, `Clear` ≥ 70)
and a one-line human-readable **reason**, and writes those three values back to
custom fields on the same LSQ opportunity.

**Philosophy — baked in, not optional:**

- It **scores and flags; it never blocks an upload.** Fail-open: on any failure
  the upload stands and the job retries. Worst case is a delayed score.
- It is a **capture-integrity / triage tool, not a truth detector.** It cannot
  prove a meeting happened and never claims to.
- **No single check decides.** Independent signals fuse; every verdict carries a
  per-check breakdown.
- **Images are never stored** — only the 8-byte dHash + a `(tenant, rep,
  opportunity, timestamp)` trail, for the uniqueness check.
- The content check is **environment-invariant**: "real people in a real
  captured scene vs a screen / graphic / meme / object" — never "does this look
  like an ideal meeting" (field environments vary across city tiers).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md),
[docs/VERDICT_COPY.md](docs/VERDICT_COPY.md),
[docs/RUNBOOK.md](docs/RUNBOOK.md) and
[docs/TENANT_ONBOARDING.md](docs/TENANT_ONBOARDING.md).

## Quickstart (clone → running, offline)

No database, no API keys, no network needed for the engine + CLI + tests. The
default vision backend is a deterministic **stub**.

```bash
git clone https://github.com/Vivek4476/prooflens.git
cd prooflens

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # engine + CLI + test tooling

# Score an image — prints the full Verdict as JSON (verdict → evidence → internals)
python -m prooflens score tests/golden/images/meeting.jpg

# Regenerate the synthetic golden images (already committed)
python scripts/generate_golden.py

# Lint, type-check, and run the full offline test + golden suite
ruff check src tests scripts migrations
mypy src
pytest
```

Example CLI output (trimmed):

```json
{
  "image": "tests/golden/images/meeting.jpg",
  "band": "Clear",
  "score": 89.0,
  "reason": "Clear — no capture-integrity issues found.",
  "reason_code": "clear",
  "checks": [ ... ],
  "rubric_version": "v1"
}
```

## The golden set

`tests/golden/` holds labelled synthetic images and asserts **both the band and
the exact reason string** for each — the reason vocabulary is policy, versioned
alongside `rubrics/`.

| Image | Band | Reason |
|---|---|---|
| `meeting.jpg` | Clear | Clear — no capture-integrity issues found. |
| `blurred.jpg` | Doubtful | Too blurred to assess — please retake in better light. |
| `landscape.jpg` | Suspect | No people or relevant scene detected in the photo. |
| `screenshot.jpg` | Suspect | Designed graphic or screenshot, not a photo of a live scene. |
| `screen_recapture.jpg` | Suspect | Photo of another screen — screen edge and glare detected. |
| `duplicate_a.jpg` → `duplicate_b.jpg` | Clear → Suspect | Recycled image — matches a photo already submitted for this account. |

## Repository layout

```
src/prooflens/
  engine/     pure scoring library: pipeline + checks/ + fusion/ + verdicts
  vision/     VisionBackend protocol; stub (default), anthropic, local_vlm
  db/         SQLAlchemy models, Postgres hash store, crypto (queue/tenants/results/audit/DLQ)
  queue/      Postgres job queue: SKIP LOCKED drain, backoff+jitter, DLQ
  tenants/    per-tenant scoring resolution + credentials
  service/    application seam: Repo (in-memory + Postgres) + per-job processor
  api/        FastAPI: POST /v1/webhooks/lsq/{tenant_slug} (+ /healthz /readyz)
  worker.py   queue-draining worker process (python -m prooflens.worker)
  lsq/        LSQClient protocol + FakeLSQClient (RealLSQClient: Phase 3)
  telemetry/  structured JSON logging (Prometheus /metrics: Phase 3)
  config.py   pydantic-settings, env-driven
rubrics/v1.yaml   the vision prompt IS policy — versioned, stamped into every result
migrations/       Alembic (initial schema: tenants, jobs, image_hashes, results, audit_log)
tests/{unit,integration,golden}/
docs/  deploy/  scripts/  .env.example
frontend/         Next.js 15 enterprise UI (Dashboard/Analyze/History/Review/Analytics/Settings)
  BACKEND_REQUIREMENTS.md   exact API contract the UI consumes + endpoints still required
```

## Run the full stack — API + worker + enterprise UI (Docker)

The engine, CLI and tests never need a database. The **service** (api + worker +
postgres + web) does — `docker compose` runs migrations on boot, seeds a dev
tenant, and serves the frontend:

```bash
docker compose -f deploy/docker-compose.yml up --build
#   db · migrate (schema + seed) · api · worker · web

# UI:      http://localhost:3000        (Dashboard, Analyze, History, Review, Analytics, Settings)
# API docs: http://localhost:8000/docs

# Populate the demo with REAL verdicts (pushes sample images through /v1/score):
python scripts/generate_demo_images.py
cd frontend && npm install && npm run seed:demo
```

For a real vision model instead of the offline stub, start the stack with
`VISION_BACKEND=openrouter` and an `OPENROUTER_API_KEY` in `.env` (the free tier
rate-limits; scoring is fail-open, so a slow/failed model degrades to "scored
without content analysis" rather than breaking). The Analyze page also has a
per-request **Demo model / Live AI** switch.

The frontend is a separate Next.js app in `frontend/` (see
`frontend/BACKEND_REQUIREMENTS.md` for the exact API contract it consumes).

### API only

```bash
curl -s localhost:8000/healthz    # {"status":"ok"}
curl -s localhost:8000/readyz     # {"status":"ready"}  (DB reachable)
curl -s localhost:8000/metrics    # Prometheus: queue depth, band mix, latencies, vision failures

# Create a tenant (admin token defaults to dev-admin-token)
curl -sX POST localhost:8000/admin/tenants -H "X-Admin-Token: dev-admin-token" \
  -H "content-type: application/json" \
  -d '{"slug":"acme","name":"Acme","webhook_secret":"s","field_map":{"band":"B","score":"S","reason":"R"}}'
```

See [docs/TENANT_ONBOARDING.md](docs/TENANT_ONBOARDING.md) for the webhook wiring
and [docs/RUNBOOK.md](docs/RUNBOOK.md) for operations.

Without Docker (against your own Postgres):

```bash
pip install -e ".[service]"
export DATABASE_URL=postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens
alembic upgrade head                       # build the schema
python scripts/seed_dev_tenant.py          # seed one dev tenant
uvicorn prooflens.api.app:app --port 8000  # api  (separate shell:)
python -m prooflens.worker                 # worker
```

## Build phases

- **Phase 1 — "spine" (this milestone):** config, migrations, tenant model +
  seed, queue, pure engine + stub backend, CLI, verdict-copy + design docs, unit
  tests, golden set. ✅
- **Phase 2 — "edges" (this milestone):** webhook (per-tenant signature +
  event-id idempotency), worker process, FakeLSQClient ordered write-back
  (band → score → reason), application seam (in-memory + Postgres repos),
  dedicated golden CI job. ✅ End-to-end offline: signed webhook → queue →
  worker → FakeLSQ shows the three fields; a duplicate event id returns 200 and
  is not reprocessed. The `anthropic`/`local_vlm` backends exist but are **never
  called** without explicit approval.
- **Phase 3 — "production skin" (this milestone):** admin tenant CRUD,
  Prometheus `/metrics` + structured logging, Dockerfile + docker-compose
  (migrations on boot), RUNBOOK + onboarding guide, `RealLSQClient` last with
  the LSQ unknowns stubbed behind marked TODOs. ✅

## Ask-before-guessing: LSQ unknowns (stubbed behind interfaces)

These are stubbed with marked `TODO`s until confirmed — the `RealLSQClient`
(Phase 3) must not guess them:

- **Webhook payload shape + signature scheme** — how LSQ signs the webhook and
  what fields carry the image, rep id and opportunity id.
- **Custom-field ids** for band / score / reason (the write-back targets). The
  dev tenant seeds placeholder ids in `field_map`.
- **API auth + image-fetch endpoint** — if the image arrives by reference rather
  than as bytes, how to authenticate and fetch it.

## Never added

Facial recognition / identity matching · gesture/pose analysis · blocking
behaviour · image persistence · GPS hard gates · per-rep behavioural profiling ·
any dashboard UI (Phase 2 concern) · secrets in code.
