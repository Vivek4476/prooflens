# Auth + tenant scoping (#18) — Design

- **Date:** 2026-07-10
- **Issue:** #18 (Auth + tenant scoping across `/v1/*`)
- **Owner decisions:**
  1. **Scope:** per-tenant **API key** + real tenant scoping. **No** user accounts, login UI, or
     roles — deferred to a later SSO/RBAC milestone.
  2. **Browser credential:** a **BFF proxy** in Next.js holds the key server-side; the browser
     never sees it.

## Goal
No `/v1/*` data route is reachable without a valid per-tenant credential; every read/write is
filtered to the caller's tenant; the browser dashboard holds no secret. The webhook (per-tenant
HMAC) and health/metrics probes are unchanged.

## Problem today
- The **read/data** routes (`/v1/score`, `/v1/results`, `/v1/analytics/*`, `/v1/dse*`,
  `/v1/bulk-score`) are unauthenticated and resolve the tenant from a hardcoded
  `DEFAULT_TENANT = "dev"` (`api/scoring.py` `_analytics_tenant_id`, `api/dse.py` `_tenant_id`).
- `service/repo.py` / `db/repo.py` `list_results(...)` has **no `tenant_id` parameter** — it returns
  results across all tenants. This is the actual data-isolation leak the new endpoints widened
  (`/v1/dse?q=` is a browsable directory of every agent).
- The **admin** routes already use a shared `X-Admin-Token` header; the **webhook** already verifies
  a per-tenant HMAC (`api/security.py`). Those two stay as-is.
- The frontend ships `NEXT_PUBLIC_ADMIN_TOKEN` to the browser and calls the backend directly at
  `http://localhost:8000` (`lib/api/client.ts`).

## Non-goals (YAGNI)
User accounts, email/password or SSO/OIDC login, sessions, roles/RBAC, per-user audit. Revisit when
more than one human operator or tenant needs distinct access. This spec closes the exposure without
building an identity system nobody needs yet.

## Design

### ① Credential store — `api_keys` table (additive migration)
New table:

```
api_keys(
  id           uuid  pk,
  tenant_id    uuid  fk -> tenants.id, indexed,
  key_hash     text  unique, indexed,   -- sha256(raw key), hex
  prefix       text,                     -- first 12 chars of the raw key, for display only
  label        text,                     -- human note ("dev dashboard", "bulk integration")
  created_at   timestamptz default now(),
  revoked_at   timestamptz null          -- non-null => inactive
)
```

- **Raw key format:** `pl_` + 40 url-safe random chars (`secrets.token_urlsafe(30)`). Shown **once**
  at mint; only `key_hash = sha256(raw)` is stored. `prefix` is the first 12 chars (e.g.
  `pl_A1b2C3d4`) for display/debugging, never enough to reconstruct the key.
- **Lookup:** on a request, `sha256(presented_key)` and match a row with that `key_hash` and
  `revoked_at IS NULL` whose tenant is `active`. Hash-equality is inherently constant-time on the
  digest; no plaintext compare.
- **Rotation/revocation:** a tenant may hold ≥1 active keys; revoke = set `revoked_at`. Minting a new
  key does not invalidate old ones (rotate: mint new, deploy, revoke old).
- **Minting:**
  - **v1 minting is the CLI only:** `scripts/mint_api_key.py --tenant <slug> [--label ...]` prints a
    fresh raw key (used to seed the `dev` key). Always creates a new key row.
  - **Deferred (not in this spec):** admin mint/revoke endpoints
    (`POST /admin/tenants/{slug}/api-keys`, `POST /admin/api-keys/{id}/revoke`). The CLI is
    sufficient to ship a single-tenant preview; add the endpoints when self-serve key management is
    actually needed.

