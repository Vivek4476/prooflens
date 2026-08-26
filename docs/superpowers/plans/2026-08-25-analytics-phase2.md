# Analytics Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the real analytics gaps — kill the misleading `avg_score`, add a hierarchy-node drill-down (`/team`), and align the look to Mission Control — reusing the existing analytics toolkit and charts.

**Architecture:** One new backend capability: an optional `dim`+`node` filter on `repo.list_results`, threaded into `/v1/results` and `/v1/analytics/summary`, that restricts to decisions whose rep maps (effective-dated) to a hierarchy node. Everything else is frontend: swap KPI cards, delete one insight rule + CSV columns, and add a `/team` page that reuses every existing chart plus a member-rep leaderboard.

**Tech Stack:** Backend — Python 3.12, FastAPI, SQLAlchemy, pytest. Frontend — Next.js 15, React 18, TS, TanStack Query, Recharts, Vitest.

## Global Constraints

- **Reuse, don't rebuild:** the existing `lib/analytics/` toolkit and chart components (`CaptureRiskTrend`, `BandMixChart`, `TopFlagReasons`, `ByTeamPanel`, `KpiRow`) are reused; Phase 2 composes them.
- **`avg_score` stays in the API/types (backward-compat) but is removed from every UI display site.** Do not remove the backend field or the type field.
- **No flag-precision KPI** — it derives from human reviews that no longer happen under automation.
- **Verdict colors band-only, paired with the band word.** Crimson masthead/primary only. (carried from Phase 1)
- **Effective-dated hierarchy:** a result maps to the node effective at THAT result's scored date (`resolve_node(rows, rep_id, scored_date)`), never a static agent→node map.
- **Small-sample gates preserved:** `MIN_PREV_N`/`MIN_TOTAL_FOR_RATE = 20`.
- **Tests:** backend `.venv/bin/python -m pytest` (pytest auto-adds `src`); frontend `npm test` from `frontend/` (Vitest globals OFF — import from `"vitest"`). Use `git add <specific files>`, never `-A`.

---

## File Structure

**Backend:**
- `src/prooflens/service/hierarchy.py` *(modify)* — add a pure `node_match(rows, rep_id, scored_date, dim_field, node) -> bool` helper reusing `resolve_node`.
- `src/prooflens/service/repo.py` *(modify)* — `Repo` protocol + `InMemoryRepo.list_results` gain `dim`/`node`.
- `src/prooflens/db/repo.py` *(modify)* — `PostgresRepo.list_results` gains `dim`/`node` (Python-side filter before pagination when set).
- `src/prooflens/api/scoring.py` *(modify)* — `/v1/results` + `/v1/analytics/summary` gain `dim`/`node` Query params + `dim` validation.

**Frontend:**
- `src/lib/api/types.ts` *(modify)* — `AnalyticsParams` gains `dim?`, `node?`.
- `src/lib/analytics/useTeamFilters.ts` *(create)* — URL-state hook (mirrors `useAnalyticsFilters` + dim/node).
- `src/lib/analytics/bandRates.ts` *(create)* — pure `bandRate(dist, total, band)`.
- `src/components/analytics/KpiRow.tsx` *(modify)* — band-rate cards, no avg_score.
- `src/components/dse/DseKpiRow.tsx` *(modify)* — drop avg_score card.
- `src/lib/analytics/insights.ts` *(modify)* — delete `avgScoreShift`.
- `src/lib/analytics/exportCsv.ts` *(modify)* — drop `avg_score` columns.
- `src/app/(app)/mission-control/page.tsx` + `src/app/(app)/page.tsx` *(modify)* — drop avg_score KPI.
- `src/components/analytics/ByTeamPanel.tsx` *(modify)* — non-agent rows link to `/team`.
- `src/app/(app)/team/page.tsx` *(create)* — the drill-down page.

---

## Task 1: Backend — hierarchy-node filter on `list_results`

**Files:**
- Modify: `src/prooflens/service/hierarchy.py` (add `node_match`; existing `resolve_node` at ~line 18, `NODE_FIELDS` at ~14)
- Modify: `src/prooflens/service/repo.py` (`Repo.list_results` protocol + `InMemoryRepo.list_results` ~line 232)
- Modify: `src/prooflens/db/repo.py` (`PostgresRepo.list_results` ~line 153)
- Modify: `src/prooflens/api/scoring.py` (`/v1/results` ~176, `/v1/analytics/summary` ~236)
- Test: `tests/unit/test_list_results_scoping.py`

