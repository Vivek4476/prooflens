# Backend Requirements & API Contract

How the frontend talks to the ProofLens backend, what was **added** for it
(additively, reusing the existing engine + DB — no business-logic changes), and
what is **still required** (documented here as requests, never mocked in the UI).

## Base

- Base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- All types are generated from the backend's `GET /openapi.json`.
- CORS is enabled for `CORS_ORIGINS` (default `http://localhost:3000`).

## Already implemented (consumed by the frontend)

| Method | Path | Used by | Notes |
|---|---|---|---|
| GET | `/healthz` | health dot, Settings | liveness |
| GET | `/readyz` | Settings | DB reachability (503 if down) |
| GET | `/metrics` | Settings (raw) | Prometheus text |
| GET | `/admin/tenants` · `/admin/tenants/{slug}` | Settings | tenant config (needs `X-Admin-Token`) |
| POST/PATCH/DELETE | `/admin/tenants…` | Settings (read-mostly) | CRUD |
| POST | `/v1/webhooks/lsq/{tenant_slug}` | — | production async path (signed) |

### Added for the frontend (additive, reuse the engine + results store)

**`POST /v1/score`** — synchronous scoring. `multipart/form-data`:
`image` (file, required), `tenant` (default `dev`), `backend` (optional override).
Runs the same pure engine the worker uses and persists a `Result`. Returns the
`Verdict` plus `result_id`, `processing_ms`, `backend`, `backend_is_real`:
```jsonc
{
  "band": "Suspect", "score": 20.0,
  "reason": "Designed graphic or screenshot, not a photo of a live scene.",
  "reason_code": "designed_graphic",
  "checks": [ { "name": "content", "available": true, "score": 12.0,
               "summary": "...", "metric": 12.0, "data": {…}, "latency_ms": 812.4 }, … ],
  "rubric_version": "v1",
  "result_id": "…", "processing_ms": 845.2, "backend": "openrouter", "backend_is_real": true
}
```
`reason` is verbatim from the backend vocabulary (see `docs/VERDICT_COPY.md`) —
the UI never rewrites it. `checks[]` is the single source of truth for the
Explainability view: render only the checks it contains.

**`GET /v1/results`** — `?limit=1..200&offset=0&band=Clear|Doubtful|Suspect`.
Newest-first page from the results store:
```jsonc
{ "items": [ { "id", "created_at", "band", "score", "reason", "reason_code",
               "rubric_version", "processing_ms", "source", "opportunity_id",
               "rep_id", "checks":[…] } ], "total": 123, "limit": 50, "offset": 0 }
```
`source` is `"webhook"` (came via LSQ) or `"direct"` (scored via `/v1/score`).
`opportunity_id` / `rep_id` are present only for `webhook` rows (LSQ supplies
them); they are `null` for direct/seeded uploads.

**`GET /v1/analytics/summary`** — aggregates computed from the results store:
`total`, `images_today`, `band_distribution`, `suspect_pct`, `avg_score`,
`avg_processing_ms`, `duplicates_caught`, `top_reasons[]` (verbatim reason text),
`series[]` (per-day count / band mix / avg score).

