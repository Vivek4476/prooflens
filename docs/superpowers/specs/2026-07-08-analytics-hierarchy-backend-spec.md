# Analytics + Team Hierarchy — Backend Spec (additive)

- **Date:** 2026-07-08
- **Branch:** `backend/analytics-hierarchy` (off main `c29091a`)
- **Scope:** Backend only (§0 + §13 backend tests of the consolidated redesign spec). Frontend (§1–12) is a separate coordinated effort. Pipeline/engine/webhook scoring logic changes ZERO.

## Goal

Additively extend the analytics + results API and add an effective-dated org-hierarchy dimension, so the redesigned `/analytics` page can answer: (1) is capture risk rising? (2) what drives flags? (3) which teams need attention? Every change is additive — existing endpoints/response keys and the golden set are preserved.

## Key decisions (rationale)

1. **`rep_id`/`opportunity_id` become real `Result` columns.** Today they live only on `Job.payload` and are backfilled via a Job join (and are `None` for direct `/v1/score` results). Promoting them to indexed `Result` columns (populated in `record_result`, backfilled from `Job.payload` in the migration) makes the hierarchy join a plain equi-join and `rep_id` filtering efficient. Direct-scored rows keep `rep_id = NULL` (they legitimately have no rep).
2. **One shared `normalize_id(s) -> str`** (`.strip().upper()`, `None`/blank → `None`). Applied via a Pydantic `field_validator` on `WebhookPayload.rep_id` (ingestion) and on every `agent_id` at hierarchy upload. Single source of truth (spec §0c).
3. **Hierarchy flows through the `Repo` abstraction** (new methods on both `InMemoryRepo` + `PostgresRepo`), NOT `admin.py`'s raw-session pattern — so analytics/hierarchy stay offline-testable with `InMemoryRepo`. New admin endpoints use `get_repo`.
4. **Effective-dated join is a pure Python resolver.** `resolve_node(rows, agent_id, scored_date) -> HierarchyNode | None`: pick the row with `agent_id == normalized rep_id` and the **latest** `valid_from <= scored_date`. Unmatched → `None` (the "Unmapped" node). Both repos expose `get_hierarchy_rows(tenant)`; aggregation resolves in Python. Parity + demo-scale safe (≤5000-row cap already in place).
5. **Read endpoints (`/v1/results`, `/v1/analytics/summary`) stay NON-tenant-scoped** — pre-existing single-demo-tenant assumption; there is no auth-derived tenant context. Real fix belongs to the separate SSO/RBAC milestone. The hierarchy TABLE is tenant-keyed and its queries are tenant-scoped. **Logged as a known gap.**
6. **CSV upload only** (stdlib `csv`) — zero new dependency in a memory-sensitive service. XLSX template/parse deferred and logged. The downloadable template is CSV.
7. **New admin routes are `/v1/admin/hierarchy` + `/v1/admin/hierarchy/status`** per the spec's explicit paths (diverges from the existing un-versioned `/admin/tenants` — logged), reusing `require_admin`.
8. **Analytics aggregation stays Python-over-`list_results`-items** (buckets, group_by, deltas), preserving InMemory/Postgres parity; no raw-SQL aggregation.

## §0 requirements (verbatim intent)

### a) Extend `GET /v1/analytics/summary` (additive)
- New params: `from`, `to` (dates; aliases of the existing `start_date`/`end_date` — keep both working), `bucket=daily|weekly|monthly` (default daily), `group_by=none|zone|srsm|rsm|sm|branch|city` (default none).
- Returns (additive — keep all existing keys): per-bucket `{clear, doubtful, suspect, total, avg_score}` in `series`, each bucket flagged `incomplete: true` for the current unfinished bucket; the SAME aggregates for the **immediately preceding period of equal length** (a `previous` block, for deltas); per-reason counts for the range (existing `top_reasons`, now also carrying `short_label`); and, when `group_by != none`, a `groups` array of per-node aggregates `{node, total, suspect, suspect_rate, avg_score, share, ...}` ALWAYS including an `"Unmapped"` node when applicable. Include the exact comparison-window bounds (`period`, `previous_period`) so the frontend caption is unambiguous. Tenant-scoped join.
- **Bucketing:** weekly buckets are "Week 1..N" anchored to the SELECTED RANGE'S START (not ISO weeks); monthly = calendar months. Incomplete current bucket identified honestly.

### b) Extend `GET /v1/results` (additive)
- Add filters: `band`, `reason`, `rep_id`, `from`, `to`. `band` already exists; add `reason` (exact `reason_code`), `rep_id` (exact, normalized), `from`/`to` (surface the existing `start`/`end` range semantics as query params). No logic changes to existing filters.

### c) NEW hierarchy reference table (tenant-scoped, effective-dated)
Columns: `tenant_id, agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from (date), uploaded_at, upload_id`. Join rule: a result maps to the row where `agent_id == result.rep_id` AND `valid_from <= result.scored_date`, picking the **latest** `valid_from` (effective-dated — org changes never rewrite historical reports). ID normalization identical at webhook ingestion and file upload via the ONE shared util.

### d) NEW admin endpoints
- `POST /v1/admin/hierarchy` (multipart CSV upload → validate → new version).
- `GET /v1/admin/hierarchy/status` → current version (`upload_id`/`valid_from`), row count, and **match rate** vs `rep_id`s seen in the last 90 days of results.

### e) Reason `short_label` in the verdict vocabulary
Add `REASON_SHORT_LABEL` to `engine/verdicts.py` (single source of truth) + document in `VERDICT_COPY.md`. Short labels (aggregate-surface only; full sentences remain the verdict surface):
- Recycled image · Photo of a screen · Designed graphic · No people in scene · Too blurred · Scored without content check
- (Map: `recycled`→"Recycled image"; `screen_recapture`→"Photo of a screen"; `designed_graphic`→"Designed graphic"; `no_people_or_irrelevant`→"No people in scene"; `too_blurred`→"Too blurred"; `no_content_analysis`→"Scored without content check"; plus the three visit gates → concise labels; `clear`→"Clear".) Expose `short_label` in `top_reasons` entries.

### f) Document in `BACKEND_REQUIREMENTS.md` as "implemented additively."

## Testing (§13 backend)
- Hierarchy join correctness across two versions (a rep who moved branches mid-range splits correctly by `scored_date`).
- Unmapped handling + ID normalization (mixed-case/whitespace IDs still match).
- Summary: delta math, `group_by` aggregation, previous-period window, incomplete-bucket identification, weekly-anchored labels.
- Results filters (reason/rep_id/from/to) narrow correctly.
- Admin upload: validation (dup agent_ids, blank IDs, unknown columns), match-rate computation, versioning.

## Non-goals
Frontend (§1–12). Tenant-scoping the existing read paths (SSO/RBAC milestone). XLSX parsing. Changing any scoring/engine/webhook logic.
