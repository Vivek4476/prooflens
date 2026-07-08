# Retire the stub backend as the production default

- **Date:** 2026-07-08
- **Branch:** `backend/retire-stub-default`
- **Status:** Design approved; pending spec review before implementation plan.

## Problem

The stub vision backend (`src/prooflens/vision/stub.py`) is the production default
(`VISION_BACKEND=stub` in `config.py`, `render.yaml`, and the `image_hashes`/tenant
DB default). It is a deterministic colour-count + skin-tone heuristic, **not** real
scene understanding, and it declares `is_real = False`.

In production it silently produces real-looking verdicts. Observed case (result
`576ecbc6-…`): a photo of a random shop returned **Clear**. A shop's warm brown/tan
tones tripped the stub's permissive "skin ⇒ people present" RGB mask, which inflates
`plausibility` and (since the stub mirrors `visit_context = plausibility`) pushes
`visit_context` above the scene-relevance flag bands. The scene-relevance Suspect gate
(PR #5) never received a genuine signal, so an irrelevant photo passed as Clear.

## Goals

- No fake **Clear** verdict can reach a real user.
- A real vision backend (**groq**) is the production default.
- With no API key configured, scoring degrades to **Doubtful** (review) — never Clear,
  never a hard block. This honours the project's core principle: *fail-open, scores &
  flags, never blocks.*

## Non-goals

- **Not** deleting the stub code. It stays as a test-only / offline-CLI fixture — the
  golden-set CI regression suite is tuned to its heuristics
  (`scripts/generate_golden.py`).
- **Not** force-migrating existing `stub` tenants.
- **Not** changing the scene-relevance gate thresholds.

## Design

### 1. Production default → groq

- `config.py`: `vision_backend` field default `"stub"` → `"groq"`.
- Literal `or "stub"` fallbacks (`config.py:139`, `api/scoring.py:79`) → `or "groq"`,
  so the stub is never the *implicit* default anywhere.
- `render.yaml`: `VISION_BACKEND` `value: stub` → `groq`; comment that `GROQ_API_KEY`
  must be set, else images cap to Doubtful.
- `deploy/docker-compose.yml`: default → groq, with a documented `VISION_BACKEND=stub`
  override for offline local runs.

### 2. No-key behaviour → cap to Doubtful, never 503 on the default path

- **Current:** `api/scoring.py:84-91` raises `503` whenever a live backend cannot be
  constructed (e.g. missing key).
- **New:** distinguish an *explicit operator override* from the *configured default*.
  - **Default path** (no explicit per-request `backend`): if the default backend can't
    be constructed, pass an unavailable/sentinel vision to the engine so
    `engine/checks/relevance.py:29` returns `available=False` → `engine/fusion/fuse.py:131`
    fires `NO_CONTENT_ANALYSIS` → verdict capped to Doubtful. **No 503.**
  - **Explicit override path** (operator names a live backend in the request): keep the
    `503` — they asked for that backend; surface the exact error.
  - The discriminator is the `backend` request param in `_score_direct`
    (`backend is not None` ⇒ explicit) vs. falling back to `settings.vision_backend`.
  - **Worker path:** the async worker (`service/processor.py`) builds a backend per
    tenant and is not an HTTP request, so it cannot 503. It must apply the same rule —
    a missing-key construction failure degrades to an unavailable vision (→ Doubtful),
    never an uncaught exception that crashes the job. (Note: the worker is not deployed
    on the current Render free plan; the `/v1/score` path is what serves production —
    but the code path is fixed for correctness regardless.)

### 3. Stays on stub (unchanged)

- **CLI** (`src/prooflens/__main__.py`, `--backend` default `stub`) — the offline dev tool.
- **Tests, golden set, CI** — remain fully offline on stub. `vision/stub.py` and
  `get_backend("stub")` are unchanged; the stub is still selectable *by name*.
- **Verify:** no test relies on the *implicit* config default being stub (grep tests
  for `EngineContext` / `build_vision_backend` built without an explicit backend).

### 4. Tenant default, docs, frontend

- `db/models.py:60` server default `"stub"` → `"groq"` via a new alembic migration
  (applies to **new** tenants only; existing rows untouched).
- Docs updated — README, `docs/DEPLOYMENT.md`, `docs/TENANT_ONBOARDING.md`,
  `docs/DESIGN_PRINCIPLES.md`, `BRAND.md`: groq is the default; the stub is explicitly
  test-only and never a production judgement.
- Frontend `[STUB]` / "Simulated" label (`frontend/src/components/verdict/ChecksList.tsx`)
  — **keep** it; still correct for dev/CLI. No change.

## Behaviour changes (summary)

| Scenario | Before | After |
|---|---|---|
| prod, key set | real AI (if configured) | real AI (default) |
| prod, **no key** | stub → possibly fake **Clear** | vision unavailable → **Doubtful**, never Clear, no block |
| operator explicit live backend, misconfigured | 503 | 503 (unchanged) |
| CLI / tests | stub | stub (unchanged) |

## Testing

- Golden set unchanged (still stub-based, offline).
- **New:** no-key default path → a real photo caps to Doubtful (never Clear).
- **New:** explicit override to a misconfigured live backend still returns 503.
- Update the affected `api` / `fusion` tests for the no-503 default path.

## Rollout

- Ships as a normal PR. On merge to `main`, Render redeploys with `VISION_BACKEND=groq`.
- **Operator action:** set `GROQ_API_KEY` on Render **before/at merge**. Otherwise every
  image caps to Doubtful (review) until the key is configured — loud in the review queue,
  not silent; acceptable under fail-open, but avoidable by setting the key first.
- **OpenAPI:** no payload-shape change → no frontend `gen:api` regen needed. Verdict
  fields are unchanged; only the band distribution shifts.

## Risks

- If `GROQ_API_KEY` is not set on Render at deploy, all images cap to Doubtful until
  configured. Mitigate by setting the key first.
- Low blast radius on tests: stub remains for CI, so the golden regression backbone is
  intact.
