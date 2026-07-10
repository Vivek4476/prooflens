# DSE (agent) scorecard + search — Design

- **Date:** 2026-07-10
- **Owner decisions:** (1) "DSE" = the frontline agent (`rep_id`/`agent_id`). (2) DSE **names come
  from the hierarchy CSV** (new `agent_name` column). (3) **Scorecard + search** is the primary
  surface (not a 266-row leaderboard), with an optional ranked list for high-volume DSEs.
- **Additive:** scoring/engine/webhook unchanged. Layers on the existing hierarchy + analytics.

## Why scorecard-first
There are ~266 DSEs; most individuals have too few captures to rank fairly, so a "worst DSEs" list
would be mostly "not enough volume" under the existing small-sample guard. A **look-up-a-DSE**
scorecard is honest and far more useful; a ranked list is offered only among DSEs with ≥N captures.

## What exists
Every result already carries `rep_id`; the hierarchy resolves `rep_id → sm/rsm/srsm/zonal_head/
branch/city`. `group_by` supports the manager levels but **not the agent**, and the hierarchy has
**no agent name** (only `agent_id`).

## Changes

### A. DSE names in the hierarchy (prerequisite, additive)
- Add an optional **`agent_name`** column to the hierarchy schema: the CSV header, the upload
  validator/parser (`hierarchy_admin.py` / `service/hierarchy.py`), the `hierarchy` table (additive
  migration `0006_agent_name`, nullable), and `resolve_node` returns it. Absent → fall back to the
  `agent_id` as the display name (honest).
- Add realistic names to `scripts/sample-hierarchy.csv` (266 rows) and reseed.

### B. "agent" group_by dimension (additive)
- Extend `group_by` (`GROUP_BY_FIELD` / `GroupBy`) with **`agent`** → aggregates by `rep_id`, labeled
  with `agent_name` (falls back to id). Enables both the ranked list and a "By DSE" cut in the
  existing "Where to look" panel. Small-sample guard (≥20 scored) still applies to any ranking.

### C. DSE scorecard + search (the deliverable)
Backend (additive endpoints):
- `GET /v1/dse?q=<name-or-id>` → up to N matches `[{ agent_id, name, branch, sm }]` (search by name
  or id; tenant-scoped; empty q → recent/most-active).
- `GET /v1/dse/{agent_id}?from=&to=&bucket=` → the scorecard:
  `{ agent_id, name, chain: {sm,rsm,srsm,zone,branch,city}, total, band_distribution, suspect_rate,
    avg_score, top_reasons[], trend: [{bucket_label, start, end, suspect, total, suspect_rate,
    incomplete}], recent[] }` where `trend` = the DSE's per-bucket suspect rate over the range (reuse
    the analytics bucketing, filtered to this rep_id) and `recent` = the DSE's latest flagged captures
  (reuses `list_results(rep_id=…)`). Honest small-sample states when `total` is low.

Frontend (new page `/dse`):
- A **search box** (name or ID) → results list → select a DSE.
- The **scorecard**: header (name · id · manager chain SM→RSM→SRSM→Zone→Branch), the KPIs (total,
  suspect rate, avg score) with the same small-sample guards, a **suspect-rate trend** for this DSE
  over the range (reuse the CaptureRiskTrend area chart, honest incomplete-bucket marker), band-mix,
  top flag reasons, and a **recent flagged captures** list with drill-through to `/history?rep_id=…`.
- Entry points: a "By DSE" option in the analytics "Where to look" dimension selector whose rows link
  to `/dse/{id}`; and the global search box (already "Search opportunity or rep ID…") routes rep-ID
  matches here.
- Reuse existing components (Card, VerdictBadge, the bar-list, KpiRow patterns); BRAND-compliant.

## How it connects
- **Bulk upload + LSQ** populate `rep_id`-attributed captures → they fill the DSE scorecards. The
  hierarchy CSV (now with names) is the single source of DSE identity.
- Reuses drill-down (`/history?rep_id=`) already built.

## Non-negotiables
Additive; honest small-sample states (a sparse DSE shows real, un-fabricated numbers); verdict copy
verbatim; scoring unchanged; endpoints documented in BACKEND_REQUIREMENTS.md.

## Phase breakdown
1. **BE:** `agent_name` (schema + migration 0006 + upload + resolve + sample CSV + reseed); `agent`
   group_by; the two `/v1/dse` endpoints; tests.
2. **FE:** `/dse` search + scorecard page; "By DSE" dimension + row links; global-search routing; tests.