**Interfaces:**
- Consumes: `resolve_node(rows, agent_id, scored_date) -> dict | None` (hierarchy.py); `GROUP_BY_FIELD` (api/analytics.py, maps dim→hierarchy field, e.g. `zone→zonal_head`).
- Produces: `node_match(rows, rep_id, scored_date, dim_field, node) -> bool`; `list_results(..., dim: str | None = None, node: str | None = None)` on both repos; `/v1/results` + `/v1/analytics/summary` accept `dim`/`node` (unknown `dim` → 400; absent → unchanged).

- [ ] **Step 1: Write the failing test for the pure helper + repo filter**

```python
# tests/unit/test_list_results_scoping.py  (add to the existing file)
from datetime import UTC, datetime, timedelta
from prooflens.service.hierarchy import node_match

def _hier_rows():
    d = datetime.now(UTC).date() - timedelta(days=40)
    return [
        {"agent_id": "A1", "sm": "SM-North", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": d},
        {"agent_id": "A2", "sm": "SM-South", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "South", "city": None, "valid_from": d},
    ]

def test_node_match_true_when_rep_in_node():
    rows = _hier_rows(); day = datetime.now(UTC).date()
    assert node_match(rows, "A1", day, "branch", "North") is True
    assert node_match(rows, "A2", day, "branch", "North") is False

def test_node_match_false_for_unmapped_rep():
    assert node_match(_hier_rows(), "GHOST", datetime.now(UTC).date(), "branch", "North") is False

def test_list_results_filters_by_node(_repo_with_hierarchy):
    # _repo_with_hierarchy: InMemoryRepo seeded with A1(North)+A2(South) hierarchy and one
    # result per rep. See fixture below.
    repo = _repo_with_hierarchy
    items, total = repo.list_results(tenant_id="t1", limit=50, offset=0, dim="branch", node="North")
    assert total == 1
    assert all(r.rep_id == "A1" for r in items)

def test_list_results_no_filter_unchanged(_repo_with_hierarchy):
    _, total = _repo_with_hierarchy.list_results(tenant_id="t1", limit=50, offset=0)
    assert total == 2
```

