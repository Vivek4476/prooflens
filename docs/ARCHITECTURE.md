# Architecture

ProofLens is a **modular monolith**: one codebase, one Docker image, two
processes (`api` and `worker`) started by different commands. No Kubernetes, no
Kafka, no Redis, no microservices. This is a deliberate choice, not a stepping
stone.

## Processes

- **api** — FastAPI. Receives LSQ webhooks (verify signature, idempotency-check
  on event id, enqueue, ack fast), serves admin CRUD and `/healthz /readyz
  /metrics`. *(webhook: Phase 2; admin + metrics: Phase 3.)*
- **worker** — drains the Postgres job queue, runs the engine, writes the three
  fields back to LSQ. *(Phase 2.)*

## PostgreSQL does triple duty

One database is the tenants store, the job queue, the uniqueness hash store, the
results store, the audit log, and the dead-letter queue.

- **Queue**: the `jobs` table, drained with `SELECT ... FOR UPDATE SKIP LOCKED`.
  `attempts` + `scheduled_at` drive exponential backoff with full jitter; a job
  that exhausts `max_attempts` moves to `dead_letter`. A `429` honours
  `Retry-After`; a `529` is treated as provider overload — back off but **do not**
  count it against the retry budget.
- **Idempotency**: a unique `(tenant_id, event_id)` constraint; a duplicate
  webhook is a no-op that returns the existing job.

## Multi-tenant from day one

`tenants` holds the webhook secret, LSQ credentials (Fernet-encrypted at rest,
key from env), custom-field mappings, scoring overrides, and vision-backend
choice. **Every table carries `tenant_id`; every query is tenant-scoped**,
including the uniqueness hash store.

## The engine is a pure library

`src/prooflens/engine/` imports **no** HTTP, queue, or LSQ code:

```python
engine.score(image_bytes, context) -> Verdict
```

The vision backend and hash store are injected via `EngineContext`, so the same
engine powers the CLI (in-memory store, stub backend), the worker (Postgres
store, configured backend), and a future batch module — without change.

## The pipeline (cheap → costly)

Free gates short-circuit before the paid vision call:

1. **EXIF** — timestamp/GPS as soft bonuses; never gates (EXIF is strippable,
   clocks/GPS are user-controllable).
2. **Sharpness** — Laplacian variance; unreadable → a quality flag ("retake"),
   never a heavy penalty on its own.
3. **Uniqueness** — dHash vs the tenant hash store; Hamming 0 = exact duplicate
   (hard gate), ≤ 6 = near-duplicate (flag). Stores hash + trail, **never the
   image**.
4. **Recapture** — moiré (FFT), specular glare, screen-bezel; "photo of another
   screen" is a hard gate. The primary defence against laundered saved/AI images
   under the live-camera lock.
5. **Content (vision)** — structured, pydantic-validated JSON. Environment-
   invariant: "real people in a real captured scene vs screen/graphic/meme/
   object", never "does this look like an ideal meeting". Malformed output is
   retried once, then scored without this check.
6. **Fusion** — weighted blend of the soft signals + hard-gate floors. Every
   weight/threshold/cap is resolved per tenant; no magic numbers in the logic.

## Rubric is versioned policy

The vision prompt lives in `rubrics/v1.yaml`. Its `version` is stamped into
every `Verdict` as `rubric_version`. Changing the prompt or output fields
requires a **new** version file and a golden-set update in the same PR.

## Fail-open

Nothing blocks an upload. On any failure the upload stands, the job retries, and
the worst case is a delayed score. ProofLens **scores and flags**; it never
blocks, never stores images, and never claims to prove a meeting happened.
