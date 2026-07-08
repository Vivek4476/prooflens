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
