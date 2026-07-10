# Bulk Photo Scoring (LSQ folder/export) — Design

- **Date:** 2026-07-10
- **Branch:** `feature/bulk-upload` (off `frontend/analytics-v4`, so it inherits the `source` column
  + rep/opportunity attribution + analytics).
- **Additive:** scoring/engine/webhook flow change ZERO. Reuses the real scoring path.

## Goal

Let an operator score a batch of field-visit photos in one go, attributed to the agent/opportunity,
so the results flow into Analytics, History and the Review Queue. In effect: real data instead of
the seed.

## What LSQ actually gives us (researched)

Field photos are captured via the LSQ mobile app into a **Custom Field Set "file" field**, stored on
LeadSquared's **private S3/CDN** (not public). A leads/activities **export is a CSV** with identifier
columns (Agent ID, Opportunity ID, …) and the image field as a **URL or bare filename** — NOT the
image files. So intake = a CSV of `{identifiers + image URL}`, and the images are **private** →
must be fetched **server-side with LSQ credentials**. (ProofLens already integrates with LSQ.)

## Architecture: server-side bulk job

Because the image URLs are private, the browser cannot fetch them — the **backend** fetches + scores.
Reuses what already exists:
- `LSQClient.fetch_image(url) -> bytes` (already on the real client; add to the Protocol + fake).
- `score(data, ctx) -> Verdict` (engine, unchanged).
- `repo.record_result(tenant_id, job_id=None, verdict, *, opportunity_id, rep_id, source="bulk")`
  (already accepts source + attribution).

Per photo: **fetch → score → record_result(source="bulk") → discard the image** (only the perceptual
hash + verdict are kept — the "images are never stored" promise holds). Fail-open per photo: a fetch or
score error records a per-row error and the batch continues. Throttled concurrency (memory-safe; Render
has OOM'd before). The recycled-image check runs across the batch, so intra-folder duplicates are caught.

## Phasing

- **Phase 1 (this spec) — Upload the LSQ export CSV.** Upload → map columns → run job → results.
  Testable now with any fetchable image URLs; the LSQ-auth fetch is behind `fetch_image`.
- **Phase 2 — Pull from LSQ directly** (no manual export): pick agent/team + date range → query the LSQ
  activities API → same job engine. Documented seam.
- **Phase 3 — Durable queue/worker** only if folders reach thousands.

## Backend contract (Phase 1, additive)

- `POST /v1/bulk-score` — body: `{ rows: [{ image_url, rep_id?, opportunity_id? }], label? }` (or a
  multipart CSV + column mapping). Creates a job, kicks off background processing, returns
  `{ job_id, total }`.
- `GET /v1/bulk-score/{job_id}` — `{ status: queued|running|done, processed, total, results: [{ image_url,
  rep_id, opportunity_id, band, score, reason_code, result_id, error? }] }`.
- **Job store:** in-memory registry keyed by job_id (Phase 1 — single instance demo; DB/queue is the
  Phase 3 seam, noted in BACKEND_REQUIREMENTS). Results ALSO persist as normal `Result` rows
  (`source="bulk"`), so they appear in analytics/history/review regardless of the job store's lifetime.
- **Concurrency:** small fixed cap (e.g. 4) with `asyncio`/threadpool; never load the whole folder into
  memory. **Fail-open:** exceptions per row → `error` field, job continues.
- **Attribution:** `rep_id`/`opportunity_id` normalized via the shared `normalize_id`; drives the org
  hierarchy join → team analytics.

## Column mapping

LSQ field names are tenant-configurable, so DON'T hardcode. The upload step lets the user map their CSV
columns → **Image URL** (required), **Agent/rep ID** (optional), **Opportunity ID** (optional). Preview
the first rows + validate (flag rows with no image URL) before running. Remember the mapping
(localStorage) for next time.

## Frontend module

- New nav item **"Bulk upload"** (`/bulk`).
- **Step 1 — Upload:** drop the LSQ export CSV; parse client-side.
- **Step 2 — Map & preview:** map columns; table preview + per-row validation; show N valid / N skipped.
- **Step 3 — Run:** POST rows → poll the job → live "X of N" progress.
- **Step 4 — Results:** table (image · agent · band · score · reason · error), band-mix summary, **CSV
  export**, and jump-links to Review Queue / Analytics (now populated).
- Honest states throughout: fail-open rows shown as errors, not hidden; empty/loading/error.

## Non-negotiables
Scoring/engine/webhook unchanged; images never stored; fail-open; additive endpoints documented in
`BACKEND_REQUIREMENTS.md`; small-sample guards still apply downstream.

## Phase-1 task breakdown
1. **BE:** add `fetch_image` to the `LSQClient` Protocol + fake; a `bulk` service (fetch→score→
   record_result source="bulk", throttled, fail-open) + in-memory job registry; the two endpoints;
   tests (fake LSQ + stub vision: batch scores + attributes + progresses; a bad row errors + batch
   continues). Document endpoints.
2. **FE:** the `/bulk` page (upload → CSV parse → column-map UI → run → poll → results table + export)
   + nav item + a pure CSV-parse/validate lib with tests.
