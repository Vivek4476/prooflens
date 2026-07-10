# Pre-go-live hardening + DSE UX (#20, #21, #22) — Design

- **Date:** 2026-07-10
- **Issues:** #22 (API-wide rate limiting), #20 (DSE search SQL pushdown + truncation signal), #21 (DSE date-range control)
- **Owner decision:** rate limiting = in-memory, per-key + per-IP fallback. Remaining open calls delegated
  ("be the judge") — resolved below.
- **Additive:** scoring engine, verdict vocabulary, webhook, auth (require_tenant), and golden set unchanged.
- **Branch:** `feature/hardening-dse-ux` off `frontend/analytics-v4` (which now includes auth #18).

Three independent changes, one spec, one plan; each is a self-contained task.

## #22 — API-wide rate limiting (in-memory, per-key + per-IP)

**Goal:** basic abuse protection on `/v1/*` before real traffic, without new infra.

- **Middleware** `src/prooflens/api/ratelimit.py`, wired in `create_app` (`api/app.py`) as an `@app.middleware("http")`
  **before** the auth dependency runs — so the unauthenticated 401-flood path is also throttled. Ordered after the
  existing body-size middleware.
- **Bucket key:** the API key from `Authorization: Bearer <key>` when present (hashed, so the raw key isn't held in
  the limiter), else the client IP. IP is taken from the **first hop of `X-Forwarded-For`** (Render/Vercel proxy in
  front) falling back to `request.client.host`.
- **Algorithm:** fixed-window counter per (bucket-key, tier) with a 60s window — an in-memory
  `dict[str, tuple[window_start, count]]`. Simple, allocation-light, and single-instance-correct. Stale entries are
  pruned opportunistically on access (no background task).
- **Tiers (configurable via `Settings`, env-overridable; defaults):**
  - **general** — 120 req / 60s on all `/v1/*`.
  - **compute** — 20 req / 60s on `/v1/score` and `/v1/bulk-score` (the memory/CPU-heavy paths). A compute request
    counts against BOTH its compute bucket and the general bucket; the stricter one wins.
- **Exempt:** `/healthz`, `/readyz`, `/metrics`, `/openapi.json`, `/docs` (probes/observability must never be
  throttled). Non-`/v1/*` paths (webhook, admin) are out of scope for this middleware.
- **Over limit →** `429` with a `Retry-After: <seconds-to-window-reset>` header and a JSON `{"detail": "..."}`.
- **Config:** `Settings` gains `ratelimit_general_per_min: int = 120`, `ratelimit_compute_per_min: int = 20`
  (aliases `RATELIMIT_GENERAL_PER_MIN` / `RATELIMIT_COMPUTE_PER_MIN`). A value of `0` disables that tier (escape hatch
  for tests/debug).
- **Single-instance caveat:** documented in `BACKEND_REQUIREMENTS.md` — counters are per-process; a multi-instance
  deploy needs a shared store (Redis) — deferred, noted as the upgrade path.
- **Tests** (`tests/unit/test_ratelimit.py` for the pure limiter + `tests/integration/test_ratelimit_api.py`):
  N+1th request in a window → 429 with `Retry-After`; distinct keys/IPs get independent buckets; a compute route hits
  the compute cap before the general cap; probes are never limited; `0` disables a tier.

## #20 — DSE search perf (SQL pushdown) + honest truncation

**Goal:** stop loading whole tables / 5000-row result windows into Python for DSE search, and stop silently
under-reporting a high-volume DSE's totals.

### A. SQL pushdown (PostgresRepo; InMemoryRepo keeps the Python impl for parity)
- New repo method **`search_hierarchy(tenant_id: str, q: str, limit: int) -> list[dict]`**: name/id substring match
  pushed into SQL — `WHERE tenant_id = :tid AND (agent_id ILIKE :pat OR agent_name ILIKE :pat) … LIMIT :limit`,
  latest-row-per-agent respected. LIKE metacharacters in `q` (`%`, `_`, `\`) are **escaped** so they match literally
  (`ESCAPE '\'`). Returns the same row shape `search_dse` already consumes.
- New repo method **`result_counts_by_rep(tenant_id: str, start, end) -> dict[str, int]`**: the empty-`q`
  "most-active" ranking via SQL `SELECT rep_id, COUNT(*) … WHERE tenant_id AND created_at ∈ [start,end) AND rep_id IS
  NOT NULL GROUP BY rep_id` — no more `list_results(limit=5000)` load just to count.
- `api/dse.py` `search_dse` uses these: `q` present → `search_hierarchy`; empty `q` → rank the latest hierarchy rows by
  `result_counts_by_rep` (last 90 days, matching today's behavior). InMemoryRepo implements both methods over its
  in-memory structures (identical semantics), so the endpoint is repo-agnostic and offline-testable.

### B. Truncation signal (honesty)
- The scorecard (`dse_scorecard`) still calls `list_results(limit=_SCORECARD_LIMIT=5000, …)`. When the returned
  `total > _SCORECARD_LIMIT`, add **`truncated: true`** (else `false`) to the response, plus `total` (already present).
  The KPIs/trend are computed over the first 5000; `truncated` tells the UI they're a capped sample.
- **Frontend:** `DseScorecard` type gains `truncated: boolean`; the `/dse` page shows an honest note when true —
  e.g. "Showing the most recent 5,000 captures in range — totals are capped." Placed near the KPI row with the
  existing small-sample caveat.
- **Tests:** `q` with `%`/`_`/`\` matches literally (escaped, not wildcard); `search_hierarchy` `LIMIT` caps at the DB;
  `result_counts_by_rep` counts per rep tenant-scoped; scorecard sets `truncated` only past 5000. InMemory/Postgres
  parity asserted for the two new methods where feasible offline (InMemory unit-tested; Postgres logic reviewed).

## #21 — DSE date-range control (frontend only)

**Goal:** let the operator change the scorecard's window (backend/hook/client already accept `from`/`to`/`bucket`;
today `/dse` never passes them, so it's stuck at last-30-days).

- Add a compact range + cadence control to `/dse`, **reusing the analytics `FilterBar`** (or a trimmed
  `DseFilterBar` sharing the same range presets: Last 7 / 30 / 90 days / This month / Custom, and Daily/Weekly/Monthly).
  Managed with the existing `useUrlState` pattern so the range is shareable/bookmarkable via the URL, consistent with
  analytics.
- Thread the selection into `useDseScorecard(agentId, { from, to, bucket })` (already supported end-to-end). **Default
  = last 30 days** (unchanged behavior when no range chosen).
- The suspect-rate trend and KPIs recompute for the chosen range (already wired server-side).
- **Tests** (`vitest` + RTL where the pattern exists): the control renders; selecting a preset updates the query
  params passed to `useDseScorecard`; default (no selection) requests last-30-days.

## Files (create / modify)
- **Create:** `src/prooflens/api/ratelimit.py`; tests `tests/unit/test_ratelimit.py`,
  `tests/integration/test_ratelimit_api.py`, `tests/unit/test_dse_search_repo.py`; a `/dse` range-control component if
  not reusing `FilterBar` directly.
- **Modify:** `api/app.py` (wire middleware), `config.py` (rate-limit settings), `service/repo.py` + `db/repo.py`
  (`search_hierarchy`, `result_counts_by_rep` on the protocol + both impls), `api/dse.py` (use the new methods +
  `truncated`), `frontend/src/lib/api/types.ts` (`DseScorecard.truncated`), `frontend/src/app/(app)/dse/page.tsx`
  (range control + truncation note), `frontend/BACKEND_REQUIREMENTS.md` (rate-limit + single-instance note).

## Non-negotiables
Additive; honest states (real 429/Retry-After, real truncation note — never fabricated); scoring/verdict/webhook/auth
unchanged; existing suites stay green; new endpoints/behaviors documented in `BACKEND_REQUIREMENTS.md`.