**`GET /admin/tenants` → `scoring`** — the admin tenant payload now includes the
resolved `scoring` config (weights, thresholds, caps, bands = defaults deep-merged
with the tenant's overrides), so the Settings page can display real per-tenant
thresholds without duplicating backend values.

### Analytics + Team Hierarchy (implemented additively)

All of the following are **additive** — no existing response key changed; the
golden set and verdict-copy invariants are preserved.

**`GET /v1/analytics/summary`** — now also accepts `from`/`to` (date aliases of
`start_date`/`end_date`, both kept), `bucket=daily|weekly|monthly` (default
`daily`), `group_by=none|zone|srsm|rsm|sm|branch|city` (default `none`). The
response keeps every existing key and adds:
- `buckets[]` — `{bucket_label, start, end, clear, doubtful, suspect, total, avg_score, incomplete}`. Weekly labels are `"Week 1..N"` anchored to the range start; monthly = calendar month (`YYYY-MM`).
- `incomplete` — true if the current (today's) bucket is unfinished.
- `previous` — `{clear, doubtful, suspect, total, avg_score}` for the immediately-preceding equal-length period (for deltas).
- `period` / `previous_period` — `{from, to}` explicit window bounds.
- `groups[]` — when `group_by != none`, one per node (incl. `"Unmapped"`): `{node, total, clear, doubtful, suspect, suspect_rate, avg_score, share}`.
- `top_reasons[]` entries now also carry `short_label`.
- The legacy per-day `series[]` is unchanged.
- `flag_precision` — `{reviewed, confirmed, overturned, precision_pct}` over the
  period's results. A "flag" is any result whose band is NOT `"Clear"`
  (Doubtful or Suspect). Among flagged results, only reviews with
  `review_status` in `{"reject", "approve", "false_positive"}` count:
  `confirmed` = count of `"reject"` (the flag was correct), `overturned` =
  count of `"approve"`/`"false_positive"` (the flag was wrong), `reviewed` =
  `confirmed + overturned`. `"escalate"` and pending (unreviewed) flags are
  excluded entirely — they don't count toward `reviewed`. `precision_pct` =
  `round(confirmed / reviewed * 100, 1)`, or `null` when `reviewed == 0`.
- `system_health` — `{scored_without_content_pct, median_processing_ms}` over
  the period's results (v4 Pain 9). `scored_without_content_pct` = percentage
  of results whose `reason_code` is `"no_content_analysis"` (short_label
  "Scored without content check" — the fail-open signal for "vision/content
  check did not run"), `round(no_content / total * 100, 1)`, or `null` when
  there are no results in the period. `median_processing_ms` = the median (not
  mean — `avg_processing_ms` remains the mean, unchanged) of `processing_ms`
  across the same results, `round(.., 1)`, or `null` when there are no results.

**`GET /v1/results`** — now also accepts `reason` (exact `reason_code`),
`rep_id` (normalized exact), and `from`/`to` (date range). Existing filters
(`band`, `review`, `limit`, `offset`) unchanged.

**`POST /v1/admin/hierarchy`** (multipart, `X-Admin-Token`) — CSV columns
`agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from` (`valid_from`
`YYYY-MM-DD`). Validates unknown columns / blank agent_id / duplicate agent_id
within a `valid_from` / bad dates → 400. Returns
`{upload_id, row_count, match_rate_preview, matched, unmapped}`. Versions via
`upload_id`; the hierarchy is effective-dated (a result maps to the row with the
latest `valid_from <= scored_date`).

**`GET /v1/admin/hierarchy/status`** — `{upload_id, valid_from, row_count,
match_rate, matched, unmapped}` (match rate vs distinct `rep_id`s in the last
90 days of results).

**`GET /v1/admin/hierarchy/template`** — the canonical column set + an example row.

**Known gaps (logged, not fixed here):** the analytics/results read paths are
NOT tenant-scoped (single-demo-tenant assumption; real fix is the SSO/RBAC
milestone). CSV-only upload; XLSX deferred.

### Bulk photo scoring (Phase 1 — additive; see
`docs/superpowers/specs/2026-07-10-bulk-upload-design.md`)

Lets an operator score a batch of field-visit photos (e.g. from an LSQ export
CSV) in one go, attributed to the agent/opportunity. Runs the exact same
engine + persistence as `/v1/score` — no scoring/engine/webhook logic changed.
Images are fetched **server-side** (LSQ photo URLs are private) and are
**never stored**: only the perceptual hash + verdict persist, same as today.

**`POST /v1/bulk-score`** — body:
```jsonc
{
  "rows": [
    { "image_url": "https://...", "rep_id": "A123", "opportunity_id": "OPP1" },
    { "image_url": "https://...", "rep_id": null, "opportunity_id": null }
  ],
  "label": "July 10 export"   // optional, cosmetic only
}
```
Starts a background job (throttled concurrency, fixed cap of 4 — never the
whole folder held in memory at once) and returns immediately:
```jsonc
{ "job_id": "…", "total": 2 }
```

**`GET /v1/bulk-score/{job_id}`** — poll for progress/results:
```jsonc
{
  "status": "queued" | "running" | "done",
  "processed": 1,
  "total": 2,
  "results": [
    { "image_url": "https://...", "rep_id": "A123", "opportunity_id": "OPP1",
      "band": "Suspect", "score": 15, "reason_code": "recycled",
      "result_id": "…", "error": null },
    { "image_url": "https://...", "rep_id": null, "opportunity_id": null,
      "band": null, "score": null, "reason_code": null, "result_id": null,
      "error": "fetch failed: …" }
  ]
}
```
404 for an unknown `job_id`. `results[]` is index-aligned with the request's
`rows[]` and populated progressively as rows complete — poll until
`status == "done"` (or `processed == total`).

**Fail-open per row.** A fetch or scoring error for one row is caught,
recorded as that row's `error` (band/score/reason_code/result_id stay
`null`), and the batch continues — one bad photo/URL never aborts the job.

**Persistence.** Every successfully-scored row is written as a normal
`Result` row with `source="bulk"` plus that row's `rep_id`/`opportunity_id`
(normalized the same way as webhook ingestion) — so bulk-scored photos show
up in `/v1/results`, `/v1/analytics/summary`, and the Review Queue exactly
like any other result, immediately and permanently (independent of the
in-memory job registry below).

**Job store is in-memory (Phase 1 scope).** `job_id` state (status/progress)
lives in the API process's memory, not the database — a process restart
loses in-flight job progress (the already-scored rows are NOT lost; they're
already `Result` rows). A durable queue/worker is the Phase 3 seam if folders
reach thousands of rows; not built.

**Column mapping is a frontend concern.** LSQ field names are
tenant-configurable, so this endpoint takes already-mapped rows
(`image_url`/`rep_id`/`opportunity_id`); the CSV → column-mapping UI lives
client-side (parses the LSQ export, lets the operator map columns, then
POSTs the normalized rows here).

**Not yet built (Phase 2 seam, documented only):** pulling photos directly
from the LSQ activities API (pick agent/team + date range) instead of a
manual CSV export — would reuse this exact job engine, just with a different
row source.

## Known trade-offs (by design)

- **No thumbnails.** The backend **never stores images** — only an 8-byte
  perceptual hash + trail. History/Review are metadata-only; the tables are
  designed to be excellent without thumbnails.
- **rep/opportunity** exist only for `webhook`-sourced results (LSQ provides
  them). Direct `/v1/score` uploads show `—`.
- **Demo scoring model** is chosen by `VISION_BACKEND` (default `stub`, offline
  and free). Set `VISION_BACKEND=openrouter` (+ `OPENROUTER_API_KEY`) for a real
  model. Scoring is fail-open: if the model errors/rate-limits, the verdict
  degrades to "scored without content analysis" — never a broken response.

## Analytics v4 — Gate 4 fenced seams (documented, not built)

The following are P2 doctrine/platform seams from the Analytics v4 spec
(Pains 11, 13, 14, 15). Each is designed here so the shape is agreed, but
**none of it is built** — no schema migration, no route, no UI. They stay
fenced until a follow-up gate explicitly picks them up.

**Pain 8 seam — per-card Quarterly aggregation.** The per-card override on
Capture-Risk Trend and Band Mix (Pain 8) offers Daily/Weekly/Monthly only,
because `GET /v1/analytics/summary`'s `bucket` param only accepts
`daily|weekly|monthly` (see `Bucket` in `src/prooflens/api/analytics.py`);
offering Quarterly needs that endpoint to grow `bucket=quarterly` (calendar-
quarter edges, same `AnalyticsBucket[]` shape) before the frontend control can
add the option. Not built.

### Pain 11 — On-page faceting

Clicking a Band Mix segment or a Top Flag Reasons row would re-filter the
*other* widgets on the page in place, surfaced as a removable chip
("Faceted: Suspect ×"); drilling out to `/history` becomes an explicit "view
submissions" action rather than the implicit result of a click.

**Fenced because:** `/v1/analytics/summary` returns one pre-aggregated
response per bucket/group — it has no per-bucket × per-facet breakdown (e.g.
"Band Mix counts, filtered to reason=designed_graphic"). Client-side faceting
needs one of:
- **(a) A `facet` param on the summary endpoint** — e.g.
  `GET /v1/analytics/summary?...&facet=band:Suspect` or
  `facet=reason:designed_graphic`, returning the same `buckets[]` /
  `groups[]` / `top_reasons[]` shape recomputed over the faceted subset, so
  the frontend can re-render the non-clicked widgets from a second response.
- **(b) Shipping raw rows** to the client and aggregating in the browser —
  rejected: `/v1/results` pages are metadata-only but still per-submission,
  and pulling enough rows to recompute every widget's aggregates client-side
  scales badly past a few thousand records.

Recommended: (a), a `facet` query param, additive to the existing summary
endpoint. Not built.

### Pain 13 — Viewer → hierarchy_node mapping seam

Document an optional `user_hierarchy_node` mapping (`user_id` → `node`, same
node vocabulary as `group_by`/hierarchy CSV: zone, srsm, rsm, sm, branch,
city). When present, `GET /v1/analytics/summary` would default `group_by`'s
scope to the viewer's own node — so a Zonal Head hitting `/analytics` with no
filters lands already scoped to their zone, instead of the whole tenant.

This plugs into the existing `group_by` + node-resolution machinery
described above (`groups[]`, effective-dated hierarchy from
`POST /v1/admin/hierarchy`) — no new aggregation logic, just a default-scope
lookup keyed by the authenticated user before `group_by` is applied.

**Fenced because:** there is no user/auth model yet (single-demo-tenant,
no login). This seam awaits that milestone. Do not build the mapping UI now.

### Pain 14 — Usage counters

Privacy-safe, tenant-scoped counters for `page_view`, `filter_change`,
`drill_down`, `export` events. Explicitly **no per-user tracking, no PII** —
counts only, not identities.

Design: an append-only `usage_events(tenant_id, event, day)` table (one row
per tenant/event/day, incremented in place — a daily aggregate, not an event
log) plus:
- **`POST /v1/usage/events`** — `{ "event": "page_view" | "filter_change" |
  "drill_down" | "export" }`, tenant resolved from the request context;
  increments today's counter for that event.
- **A read** — e.g. `GET /v1/usage/summary?days=7` — returning per-event
  daily counts for "last 7 days page views" in Settings → System health.

The frontend would fire the `POST` from the `/analytics` page on the
corresponding interactions (mount, filter change, chip drill-down, export
click). Fenced/documented — not built.

### Pain 15 — Chart annotations

Tenant-scoped dated markers (e.g. "Camera lock enforced · Jul 1") rendered as
a subtle vertical rule + label on time-based charts (Capture Risk Trend, Band
Mix over time), with simple admin CRUD in Settings.

Design: a `chart_annotations(tenant_id, date, label)` table plus CRUD
endpoints (`POST` / `GET` / `PATCH` / `DELETE` under
`/v1/admin/annotations`, `X-Admin-Token`-gated like the other admin routes),
and a read that `/analytics` consumes to overlay markers on the trend/Band
Mix charts by date — most simply as an `annotations[]` array
(`{date, label}`) added to the existing `GET /v1/analytics/summary` response
for the requested period, so the frontend doesn't need a second round-trip.
Fenced/documented — not built.

## STILL REQUIRED — Review Queue decision endpoints (NOT yet implemented)

The Review Queue UI is built against these; until they exist the UI shows an
honest **"backend endpoint pending"** state (no mocked responses).

**`POST /v1/results/{id}/review`** — record a moderator decision.
Request:
```jsonc
{ "decision": "approve" | "reject" | "false_positive", "note": "optional string" }
```
Response: the updated result including a new `review` block:
```jsonc
{ "id": "…", "review": { "status": "approve", "note": "…",
   "reviewed_at": "ISO-8601", "reviewer": "…" } }
```
Backend work needed: a `review_status` / `reviews` table (or nullable columns on
`results`) + this route. This is a schema change and so is **not** done here —
it is listed as a request per the build's hard rule.

**`GET /v1/results?review=pending|approve|reject|false_positive`** — optional
filter so the Review Queue can hide already-actioned items. Until added, the
frontend filters client-side on the `review` block when present.

## DSE (agent) scorecard — implemented additively

**`GET /v1/dse?q=<name-or-id>`** → `{ results: [{ agent_id, name, branch, sm }] }`.
Search the hierarchy by agent name (case-insensitive substring) or agent_id;
capped, tenant-scoped; empty `q` returns the first N. `agent_name` is a new
optional hierarchy column (migration `0006_agent_name`); missing → falls back
to the agent_id.

**`GET /v1/dse/{agent_id}?from=&to=&bucket=daily`** → the scorecard:
`{ agent_id, name, chain: {sm,rsm,srsm,zone,branch,city}, total,
band_distribution, suspect_rate, avg_score, top_reasons[], trend[], recent[] }`
— computed over that rep_id's results in the range (trend reuses the analytics
bucketing filtered to the rep; recent = latest flagged captures). Honest
small-sample values (never fabricated). Analytics `group_by=agent` added
(labels with the agent name).