Add a fixture near the top of the file (mirror the file's existing `InMemoryRepo` + `replace_hierarchy` usage):

```python
import pytest
from datetime import UTC, datetime, timedelta
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.engine.types import CheckOutcome, Verdict
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView

def _verdict(band="Clear"):
    return Verdict(band=band, score=80.0, reason="x", reason_code="clear",
                   rubric_version="v3", checks=[CheckOutcome(name="content", available=True,
                   score=80.0, summary="s", metric=None, data={}, latency_ms=1.0)])

@pytest.fixture
def _repo_with_hierarchy():
    repo = InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s",
                                    field_map={}, scoring=ScoringConfig(), vision_backend="stub")])
    d = datetime.now(UTC).date() - timedelta(days=40)
    repo.replace_hierarchy("t1", [
        {"agent_id": "A1", "sm": "SM-North", "rsm": None, "srsm": None, "zonal_head": None,
         "branch": "North", "city": None, "valid_from": d},
        {"agent_id": "A2", "sm": "SM-South", "rsm": None, "srsm": None, "zonal_head": None,
         "branch": "South", "city": None, "valid_from": d},
    ], "u1")
    repo.record_result("t1", None, _verdict(), rep_id="A1")
    repo.record_result("t1", None, _verdict(), rep_id="A2")
    return repo
```

> Confirm `InMemoryRepo.replace_hierarchy(tenant_id, rows, upload_id)` exists (it's used in `tests/integration/test_scoring_api.py:317`). If its name differs, use the actual seeding method.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/test_list_results_scoping.py -q`
Expected: FAIL — `cannot import name 'node_match'` / `list_results() got an unexpected keyword argument 'dim'`

- [ ] **Step 3a: Add the pure helper**

In `src/prooflens/service/hierarchy.py`, add:

```python
def node_match(
    rows: list[dict], rep_id: str | None, scored_date, dim_field: str, node: str
) -> bool:
    """True if rep_id's effective hierarchy row at scored_date has dim_field == node."""
    resolved = resolve_node(rows, rep_id, scored_date)
    if resolved is None:
        return False
    return resolved.get(dim_field) == node
```

- [ ] **Step 3b: Thread through both repos**

In `src/prooflens/service/repo.py`: add `dim: str | None = None, node: str | None = None` (keyword-only, after `end`) to the `Repo` protocol's `list_results` AND `InMemoryRepo.list_results`. In `InMemoryRepo`, after the existing in-memory filtering and BEFORE pagination/slicing, when both `dim` and `node` are set:

```python
        if dim and node:
            from .hierarchy import node_match
            from ..api.analytics import GROUP_BY_FIELD
            field = GROUP_BY_FIELD.get(dim)
            if field and field != "agent":
                rows = self._hierarchy.get(tenant_id, [])  # match how InMemoryRepo stores hierarchy
                filtered = [r for r in filtered
                            if node_match(rows, r.rep_id, r.created_at.date(), field, node)]
```

> Read `InMemoryRepo` to see the exact local variable holding the filtered result list and how it accesses stored hierarchy rows; adapt the two names (`filtered`, `self._hierarchy`) to reality. Recompute `total = len(filtered)` before slicing.

In `src/prooflens/db/repo.py` `PostgresRepo.list_results`: add the same params. When `dim` and `node` are set, do NOT apply SQL `offset/limit` first — fetch all candidate rows (existing tenant/band/reason/rep/date SQL filters), then filter in Python by `node_match` using `self.get_hierarchy_rows(tenant_id)`, then compute `total` and apply `offset`/`limit` slicing in Python:

```python
        if dim and node:
            from ..service.hierarchy import node_match
            from ..api.analytics import GROUP_BY_FIELD
            field = GROUP_BY_FIELD.get(dim)
            all_rows = query.order_by(Result.created_at.desc()).all()
            if field and field != "agent":
                hier = self.get_hierarchy_rows(tenant_id)
                all_rows = [r for r in all_rows
                            if node_match(hier, r.rep_id, r.created_at.date(), field, node)]
            total = len(all_rows)
            rows = all_rows[offset: offset + limit]
        else:
            total = query.count()
            rows = query.order_by(Result.created_at.desc()).offset(offset).limit(limit).all()
```

(Leave the existing `_to_view`/job-join code below unchanged.)

- [ ] **Step 3c: Add endpoint params + validation**

In `src/prooflens/api/scoring.py`, add to BOTH `/v1/results` and `/v1/analytics/summary`:

```python
    dim: str | None = Query(None),
    node: str | None = Query(None),
```

and pass `dim=dim, node=node` into every `repo.list_results(...)` call in both endpoints (analytics has TWO calls — current and previous period; add to both). Add validation at the top of each endpoint body:

```python
    from .analytics import GROUP_BY_FIELD
    if dim is not None and (dim not in GROUP_BY_FIELD or dim == "agent"):
        raise HTTPException(status_code=400, detail=f"invalid dim: {dim}")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_list_results_scoping.py -q` → PASS
Run: `.venv/bin/python -m pytest -q` → no regressions
Run: `.venv/bin/ruff check src/prooflens/service/hierarchy.py src/prooflens/service/repo.py src/prooflens/db/repo.py src/prooflens/api/scoring.py && .venv/bin/mypy src/prooflens` → clean

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/service/hierarchy.py src/prooflens/service/repo.py src/prooflens/db/repo.py src/prooflens/api/scoring.py tests/unit/test_list_results_scoping.py
git commit -m "feat(analytics): hierarchy-node (dim+node) filter on list_results + endpoints"
```

---

## Task 2: Frontend — params plumbing + team-filters hook

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (`AnalyticsParams` ~line 168)
- Create: `frontend/src/lib/analytics/useTeamFilters.ts`
- Test: `frontend/src/lib/analytics/useTeamFilters.test.ts` (pure param-assembly test)

**Interfaces:**
- Consumes: `useAnalyticsFilters` pattern, `resolvePreset`/`DEFAULT_PRESET`/`DEFAULT_BUCKET` (`dateRanges.ts`), `useUrlState`.
- Produces: `AnalyticsParams` with optional `dim?: string; node?: string`; `useTeamFilters()` returning `{ dim, node, preset, bucket, from, to, params, setPreset, setCustomRange, setBucket }` where `params` includes `dim`, `node`, and `group_by: "agent"`.

- [ ] **Step 1: Extend the type**

In `frontend/src/lib/api/types.ts`, add to `interface AnalyticsParams`:

```typescript
  dim?: string;
  node?: string;
```

(`api.analytics(params)` already spreads params to the query string, so no client change is needed.)

- [ ] **Step 2: Write the failing hook test (test the pure param assembly)**

```typescript
// frontend/src/lib/analytics/useTeamFilters.test.ts
import { describe, it, expect } from "vitest";
import { teamParams } from "./useTeamFilters";

describe("teamParams", () => {
  it("includes dim, node, and group_by=agent", () => {
    const p = teamParams({ start_date: "2026-08-01", end_date: "2026-08-30", bucket: "daily" }, "branch", "North");
    expect(p).toEqual({
      start_date: "2026-08-01", end_date: "2026-08-30", bucket: "daily",
      group_by: "agent", dim: "branch", node: "North",
    });
  });
});
```

- [ ] **Step 3: Implement the hook + exported pure helper**

```typescript
// frontend/src/lib/analytics/useTeamFilters.ts
"use client";

import { useMemo } from "react";
import type { AnalyticsParams, Bucket } from "@/lib/api/types";
import { useUrlState } from "@/lib/useUrlState";
import { DEFAULT_BUCKET, DEFAULT_PRESET, resolvePreset, type RangePreset } from "./dateRanges";

const DEFAULTS = {
  range: DEFAULT_PRESET as string,
  bucket: DEFAULT_BUCKET as string,
  from: undefined as string | undefined,
  to: undefined as string | undefined,
  dim: undefined as string | undefined,
  node: undefined as string | undefined,
};
const ALLOWED_KEYS = ["range", "bucket", "from", "to", "dim", "node"] as const;

/** Pure: assemble the analytics query for a team (node-scoped, per-agent breakdown). */
export function teamParams(
  resolved: { start_date: string; end_date: string; bucket: Bucket },
  dim: string | undefined,
  node: string | undefined,
): AnalyticsParams {
  return { ...resolved, group_by: "agent", dim, node };
}

export function useTeamFilters() {
  const [urlState, setUrlState] = useUrlState(DEFAULTS, [...ALLOWED_KEYS]);
  const preset = (urlState.range as RangePreset) || DEFAULT_PRESET;
  const bucket = (urlState.bucket as Bucket) || DEFAULT_BUCKET;
  const resolved = useMemo(
    () => resolvePreset(preset, new Date(), { start_date: urlState.from, end_date: urlState.to }),
    [preset, urlState.from, urlState.to],
  );
  const params = useMemo(
    () => teamParams({ ...resolved, bucket }, urlState.dim, urlState.node),
    [resolved, bucket, urlState.dim, urlState.node],
  );
  return {
    dim: urlState.dim, node: urlState.node, preset, bucket, from: urlState.from, to: urlState.to,
    params,
    setPreset: (n: RangePreset) => setUrlState({ range: n, from: undefined, to: undefined }),
    setCustomRange: (from: string, to: string) => setUrlState({ range: "custom", from, to }),
    setBucket: (n: Bucket) => setUrlState({ bucket: n }),
  };
}
```

- [ ] **Step 4: Run test + tsc**

Run (frontend/): `npm test -- useTeamFilters` → PASS
Run: `npx tsc --noEmit` → 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/analytics/useTeamFilters.ts frontend/src/lib/analytics/useTeamFilters.test.ts
git commit -m "feat(fe): AnalyticsParams dim/node + useTeamFilters hook"
```

---

## Task 3: Kill `avg_score` on /analytics (KpiRow + insights + exportCsv)

**Files:**
- Create: `frontend/src/lib/analytics/bandRates.ts`
- Modify: `frontend/src/components/analytics/KpiRow.tsx`
- Modify: `frontend/src/lib/analytics/insights.ts`
- Modify: `frontend/src/lib/analytics/exportCsv.ts`
- Test: `frontend/src/lib/analytics/bandRates.test.ts`, `frontend/src/components/analytics/KpiRow.test.tsx`

**Interfaces:**
- Consumes: `AnalyticsSummary` (`band_distribution`, `suspect_pct`, `total`, `previous`), `computeDelta`, `MetricCard`, `formatPct`, `formatCount`.
- Produces: `bandRate(dist, total, band) -> number`; `KpiRow` renders Total scored · Suspect rate · Doubtful rate · Unassessed rate (no avg_score, no duplicates card).

- [ ] **Step 1: Write the failing pure test**

```typescript
// frontend/src/lib/analytics/bandRates.test.ts
import { describe, it, expect } from "vitest";
import { bandRate } from "./bandRates";

describe("bandRate", () => {
  const dist = { Clear: 70, Doubtful: 20, Suspect: 8, Unassessed: 2 };
  it("returns the band's percentage of total", () => {
    expect(bandRate(dist, 100, "Doubtful")).toBe(20);
    expect(bandRate(dist, 100, "Unassessed")).toBe(2);
  });
  it("returns 0 when total is 0", () => {
    expect(bandRate({ Clear: 0, Doubtful: 0, Suspect: 0, Unassessed: 0 }, 0, "Suspect")).toBe(0);
  });
});
```

- [ ] **Step 2: Run → fail** (`cannot find module ./bandRates`)

Run (frontend/): `npm test -- bandRates`

- [ ] **Step 3a: Implement bandRate**

```typescript
// frontend/src/lib/analytics/bandRates.ts
import type { Band } from "@/lib/api/types";

export function bandRate(
  dist: Record<Band, number>, total: number, band: Band,
): number {
  if (!total) return 0;
  return (dist[band] / total) * 100;
}
```

- [ ] **Step 3b: Rewrite KpiRow** (replace the whole `return (...)` card grid and drop the avg_score + duplicates deltas)

Replace the component body's delta computations and JSX so it renders exactly four cards. Keep `totalDelta` and `suspectRateDelta` as-is; DELETE `avgScoreDelta` and the `dupDelta` block; simplify props (remove `prevDuplicatesCaught`, `prevDuplicatesUnavailable`). New JSX:

```tsx
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <MetricCard label="Total scored" value={formatCount(a.total)}
        sub={deltaSub(totalDelta)} subDirection={totalDelta.direction} />
      <MetricCard label="Suspect rate" value={formatPct(a.suspect_pct)}
        sub={deltaSub(suspectRateDelta)} subDirection={suspectRateDelta.direction} accent />
      <MetricCard label="Doubtful rate" value={formatPct(bandRate(a.band_distribution, a.total, "Doubtful"))}
        sub="share of scored" />
      <MetricCard label="Unassessed rate" value={formatPct(bandRate(a.band_distribution, a.total, "Unassessed"))}
        sub="vision unavailable at ingest" />
    </div>
  );
```

Add `import { bandRate } from "@/lib/analytics/bandRates";`. Update the `KpiRow` prop type to `{ analytics: AnalyticsSummary }` only. Then update its call site in `app/(app)/analytics/page.tsx` to `<KpiRow analytics={a} />` (remove the now-unused `prevDuplicatesCaught`/`prevDuplicatesUnavailable` props there — if that page computed `prevDuplicatesCaught` solely for KpiRow, leave that computation if `computeInsights` still needs it; otherwise remove).

> Doubtful/Unassessed rates are shown as current values (no delta) because `PeriodAggregate` may not carry per-band previous counts. Read `PeriodAggregate` in `types.ts`: IF it exposes `doubtful`/`unassessed` counts, you MAY add deltas via `computeDelta(rate, prevRate, a.previous.total, {higherIsBad:true, unit:"pts"})`; if not, keep the static `sub` strings above. Do not invent fields.

- [ ] **Step 3c: Write a KpiRow render test**

```tsx
// frontend/src/components/analytics/KpiRow.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiRow } from "./KpiRow";
import type { AnalyticsSummary } from "@/lib/api/types";

const a = {
  total: 100, suspect_pct: 8, avg_score: 73,
  band_distribution: { Clear: 70, Doubtful: 20, Suspect: 8, Unassessed: 2 },
  previous: { total: 90, suspect: 6, avg_score: 71 },
} as unknown as AnalyticsSummary;

describe("KpiRow", () => {
  it("shows band-rate KPIs and NO avg score", () => {
    render(<KpiRow analytics={a} />);
    expect(screen.getByText("Doubtful rate")).toBeInTheDocument();
    expect(screen.getByText("Unassessed rate")).toBeInTheDocument();
    expect(screen.queryByText("Avg score")).toBeNull();
  });
});
```

- [ ] **Step 3d: Delete `avgScoreShift`**

In `frontend/src/lib/analytics/insights.ts`: delete the `avgScoreShift` function (~lines 71–84) and remove the `avgScoreShift(a),` entry from the `candidates` array in `computeInsights`.

- [ ] **Step 3e: Remove avg_score from CSV**

In `frontend/src/lib/analytics/exportCsv.ts`: remove `"avg_score"` from `HEADERS`, remove `b.avg_score,` from both `bucketsToCsv` and the time-series loop in `analyticsToCsv`, and delete the `lines.push(csvRow(["Avg score", a.avg_score]));` headline line.

- [ ] **Step 4: Run tests + gates**

Run (frontend/): `npm test -- bandRates KpiRow` → PASS; `npm test` → full suite green
Run: `npx tsc --noEmit` and `npx eslint src/components/analytics/KpiRow.tsx src/lib/analytics/bandRates.ts src/lib/analytics/insights.ts src/lib/analytics/exportCsv.ts` → clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/analytics/bandRates.ts frontend/src/lib/analytics/bandRates.test.ts frontend/src/components/analytics/KpiRow.tsx frontend/src/components/analytics/KpiRow.test.tsx frontend/src/lib/analytics/insights.ts frontend/src/lib/analytics/exportCsv.ts frontend/src/app/\(app\)/analytics/page.tsx
git commit -m "feat(fe): kill avg_score on /analytics — band-rate KPIs, drop insight+CSV"
```

---

## Task 4: Kill `avg_score` on the other surfaces (DSE, Mission Control, Dashboard)

**Files:**
- Modify: `frontend/src/components/dse/DseKpiRow.tsx`
- Modify: `frontend/src/app/(app)/dse/page.tsx` (its `<DseKpiRow .../>` call site)
- Modify: `frontend/src/app/(app)/mission-control/page.tsx`
- Modify: `frontend/src/app/(app)/page.tsx` (dashboard)
- Test: extend `frontend/src/components/mission/DecisionStream.test.tsx`? No — add a small assertion via build; primary gate is tsc/eslint/build + a DseKpiRow test.
- Test: `frontend/src/components/dse/DseKpiRow.test.tsx`

**Interfaces:**
- Consumes: `bandRate` (Task 3), `DseScorecard.band_distribution`, `MetricCard`.
- Produces: `DseKpiRow({ total, suspectRate, bandDistribution })` (avgScore prop removed).

- [ ] **Step 1: Failing DseKpiRow test**

```tsx
// frontend/src/components/dse/DseKpiRow.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DseKpiRow } from "./DseKpiRow";

describe("DseKpiRow", () => {
  it("shows Unassessed rate, not Avg score", () => {
    render(<DseKpiRow total={50} suspectRate={0.1}
      bandDistribution={{ Clear: 40, Doubtful: 5, Suspect: 5, Unassessed: 0 }} />);
    expect(screen.getByText("Unassessed rate")).toBeInTheDocument();
    expect(screen.queryByText("Avg score")).toBeNull();
  });
});
```

- [ ] **Step 2: Run → fail**

Run (frontend/): `npm test -- DseKpiRow`

- [ ] **Step 3a: Rewrite DseKpiRow** — replace the `avgScore` prop + card with an `Unassessed rate` card computed from `bandDistribution`:

```tsx
import { bandRate } from "@/lib/analytics/bandRates";
import type { Band } from "@/lib/api/types";
// ...
export function DseKpiRow({
  total, suspectRate, bandDistribution,
}: {
  total: number; suspectRate: number; bandDistribution: Record<Band, number>;
}) {
  const sparse = isSparseDse(total);
  const sparseNote = `Fewer than ${MIN_TOTAL_FOR_CONFIDENT_RATE} scored — not enough volume to read confidently.`;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <MetricCard label="Total scored" value={formatCount(total)} sub={sparse ? sparseNote : undefined} />
      <MetricCard label="Suspect rate" value={formatPct(suspectRate * 100)} sub={sparse ? sparseNote : undefined} accent />
      <MetricCard label="Unassessed rate" value={formatPct(bandRate(bandDistribution, total, "Unassessed"))}
        sub={sparse ? sparseNote : undefined} />
    </div>
  );
}
```

Update the `/dse` page call site to `<DseKpiRow total={data.total} suspectRate={data.suspect_rate} bandDistribution={data.band_distribution} />`.

- [ ] **Step 3b: Mission Control** — in `app/(app)/mission-control/page.tsx`, replace the `Avg score` `MetricCard` with:

```tsx
        <MetricCard label="Unassessed" value={a ? formatPct(bandRate(a.band_distribution, a.total, "Unassessed")) : "—"} />
```

Add `import { bandRate } from "@/lib/analytics/bandRates";`.

- [ ] **Step 3c: Dashboard** — in `app/(app)/page.tsx`, remove the `Avg score` `MetricCard` (or replace with the same Unassessed card, matching whatever the row's card count expects).

- [ ] **Step 4: Tests + gates + build**

Run (frontend/): `npm test -- DseKpiRow` → PASS; `npm test` → green
Run: `npx tsc --noEmit`; `npx eslint src/components/dse src/app/\(app\)/mission-control src/app/\(app\)/page.tsx src/app/\(app\)/dse`; `npm run build` → succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dse/DseKpiRow.tsx frontend/src/components/dse/DseKpiRow.test.tsx frontend/src/app/\(app\)/dse/page.tsx frontend/src/app/\(app\)/mission-control/page.tsx frontend/src/app/\(app\)/page.tsx
git commit -m "feat(fe): remove avg_score from DSE, Mission Control, Dashboard"
```

---

## Task 5: `/team` drill-down page + ByTeamPanel links

**Files:**
- Create: `frontend/src/app/(app)/team/page.tsx`
- Modify: `frontend/src/components/analytics/ByTeamPanel.tsx` (row link)
- Test: extend `ByTeamPanel` behavior via a small unit on the link target (or rely on build); primary gate is `npm run build` with `/team` emitted.

**Interfaces:**
- Consumes: `useTeamFilters` (Task 2), `useAnalytics` (with `params` incl. `dim/node/group_by=agent`), `PageHeader`, `Card`, `FilterBar`, `CaptureRiskTrend`, `BandMixChart`, `TopFlagReasons`, `ByTeamPanel`-style ranking (`rankHotspots`), `KpiRow` (Task 3), `EmptyState`, skeletons, `AnalyticsSummary`/`AnalyticsGroup` types.
- Produces: `TeamPage` default export at route `/team?dim=&node=`.

- [ ] **Step 1: Add the ByTeamPanel drill-down link**

In `frontend/src/components/analytics/ByTeamPanel.tsx`, extend `onRowSelect`:

```tsx
  function onRowSelect(g: AnalyticsGroup) {
    if (dimension === "agent" && g.agent_id) {
      router.push(`/dse?agent=${encodeURIComponent(g.agent_id)}`);
    } else if (dimension !== "agent") {
      router.push(`/team?dim=${encodeURIComponent(dimension)}&node=${encodeURIComponent(g.node)}`);
    }
  }
```

- [ ] **Step 2: Implement the page** (mirrors `/dse` composition; ONE `useAnalytics` call returns node-scoped buckets/band-mix/top-reasons AND `groups` = the member reps)

```tsx
// frontend/src/app/(app)/team/page.tsx
"use client";

import { Suspense } from "react";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { CardsSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { KpiRow } from "@/components/analytics/KpiRow";
import { CaptureRiskTrend } from "@/components/analytics/CaptureRiskTrend";
import { BandMixChart } from "@/components/analytics/BandMixChart";
import { TopFlagReasons } from "@/components/analytics/TopFlagReasons";
import { useAnalytics } from "@/lib/api/hooks";
import { useTeamFilters } from "@/lib/analytics/useTeamFilters";
import { rankHotspots } from "@/lib/analytics/hotspots";
import { formatPct, formatCount } from "@/lib/format";

function TeamInner() {
  const router = useRouter();
  const { dim, node, params, from, to, bucket } = useTeamFilters();
  const { data: a, isLoading } = useAnalytics(params, Boolean(dim && node));

  if (!dim || !node) {
    return <EmptyState icon={Users} title="No team selected"
      what="Open a team from the Analytics leaderboard to see its scorecard." />;
  }
  return (
    <div className="space-y-8">
      <PageHeader title={node} description={`Team scorecard · by ${dim}`} />
      {isLoading || !a ? (
        <CardsSkeleton count={4} />
      ) : a.total === 0 ? (
        <EmptyState icon={Users} title="No decisions" what={`No scored captures for ${node} in range.`} />
      ) : (
        <div className="space-y-8">
          <KpiRow analytics={a} />
          <div className="grid gap-6 lg:grid-cols-2">
            <CaptureRiskTrend buckets={a.buckets} previous={a.previous} bucket={bucket} from={from} to={to} />
            <BandMixChart buckets={a.buckets} bucket={bucket} from={from} to={to} />
          </div>
          <TopFlagReasons topReasons={a.top_reasons} from={from} to={to} />
          <Card>
            <CardHeader title="Members" subtitle="reps in this team, highest risk first" />
            <ul className="p-2">
              {rankHotspots(a.groups, { minTotal: 20 }).ranked.map((g, i) => (
                <li key={g.agent_id ?? g.node}>
                  <button onClick={() => g.agent_id && router.push(`/dse?agent=${encodeURIComponent(g.agent_id)}`)}
                    className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-surface-2">
                    <span className="w-4 text-caption tabular-nums text-text-muted">{i + 1}</span>
                    <span className="flex-1 truncate text-body-sm">{g.node}</span>
                    <span className="text-body-sm tabular-nums text-text-secondary">
                      {formatPct(g.suspect_rate * 100)} · {formatCount(g.total)} scored
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function TeamPage() {
  return <Suspense fallback={<CardsSkeleton count={4} />}><TeamInner /></Suspense>;
}
```

> Confirm `rankHotspots(groups, opts)` returns `{ ranked, ... }` and each ranked row has `node`, `agent_id`, `suspect_rate`, `total` (from the Task-scout: it ranks `AnalyticsGroup[]` by suspect_rate). Confirm `CaptureRiskTrend`/`BandMixChart`/`TopFlagReasons` prop names match (buckets/previous/bucket/from/to; topReasons/from/to). Confirm `CardsSkeleton`/`TableSkeleton` exports. Adjust imports to reality; do not invent props.
> `/team` is a drill-down target (like `/dse`) — do NOT add it to `NAV`.

- [ ] **Step 3: Gates + build**

Run (frontend/): `npx tsc --noEmit`; `npx eslint src/app/\(app\)/team src/components/analytics/ByTeamPanel.tsx`; `npm run build` → succeeds with route `/team` emitted.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(app\)/team frontend/src/components/analytics/ByTeamPanel.tsx
git commit -m "feat(fe): /team drill-down page + ByTeamPanel node links"
```

---

## Task 6: Visual consistency pass (Mission Control alignment)

**Files:**
- Modify (as needed): `frontend/src/app/(app)/analytics/page.tsx`, `frontend/src/app/(app)/team/page.tsx`
- Test: `npm run build` + visual check.

**Interfaces:** none new — this is a restyle using existing `Card`/`CardHeader`/`PageHeader`/tokens.

- [ ] **Step 1: Audit for divergence**

`/analytics` and `/dse` already use the shared design system (`Card`, `MetricCard`, `PageHeader`, tokens) — the same primitives as Mission Control, so most alignment is already satisfied. Compare `/analytics` and `/team` against `mission-control/page.tsx` for: page-level spacing (`space-y-6` vs `space-y-8`), section headers (`CardHeader` title/subtitle usage), and card density. Make ONLY the changes needed for visual consistency:
- Ensure each chart/section on `/team` is wrapped in a `Card` with a `CardHeader` (title + subtitle) matching Mission Control's pattern.
- Normalise page vertical rhythm to match Mission Control (`space-y-6`).
Do not restructure data or logic; do not restyle shared components (that would affect all pages).

- [ ] **Step 2: Verify**

Run (frontend/): `npx tsc --noEmit`; `npm run build` → succeeds. Manual: `/analytics`, `/team`, `/mission-control` read as one cohesive system (same card look, spacing, headers).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(app\)/analytics/page.tsx frontend/src/app/\(app\)/team/page.tsx
git commit -m "style(fe): align analytics + team pages to Mission Control"
```

---

## Self-Review

**Spec coverage:**
- Unit A (backend node filter) → Task 1. ✅
- Unit B (kill avg_score + trustworthy KPIs) → Tasks 3 + 4; flag-precision dropped (not added). ✅
- Unit C (team drill-down) → Tasks 2 (plumbing) + 5 (page + links). ✅
- Unit D (visual refresh) → Task 6 (light, since the design system is already shared). ✅

**Placeholder scan:** no TBD/TODO; every code step shows code. Two explicit "confirm against reality" notes (InMemoryRepo hierarchy accessor names; PeriodAggregate per-band fields; rankHotspots/chart prop names) are grounded conditionals with a named fallback, not placeholders.

**Type consistency:** `bandRate(dist, total, band)` defined in Task 3, consumed in Tasks 4 + 5. `AnalyticsParams.dim/node` (Task 2) consumed by Task 5's `useAnalytics(params)`. `DseKpiRow({total, suspectRate, bandDistribution})` signature consistent between Task 4 def and its `/dse` call site. `node_match` signature consistent between hierarchy.py (Task 1 def) and both repos.

**Deferred (documented):** provenance-coverage KPI (gated on provenance engine); backend removal of avg_score (kept for compat); new chart types (none — reuse).