### ② Backend enforcement + tenant scoping
- **`require_tenant` dependency** (`api/auth.py`, new): reads `Authorization: Bearer <key>`; if
  absent/blank → `401`. Hashes, looks up an active, non-revoked key → returns the owning
  `TenantView`. Unknown/revoked/inactive → `401` (never `403`; we don't reveal existence). The
  `TenantView` already carries `id`, `slug`, `scoring`, etc.
- **Apply to every data route** via `dependencies=[Depends(require_tenant)]` on the router or the
  route, and inject the resolved `TenantView` where the tenant is needed. Routes:
  `/v1/score`, `/v1/results`, `/v1/analytics/summary`, `/v1/dse`, `/v1/dse/{agent_id}`,
  `/v1/bulk-score`, `/v1/bulk-score/{job_id}`.
- **Remove the hardcoded tenant:** `_analytics_tenant_id` / `_tenant_id` are replaced by the tenant
  from `require_tenant`. `scoring.py`'s `DEFAULT_TENANT` stays only as the seed-script default.
- **Data-isolation fix (the core):** add `tenant_id: str` to
  `Repo.list_results(...)` and filter by it in both `InMemoryRepo` and `PostgresRepo`
  (`Result.tenant_id == tid`). Thread the resolved tenant id into every caller
  (`api/scoring.py` results, `api/analytics.py` aggregate, `api/dse.py` search + scorecard,
  `service/bulk.py` reads). Hierarchy reads (`get_hierarchy_rows(tenant_id)`) are already
  tenant-scoped.
- **Untouched:** webhook (`/v1/webhooks/lsq/{slug}`, HMAC), admin routes (`X-Admin-Token`),
  `/healthz`, `/readyz`, `/metrics`, `/openapi.json`, `/docs`.
- **Config:** `AUTH_ENABLED: bool = True` (`config.py`). When `False` (local dev convenience only),
  `require_tenant` falls back to the `dev` tenant so a bare `curl` still works locally. Production
  sets it `True`. The setting is the single switch; enforcement code lives in one dependency.

### ③ Next.js BFF proxy
- **Catch-all route handler** `frontend/src/app/api/[...path]/route.ts` exporting `GET/POST/PUT/PATCH/DELETE`.
  It forwards `"/api/<path>?<query>"` → `"${PROOFLENS_API_URL}/<path>?<query>"`, injecting headers by
  path prefix:
  - paths starting `v1/` → `Authorization: Bearer ${PROOFLENS_TENANT_KEY}`,
  - paths starting `admin/` → `X-Admin-Token: ${PROOFLENS_ADMIN_TOKEN}` (moved server-side).
  It passes through method, body (raw), and content-type; returns the upstream status + body. Runs on
  the Node runtime (`export const runtime = "nodejs"`), never statically cached
  (`export const dynamic = "force-dynamic"`).
- **Client repoint:** `lib/api/client.ts` baseURL becomes same-origin `/api` (drop the
  `http://localhost:8000` default and the `X-Admin-Token`/`NEXT_PUBLIC_ADMIN_TOKEN` browser header —
  the proxy adds them). All existing `api.*` methods keep their paths (`/v1/...`, `/admin/...`) since
  the proxy strips the `/api` prefix.
- **Env (server-only — NOT `NEXT_PUBLIC_*`):** `PROOFLENS_API_URL` (backend origin),
  `PROOFLENS_TENANT_KEY`, `PROOFLENS_ADMIN_TOKEN`. Set in Vercel as encrypted server env.
- **Result:** the browser only ever calls same-origin `/api/*`; the raw backend rejects anonymous
  callers with `401`.

### ④ Rollout (production held)
1. Migration `0007_api_keys` (additive; nullable/independent — no backfill).
2. `scripts/mint_api_key.py --tenant dev` → set `PROOFLENS_TENANT_KEY` in Vercel (server) + wherever
   server-to-server callers need it. `AUTH_ENABLED=True` on Render.
3. Move `PROOFLENS_ADMIN_TOKEN` / `PROOFLENS_API_URL` to Vercel server env; remove
   `NEXT_PUBLIC_ADMIN_TOKEN`.
4. Land backend + proxy together on this branch so preview always has a consistent pair. No data
   migration — `Result.tenant_id` is already populated by the webhook/bulk/score paths; scoping only
   starts *enforcing* it.
5. Production stays held; this merges into `analytics-v4` (preview) first, like DSE/bulk.

### ⑤ Testing
- **Backend unit** (`tests/unit/test_auth.py`): `require_tenant` — valid key → correct `TenantView`;
  missing/blank header → 401; unknown key → 401; revoked key → 401; inactive tenant → 401;
  `AUTH_ENABLED=False` → dev fallback.
- **Cross-tenant isolation** (`tests/integration/test_tenant_scoping.py`): seed tenant A + B each with
  results; A's key on `/v1/results` and `/v1/analytics/summary` and `/v1/dse` returns only A's data,
  never B's. `list_results` unit test: `tenant_id` filter excludes other tenants.
- **Existing suite:** the app test factory (`create_app` in tests) overrides `require_tenant` via
  `app.dependency_overrides[require_tenant] = lambda: <fixture TenantView>` (mirrors the existing
  `get_repo` override), so the ~245 current tests don't each need a header. A handful assert real
  enforcement without the override.
- **Frontend** (`app/api/[...path]/route.test.ts` or a vitest): the proxy injects the bearer key +
  admin token and forwards method/body/query, returns upstream status. Mock `fetch`.
- **e2e:** the data-independent mobile smoke tests still pass through the proxy (they assert layout/nav,
  not data). The proxy must not 500 when the backend/env is absent — it returns the upstream error.
  Data-dependent e2e (none today) would need the proxy env + a backend key; note in the plan.

## Files (create / modify)
- **Create:** `migrations/versions/0007_api_keys.py`, `src/prooflens/api/auth.py`,
  `src/prooflens/service/api_keys.py` (hash + lookup helpers), `scripts/mint_api_key.py`,
  `frontend/src/app/api/[...path]/route.ts`, tests noted above.
- **Modify:** `src/prooflens/db/models.py` (+`ApiKey`), `db/repo.py` + `service/repo.py`
  (`list_results(tenant_id=...)`, `get_api_key_by_hash`), `api/scoring.py`, `api/analytics.py`
  (caller signatures), `api/dse.py`, `service/bulk.py`, `api/app.py` (router deps), `config.py`
  (`AUTH_ENABLED`), admin router (mint/revoke, optional), `frontend/src/lib/api/client.ts`,
  `frontend/.env.local.example` + `.env.production` (server env), `frontend/BACKEND_REQUIREMENTS.md`.

## Non-negotiables
Additive to the scoring engine/verdict/webhook (zero change). Honest 401s (no info leak). No stored
plaintext keys. Existing tests stay green (via dependency override). Endpoints + env documented in
`BACKEND_REQUIREMENTS.md`.