## Auth (per-tenant API key) — implemented (#18)

All `/v1/*` **tenant data** routes require `Authorization: Bearer <key>`;
missing/invalid/revoked → `401`. The key resolves the tenant and every query is
filtered to it — a valid key for the wrong tenant gets an honest `404` on a
single-result lookup (e.g. `GET /v1/results/{id}`), never a leak of another
tenant's data. The `/v1/admin/*` admin routes (e.g. `POST /v1/admin/hierarchy`)
use `X-Admin-Token` instead, exactly like the legacy `/admin/*` routes. Webhook
(HMAC) and `/healthz`/`/readyz`/`/metrics` are unaffected.

**Keys:** minted via `python scripts/mint_api_key.py --tenant <slug> --label <note>` (prints the raw
key once; only its sha256 is stored; revocable). **Never** shipped to the browser.

**Frontend:** the dashboard calls same-origin `/api/*`; the Next.js BFF proxy
(`src/app/api/[...path]/route.ts`) injects the key from server-only env
(`PROOFLENS_API_URL`, `PROOFLENS_TENANT_KEY`, `PROOFLENS_ADMIN_TOKEN`).

## Rate limiting (#22)
`/v1/*` is rate-limited per 60s window, bucketed by API key (hashed) or client IP: general
`RATELIMIT_GENERAL_PER_MIN` (default 120), compute (`/v1/score`, `/v1/bulk-score`)
`RATELIMIT_COMPUTE_PER_MIN` (default 20); `0` disables a tier. Over limit → `429` + `Retry-After`.
`/healthz`/`/readyz`/`/metrics` and the LSQ webhook (`/v1/webhooks/*`) are exempt. **Single-instance
only** — counters are per-process; a multi-instance deploy needs a shared store (Redis).

**Shared-key caveat (multi-operator):** the dashboard's BFF proxy injects ONE tenant key for every
browser user, so all operators share a single bucket (per-IP fallback never engages for dashboard
traffic). Fine for a small operator pool; with many concurrent operators, raise
`RATELIMIT_COMPUTE_PER_MIN` (the 20/min compute tier is the tight one, e.g. several people scoring at
once) or move to per-user keys when SSO/RBAC lands. This is a conscious go-live sizing decision.
