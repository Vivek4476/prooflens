# Phase 2 — Analytics: Close the Gaps

**Date:** 2026-08-25
**Status:** Design approved; ready for implementation plan
**Branch:** `feature/analytics-phase2` (stacked on `feature/glass-cockpit-redesign` / PR #29)
**Precedes:** builds on the Phase-1 Glass Cockpit; see `2026-08-24-prooflens-glass-cockpit-redesign-design.md` §3.

---

## 1. Context

Analytics is **~80% already built** and must be **reused, not rebuilt**. Existing and kept as-is:

- **`/analytics` page:** `KpiRow`, `SystemHealthLine`, `CaptureRiskTrend` (suspect % over time), `BandMixChart`
  (100%-stacked band distribution), `TopFlagReasons` (ranked flag drivers, drill to `/history`),
  `ByTeamPanel` (hotspot ranking by any hierarchy dimension), `InsightsRail` (rule-engine bullets).
- **`lib/analytics/` toolkit:** `dateRanges`, `useAnalyticsFilters`, `chartData`, `insights`, `deltas`,
  `hotspots` — all reused unchanged.
- **`/dse` per-rep scorecard** page + `lib/dse/scorecard.ts`.
- **Backend `GET /v1/analytics/summary`** already returns `band_distribution`, `buckets` (daily/weekly/
  monthly trend), `top_reasons`, `groups` (per-node breakdown for `group_by=zone|srsm|rsm|sm|branch|
  city|agent`, each with `suspect_rate`, `share`, `avg_score`), `system_health`, and `avg_score`.

Phase 2 = close the **narrow real gaps**, not duplicate the above.

**Honest correction to the audit's suggestion:** the audit proposed *flag-precision* as a replacement KPI.
Flag-precision is derived from **human review decisions** (`review_status`), which **no longer occur** in the
fully-automated redesign — so it would read empty. Phase 2 therefore **drops flag-precision as a KPI** and
replaces `avg_score` with metrics that are real in an automated world.

---

## 2. The four units

### A. Backend — hierarchy-node scope filter *(the one genuinely-new backend piece)*
Add optional `dim` + `node` query params to **`GET /v1/results`** and **`GET /v1/analytics/summary`**:
- `dim ∈ {zone, srsm, rsm, sm, branch, city}` and `node = <label>` → restrict the result set to decisions
  whose rep maps (via the existing hierarchy join) to that node.
- Reuses the existing `GROUP_BY_FIELD` mapping and hierarchy-join logic already in `api/analytics.py` /
  `db/repo.py` — this is a *filter*, not new aggregation. `dim=agent` is out of scope (per-rep drill-down is
  already `/dse`).
- Absent params → unchanged behaviour (backward-compatible). Unknown `dim` → 400; unknown `node` → empty set
  (valid, not an error).
This unlocks a team-scoped view without new aggregation code.

### B. Kill `avg_score` + trustworthy KPIs *(audit C3)*
- **Remove `avg_score` from every display site:** `KpiRow`, `DseKpiRow`, mission-control page, dashboard,
  `lib/analytics/exportCsv.ts`, and the `avgScoreShift` rule in `insights.ts`. **Keep** the field in the API
  response and types for backward-compat (no backend removal).
- **Replace the KPI set** (`KpiRow`) with metrics real under automation: **Total scored · Suspect rate ·
  Doubtful rate · Unassessed rate** (the vision-availability / trust signal). `SystemHealthLine`
  (median time-to-score + fail-open %) stays and is given more prominence.
- The `avgScoreShift` insight rule is deleted (it had no drill-down anyway); the other three insight rules
  (suspect-rate shift, dominant-reason, duplicates shift) remain.

### C. Team/region drill-down page `/team?dim=&node=` *(the real capability gap)*
A node-scoped analytics page that **reuses every existing chart** (`CaptureRiskTrend`, `BandMixChart`,
`TopFlagReasons`, the new KPI row) fed by `/v1/analytics/summary?dim=&node=`, **plus a member-rep
leaderboard**: the reps under that node (`group_by=agent` scoped to the node) ranked by suspect-rate via the
existing `rankHotspots`, each row linking to `/dse?agent=<id>`. `ByTeamPanel`'s non-DSE rows — currently
dead — link here (`/team?dim=<dim>&node=<label>`). Mirrors the DSE drill-down one hierarchy level up.
Page composition only; no new chart components.

### D. Glass-cockpit visual refresh
Align `/analytics` and the new `/team` to the Phase-1 Mission Control look — same `Card`/`CardHeader`,
tokens, density, `PageHeader`. Restyle only; no new data or logic. Verdict colors stay band-only.

---

## 3. Architecture & data flow

```
/v1/analytics/summary?dim=&node=  ──►  same aggregate_range(), pre-filtered to node
/v1/results?dim=&node=            ──►  same list, pre-filtered to node
        │                                        │
        ▼                                        ▼
  /analytics (unchanged data)            /team?dim=&node=  (scoped charts + member leaderboard)
        │  ByTeamPanel rows ─────────────────────┘  (non-DSE dims now link here)
        └─ DSE dim rows ─► /dse?agent=…  (unchanged)
```

- **Reused unchanged:** the whole `lib/analytics/` toolkit, every chart component, `useAnalyticsFilters`,
  the `groups`/`buckets` response shapes.
- **New/changed frontend units:** `app/(app)/team/page.tsx` (new), `KpiRow` (KPI set swap), `ByTeamPanel`
  (row links), `exportCsv`/`insights` (drop avg_score), plus a small `useTeamScope` param hook.
- **New/changed backend units:** the `dim`/`node` filter threaded into the results query + analytics summary
  (one filter helper, reused by both endpoints).

---

## 4. Error handling & edge cases
- **Small-sample gates preserved:** `rankHotspots`/`deltas` keep `MIN_PREV_N`/`MIN_TOTAL_FOR_RATE = 20` so a
  team or rep with < 20 scored doesn't produce a fake rate.
- **Unmapped reps:** a node filter excludes "Unmapped" reps (they belong to no node); `/team` shows only
  mapped members, consistent with `ByTeamPanel`.
- **Empty node:** unknown/empty `node` → valid empty result set, `EmptyState`, not an error.
- **avg_score still in API:** removing it from the UI must not break any consumer that reads the field
  (types keep it optional); only display sites change.
- **Unassessed:** the new "Unassessed rate" KPI reads `band_distribution.Unassessed / total`.

## 5. Testing
- Backend: pytest for the `dim`/`node` filter (filters correctly, backward-compatible when absent, unknown
  dim → 400, unknown node → empty). The existing analytics suite stays green.
- Frontend: Vitest for the new KPI derivations (suspect/doubtful/unassessed rate from `band_distribution`),
  the `useTeamScope` param hook, and `ByTeamPanel` row-link targets; `tsc` + eslint + `next build` with the
  `/team` route emitted. Assert `avg_score` no longer appears on `/analytics`, mission-control, dashboard, DSE.

## 6. Out of scope / deferred
- **Provenance-coverage KPI** — gated on the provenance-engine sub-project (Phase-1 gauge is a placeholder);
  not a Phase-2 KPI.
- Removing `avg_score` from the backend API / DB (kept for backward-compat).
- New chart *types* — Phase 2 composes existing charts only.
- NL search, dispute→re-score (Phase-1 deferred items, unchanged).

## 7. Decisions log
- ✅ Reuse the existing analytics toolkit + charts; Phase 2 closes gaps only.
- ✅ Drop flag-precision as a KPI (no human reviews under automation); replace avg_score with band-rate KPIs.
- ✅ Node filter is a *filter* on existing aggregation, not new aggregation.
- ✅ `/team` reuses charts + adds a member-rep leaderboard; `dim=agent` stays `/dse`.
- ✅ Stacked on the Phase-1 branch; merges after (or with) PR #29.
