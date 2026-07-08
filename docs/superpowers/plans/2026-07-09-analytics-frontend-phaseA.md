# Analytics Dashboard Redesign — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Rebuild `frontend/src/app/(app)/analytics/page.tsx` into a filterable, insight-led
analytics dashboard: a global date-range + aggregation filter bar (state serialized to
the URL), a computed insights block, four KPI cards with worded period-over-period
deltas, a capture-risk trend chart, a band-mix stacked chart, and a ranked top-flag-reasons
list — all reusing existing UI primitives, all honest in loading/empty/error states, in
both themes, responsive down to ≤1024px.

**Explicitly OUT of scope for Phase A** (per BRAND.md §8/§9 and the task brief): by-team
breakdown (`group_by`/`groups[]` consumption), hierarchy CSV upload, and any drill-down
navigation. The data layer will accept `group_by` as a parameter (future-proofing the
hook signature) but no Phase-A UI will set it to anything but `"none"`, and `groups[]`
is not rendered.

## Architecture

- **Data layer** (`frontend/src/lib/api/{types.ts,client.ts,hooks.ts}`): extend
  `AnalyticsSummary` with the already-live backend fields (`buckets`, `previous`,
  `period`, `previous_period`, `groups`, and `short_label` on `top_reasons`); add
  `api.analytics(params)` accepting `{start_date?, end_date?, bucket?, group_by?}`; add
  `useAnalytics({range, bucket, groupBy})`, ONE React Query keyed on the resolved
  params, debounced 300ms, that replaces the current zero-arg `useAnalytics()`.
- **URL state** (`frontend/src/lib/useUrlState.ts`, new): a small generic hook that
  reads/writes a typed slice of state to `useSearchParams`/`router.replace`, so the
  entire filter-bar selection (range preset, custom from/to, bucket) round-trips through
  a pasted URL. The Analytics page composes this into a `useAnalyticsFilters()` hook.
- **Pure logic** (new, framework-free, unit-tested): `frontend/src/lib/analytics/
  insights.ts` (insight rules), `frontend/src/lib/analytics/deltas.ts` (worded delta +
  good/bad-for-integrity coloring + small-sample guard), `frontend/src/lib/format.ts`
  (number formatting: thousands separators, rounding, tabular-numeral-safe strings).
  `useUrlState`'s serialize/parse functions are also pure and unit-tested directly.
- **Presentation**: new widget components under `frontend/src/components/analytics/`
  (`FilterBar.tsx`, `InsightsPanel.tsx`, `KpiRow.tsx`, `CaptureRiskTrend.tsx`,
  `BandMixChart.tsx`, `TopFlagReasons.tsx`), composed by a slimmed-down
  `analytics/page.tsx`. They reuse `MetricCard`, `ChartCard`, `Card`, `EmptyState`,
  `Skeleton`, `Button`, `VerdictBadge`'s color tokens — no new base primitives.
- **Brand-compliance fixes** ride along in Task 2 (tokens/Tailwind) and Task 4
  (MetricCard) since every later widget depends on them: `--accent` token, real
  `--verdict-suspect` `#DC2F45` light value, MetricCard label case + icon removal,
  Sidebar active-state left bar removal.

## Tech Stack

Next.js 15 (App Router) · React 18 · TypeScript 5 (strict) · Tailwind CSS 3 ·
`@tanstack/react-query` v5 · `recharts` v2 · `axios` · `lucide-react` · `next-themes` ·
Vitest + React Testing Library (net-new, installed in Task 1) · existing `next lint` /
`tsc --noEmit` / `next build` gates.

## Global Constraints

### BRAND.md rules (verbatim obligations — apply to every task)

- **Real tokens only**, no invented names: `--text` / `--text-secondary` / `--text-muted`;
  `--surface` / `--surface-2` / `--surface-3`; `--border` / `--border-strong`; `--canvas`;
  `--verdict-clear` / `--verdict-doubtful` / `--verdict-suspect` (each with paired
  `-bg` / `-fg`); `--radius` (10px) / `--radius-sm` (7px); `--shadow-1` / `--shadow-2`.
  No hex values outside `tokens.css`.
- Type utilities only: `text-display`, `text-h1`, `text-h2`, `text-body`, `text-body-sm`,
  `text-caption`. Body-strong = `text-body` + `font-semibold`, never its own class.
- `.dark` class via next-themes (`attribute="class"`), already wired in `providers.tsx`.
  Every widget must be screenshotted/verified in both themes.
- **Sentence case everywhere. No uppercase, ever** (this fixes an existing MetricCard bug
  — see Task 4). No exclamation marks, no "oops," no AI mysticism, no jargon.
- Motion ceiling: **300ms max**, `cubic-bezier(0.2,0,0,1)` ease-out, no bounce. Chart
  draw-in ≤400ms once on mount, never per-datapoint. Everything collapses to instant under
  `prefers-reduced-motion` (already global in `globals.css` + `MotionConfig` in
  `providers.tsx` — new components must not fight this, e.g. no inline animation that
  bypasses the CSS media query).
- **Accent ≤10% of any screen.** Focus Indigo (`--accent`, `#4C5FD5` light / `#7B8CFF`
  dark) is for interactive elements only: links, primary buttons, focus rings, the
  active-nav text. Never a decorative background or a chart series color unless that
  series is the one interactive/highlighted thing.
- **Verdict color is always paired with the verdict word** — never color alone. Charts
  use verdict colors only where the data literally encodes Clear/Doubtful/Suspect (the
  band-mix chart); the trend line and neutral bars use neutral/text-secondary + accent
  highlight, per §6 "Charts & data visualization."
  the accent should be used sparingly - highlight, focus, primary button, links etc,
- Tabular numerals on every numeric value (`font-feature-settings: "tnum" 1` — already
  global via `globals.css`'s `cv11`/body font-feature-settings and Tailwind's
  `tabular-nums` utility; use `tabular-nums` explicitly on any new numeric span).
- WCAG AA contrast in both themes; full keyboard nav; visible 2px focus ring, 2px offset,
  using the `--ring`/`--accent` token (not a browser default); interactive targets
  ≥44×44px; `aria-live="polite"` where a live-updating verdict/number appears.
- Icons: Lucide only, 20px default (16px dense), 1.5px stroke, `--text-secondary`. Never
  filled, never emoji, never decorative-only without `aria-hidden`.

### SaaS hygiene (owner-mandated — enforce in EVERY task, not just the QA pass)

- **Spacing:** one consistent scale (4/8/12/16/24/32/48/64 per BRAND.md §"Spacing & layout
  rules" — no arbitrary values), aligned grids, **equal card heights within a row**,
  uniform card padding, consistent section gaps (32px vertical between sections, 16px
  intra-card per BRAND.md shell rules).
- **Numbers:** thousands separators (`2,113` not `2113`), consistent decimals + units per
  metric (e.g. always 1 decimal on `avg_score`, always whole-number counts), tabular
  numerals, sensible rounding (no false precision — never show `62.3333%`), deltas always
  signed and worded ("+3.2 pts vs previous period", never a bare colored triangle).
- **Organization:** clear hierarchy, one job per widget, scannable at a glance,
  sentence-case labels everywhere.
- **Alignment/polish:** chart baselines and card tops aligned across a row, legends
  consistently placed (bottom, same position across charts), honest
  loading→empty→error parity in both themes, real hover/focus states (not just
  `cursor: pointer`).
- **Restraint:** accent ≤10%, no decorative clutter, calm density (Stripe/Linear feel) —
  no gradients-for-mood, no card-in-card, no drop shadows beyond `--shadow-1`/`-2`.

### URL-reproducibility (hard requirement)

Every piece of filter state (range preset OR custom from/to, aggregation bucket) must be
in the URL query string such that **pasting the URL into a new tab reproduces the exact
same view** — no localStorage-only state, no state that resets to default on reload.

### Testing policy

- **Task 1 installs and configures Vitest + React Testing Library** (nothing is
  installed today — verified: `package.json` has no test runner). Pure logic gets unit
  tests: insight fire/no-fire at exact thresholds, `useUrlState` serialize/parse
  round-trip, delta good/bad-for-integrity classification + small-sample guard, number
  formatting edge cases (0, negative, large numbers, rounding).
- Components (React/JSX) are **not** unit-tested in Phase A — they are verified via
  `npm run typecheck` (`tsc --noEmit`), `npm run build` (`next build`), and
  `npm run lint` (`next lint`), plus the final visual QA pass. This matches the existing
  codebase (zero component tests today) and keeps Phase A shippable without inventing a
  component-testing harness mid-plan.
- Every task lists **exact verify commands** to run from `frontend/`.

---

## Confirmed backend contract (read from live source, not assumed)

`GET /v1/analytics/summary` (`src/prooflens/api/scoring.py::analytics_summary`, backed by
`src/prooflens/api/analytics.py::aggregate_range`) — params `start_date`/`end_date` (also
accepts `from`/`to` as aliases), `bucket=daily|weekly|monthly` (default `daily`),
`group_by=none|zone|srsm|rsm|sm|branch|city` (default `none`, out of scope for Phase A
UI). Response keeps every existing key and adds:

```jsonc
{
  "total": 2113, "images_today": 12,
  "band_distribution": { "Clear": 1800, "Doubtful": 250, "Suspect": 63 },
  "suspect_pct": 3.0, "avg_score": 78.4, "avg_processing_ms": 812.4,
  "duplicates_caught": 14,
  "top_reasons": [
    { "reason_code": "screen_recapture", "reason": "Photo of another screen — screen edge and glare detected.",
      "short_label": "Photo of a screen", "count": 41 }
  ],
  "series": [ /* legacy per-day, unchanged shape: date/count/clear/doubtful/suspect/avg_score */ ],
  "buckets": [
    { "bucket_label": "Jul 3", "start": "2026-07-03", "end": "2026-07-03",
      "clear": 60, "doubtful": 8, "suspect": 2, "total": 70, "avg_score": 79.1,
      "incomplete": false }
  ],
  "incomplete": false,
  "previous": { "clear": 1500, "doubtful": 210, "suspect": 55, "total": 1765, "avg_score": 76.2 },
  "period": { "from": "2026-06-08", "to": "2026-07-07" },
  "previous_period": { "from": "2026-05-09", "to": "2026-06-07" },
  "groups": []
}
```

Notes for implementers:
- `buckets[].total` — use this, not `clear+doubtful+suspect`, when both are equal (they
  should be; backend guarantees it but don't assume for `incomplete` buckets mid-count).
- `previous` has **no per-bucket breakdown**, only one aggregate object — deltas compare
  a whole-period aggregate to a whole-period aggregate, not bucket-to-bucket.
- `duplicates_caught` has no `previous.duplicates_caught` equivalent field — re-derive it:
  the backend's `duplicates_caught` is `reason_counts[recycled]` for the *current* filtered
  window only. **There is no previous-period duplicates count in the response.** Task 5
  must handle this explicitly (see the flagged risk below) — the plan computes it from
  `previous` band totals is NOT possible; instead the duplicates KPI's delta will
  say "vs previous period" using a **second lightweight fetch** of the previous period's
  `top_reasons` via the same `useAnalytics` hook keyed on the previous window, OR (cheaper,
  chosen approach) the frontend requests analytics once for the *combined* range covering
  both periods is wasteful — **decision: extend the hook to fire a second query for the
  previous-period `duplicates_caught` only when the Duplicates KPI needs it**, using the
  existing endpoint with `period.previous_period` as its own `start_date`/`end_date`. This
  is a plain second `useQuery` (same `api.analytics`), not a new endpoint — documented in
  Task 5.
- `period`/`previous_period` `.from`/`.to` are **date-only strings** (`YYYY-MM-DD`), already
  formatted for direct display via a date formatter — no time component to strip.
- `top_reasons[].short_label` is already present — use it as the primary label; keep
  `reason` (verbatim) for tooltip/full text per BRAND.md §"Voice rules" (never truncate
  the verbatim reason — the *short_label* is a distinct, backend-provided field, not a
  frontend truncation of `reason`).

---

## Task 1: Vitest + RTL setup, pure-logic scaffolding, number formatting

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Modify: `frontend/package.json` (devDependencies + `"test"` / `"test:watch"` scripts)
- Modify: `frontend/tsconfig.json` (add `"types": ["vitest/globals"]` if needed, or rely on
  explicit imports — prefer explicit imports from `"vitest"` to avoid global pollution)
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/format.test.ts`

**Details:**

Install (do not just declare in package.json — actually run the install):
```bash
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

`vitest.config.ts`:
```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
});
```

`vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

`package.json` scripts — add:
```json
"test": "vitest run",
"test:watch": "vitest"
```

`frontend/src/lib/format.ts` — pure formatting helpers used by every widget:
```ts
/** Thousands separators, no decimals: 2113 -> "2,113". */
export function formatCount(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/** Fixed 1 decimal for score-like values: 78.4 -> "78.4". Clamps -0 to 0. */
export function formatScore(n: number): string {
  const v = Math.round(n * 10) / 10;
  return (v === 0 ? 0 : v).toFixed(1);
}

/** Percentage with 1 decimal, no false precision: 3.0421 -> "3.0%". */
export function formatPct(n: number): string {
  const v = Math.round(n * 10) / 10;
  return `${(v === 0 ? 0 : v).toFixed(1)}%`;
}

/** Signed, worded delta for a count/percentage-point metric.
 *  formatSignedPct(3.2) -> "+3.2 pts", formatSignedPct(-1.1) -> "-1.1 pts" */
export function formatSignedPts(n: number): string {
  const v = Math.round(n * 10) / 10;
  const sign = v > 0 ? "+" : v < 0 ? "" : "±"; // toFixed keeps the "-" for negatives
  return `${v === 0 ? "±0.0" : `${sign}${v.toFixed(1)}`} pts`;
}

/** Signed relative percentage change: formatSignedRelPct(23.4) -> "+23.4%" */
export function formatSignedRelPct(n: number): string {
  const v = Math.round(n * 10) / 10;
  if (v === 0) return "±0.0%";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/** Short date for captions/axis ticks: "2026-07-08" -> "Jul 8". */
export function formatShortDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "Jun 8 – Jul 7" style range caption from two YYYY-MM-DD strings. */
export function formatDateRange(fromIso: string, toIso: string): string {
  return `${formatShortDate(fromIso)}–${formatShortDate(toIso)}`;
}
```

`frontend/src/lib/format.test.ts` — cover: `formatCount` (0, 1000, 2113, 1000000),
`formatScore` (0, 78.44 rounds to 78.4, 78.45 rounds to 78.5 or 78.4 — assert the actual
banker's-rounding-free behavior of `toFixed`, don't assume), `formatPct` (0, 100, 3.0421),
`formatSignedPts` (0 → "±0.0 pts", 3.2 → "+3.2 pts", -1.1 → "-1.1 pts"), `formatSignedRelPct`
(same shape), `formatShortDate` (leap-year Feb 29, Dec 31→Jan 1 boundary), `formatDateRange`
(cross-month, e.g. "Jun 8–Jul 7").

- [ ] Step 1: Install dependencies (command above).
- [ ] Step 2: Write `vitest.config.ts`, `vitest.setup.ts`, add scripts to `package.json`.
- [ ] Step 3: Write `frontend/src/lib/format.ts` per the spec above.
- [ ] Step 4: Write `frontend/src/lib/format.test.ts` with the cases listed above (write
      tests FIRST against the not-yet-existing exact rounding behavior is not required
      here since these are pure new functions — write test+impl together, then run).
- [ ] Step 5: Verify.

**Verify:**
```bash
cd frontend
npm run test -- --run src/lib/format.test.ts
npm run typecheck
```
Expected: all format tests pass; `tsc --noEmit` clean.

- [ ] Step 6: Commit.

---

## Task 2: Brand-token fixes (`--accent`, real Suspect red) + Tailwind wiring

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/tailwind.config.ts`

**Why now:** every later widget (buttons in the filter bar, focus rings, the one accent
chart highlight) depends on `--accent` existing. Doing this first avoids rework.

**Details:**

In `tokens.css` `:root`, add the Focus Indigo accent and correct light-mode Suspect to the
BRAND.md §6 target (`#DC2F45`, currently `#C8102E` — same as tenant crimson, which
BRAND.md explicitly says must never collide):
```css
--accent: #4c5fd5;
--accent-hover: #3d4ec2;
--verdict-suspect: #dc2f45;         /* was #c8102e — no longer collides with tenant crimson */
--verdict-suspect-bg: #fbe9ea;      /* re-derive a soft tint of #dc2f45; verify AA on --verdict-suspect-fg */
--verdict-suspect-fg: #a3132a;      /* verify WCAG AA against --verdict-suspect-bg in both themes */
```
In `.dark`, confirm/add:
```css
--accent: #7b8cff;
--accent-hover: #93a1ff;
/* --verdict-suspect dark is already #f0596e per §6 table — no change needed */
```
Do **not** touch `--brand-crimson` (tenant chip only, per §9) — it stays as-is; this task
only adds `--accent` and corrects `--verdict-suspect` (light).

In `tailwind.config.ts`, add to `theme.extend.colors`:
```ts
accent: { DEFAULT: "var(--accent)", hover: "var(--accent-hover)" },
```

Update `globals.css`'s `:focus-visible` rule to use the accent token per BRAND.md
Accessibility rules ("target migration moves focus rings to `--accent`"):
```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
```

- [ ] Step 1: Edit `tokens.css` (`:root` and `.dark`) per above.
- [ ] Step 2: Edit `tailwind.config.ts` to expose `accent`/`accent-hover`.
- [ ] Step 3: Edit `globals.css`'s `:focus-visible` to use `--accent`.
- [ ] Step 4: Grep for any hardcoded `#c8102e`/`#C8102E` use as "Suspect" (not tenant chip)
      to confirm nothing else needs updating in this task's scope:
      `grep -rn "c8102e" frontend/src --include=*.tsx -i` — expect only
      `AbsliMasthead.tsx`/`TenantLogo.tsx`/tenant-chip-related files; anything else
      referencing Suspect verbatim should already resolve via the `verdict-suspect` token,
      not a literal hex.

**Verify:**
```bash
cd frontend
npm run typecheck
npm run build
```
Expected: builds clean; grep shows only tenant-branding files using the literal crimson hex.

- [ ] Step 5: Commit.

---

## Task 3: Data layer — extend types, `api.analytics(params)`, `useAnalytics`, `useUrlState`

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/src/lib/api/hooks.ts`
- Create: `frontend/src/lib/useUrlState.ts`
- Create: `frontend/src/lib/useUrlState.test.ts`

**Details:**

`types.ts` — extend additively (do not remove existing fields; `series`/`band_distribution`
etc. are still used elsewhere, e.g. Dashboard):
```ts
export interface TopReason {
  reason_code: string;
  reason: string;
  short_label: string;   // NEW — always present now
  count: number;
}

export interface AnalyticsBucket {
  bucket_label: string;
  start: string; // YYYY-MM-DD
  end: string;   // YYYY-MM-DD
  clear: number;
  doubtful: number;
  suspect: number;
  total: number;
  avg_score: number;
  incomplete: boolean;
}

export interface PeriodAggregate {
  clear: number;
  doubtful: number;
  suspect: number;
  total: number;
  avg_score: number;
}

export interface PeriodBounds {
  from: string; // YYYY-MM-DD
  to: string;   // YYYY-MM-DD
}

export interface AnalyticsGroup {
  node: string;
  total: number;
  clear: number;
  doubtful: number;
  suspect: number;
  avg_score: number;
  suspect_rate: number;
  share: number;
}

export interface AnalyticsSummary {
  total: number;
  images_today: number;
  band_distribution: Record<Band, number>;
  suspect_pct: number;
  avg_score: number;
  avg_processing_ms: number;
  duplicates_caught: number;
  top_reasons: TopReason[];
  series: DaySeries[];        // legacy, unchanged — still used by Dashboard if applicable
  buckets: AnalyticsBucket[]; // NEW
  incomplete: boolean;        // NEW
  previous: PeriodAggregate;  // NEW
  period: PeriodBounds;       // NEW
  previous_period: PeriodBounds; // NEW
  groups: AnalyticsGroup[];   // NEW — unused by Phase A UI, present for type completeness
}

export type Bucket = "daily" | "weekly" | "monthly";
export type GroupBy = "none" | "zone" | "srsm" | "rsm" | "sm" | "branch" | "city";

export interface AnalyticsParams {
  start_date?: string; // YYYY-MM-DD
  end_date?: string;   // YYYY-MM-DD
  bucket?: Bucket;
  group_by?: GroupBy;
}
```

`client.ts` — replace the zero-arg `analytics()`:
```ts
async analytics(params?: AnalyticsParams): Promise<AnalyticsSummary> {
  const { data } = await http.get("/v1/analytics/summary", { params });
  return data;
},
```
(Import `AnalyticsParams` in the type import list at top of the file.)

`hooks.ts` — replace `useAnalytics`:
```ts
import { useDebouncedValue } from "./useDebouncedValue"; // or inline below
import type { AnalyticsParams } from "./types";

export function useAnalytics(params: AnalyticsParams = {}) {
  const debounced = useDebouncedValue(params, 300);
  return useQuery({
    queryKey: ["analytics", debounced],
    queryFn: () => api.analytics(debounced),
    // Keep the previous page's data visible while the debounced params refetch,
    // so widgets show a subtle in-place update rather than a full unmount —
    // pairs with Task 8's "skeleton only on first load" rule.
    placeholderData: (prev) => prev,
    refetchInterval: 30_000,
  });
}
```
Add a tiny colocated debounce hook (new file `frontend/src/lib/api/useDebouncedValue.ts`,
or inline in `hooks.ts` if simpler — prefer a separate file since it's reusable and
independently testable):
```ts
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
```
Note: `useQuery`'s `queryKey` must be a stable, serializable value — `debounced` (a plain
object of primitives) works fine as a React Query key.

`useUrlState.ts` — the generic URL-state hook. Keep it small and pure where possible;
separate the **pure serialize/parse logic** (unit-tested) from the **React binding**
(verified via typecheck/build only, consistent with Testing policy above):

```ts
"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** Pure: encode a partial state object into a URLSearchParams-compatible record,
 *  dropping keys whose value equals the default (keeps URLs clean). */
export function serializeState<T extends Record<string, string | undefined>>(
  state: T,
  defaults: Partial<T>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const key of Object.keys(state)) {
    const v = state[key];
    if (v === undefined || v === "") continue;
    if (defaults[key] !== undefined && v === defaults[key]) continue;
    out[key] = v;
  }
  return out;
}

/** Pure: parse a URLSearchParams into a typed state object, falling back to defaults
 *  and dropping keys not in `allowedKeys` (ignores unrelated query params). */
export function parseState<T extends Record<string, string | undefined>>(
  params: URLSearchParams,
  defaults: T,
  allowedKeys: (keyof T)[],
): T {
  const out = { ...defaults };
  for (const key of allowedKeys) {
    const raw = params.get(String(key));
    if (raw !== null && raw !== "") out[key] = raw as T[typeof key];
  }
  return out;
}

/** React binding: reads the given keys from the URL (typed via defaults), and
 *  returns [state, setState] where setState merges + replaces the URL (no history
 *  entry per keystroke — callers should debounce free-text inputs upstream). */
export function useUrlState<T extends Record<string, string | undefined>>(
  defaults: T,
  allowedKeys: (keyof T)[],
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const state = useMemo(
    () => parseState(searchParams, defaults, allowedKeys),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams.toString()],
  );

  const setState = useCallback(
    (patch: Partial<T>) => {
      const next = { ...state, ...patch };
      const serialized = serializeState(next, defaults);
      const qs = new URLSearchParams(serialized).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [state, defaults, pathname, router],
  );

  return [state, setState] as const;
}
```

`useUrlState.test.ts` — unit test **only** `serializeState` and `parseState` (pure, no
React/DOM needed): round-trip a full state object through serialize→URLSearchParams
string→parse and assert equality; assert default-valued keys are omitted from
`serializeState`'s output (keeps URL clean); assert `parseState` ignores unknown query
keys and fills in defaults for missing ones; assert empty-string values are treated as
absent.

- [ ] Step 1: Extend `types.ts` per above.
- [ ] Step 2: Update `client.ts`'s `analytics()` to accept `AnalyticsParams`.
- [ ] Step 3: Add `useDebouncedValue.ts`; update `useAnalytics` in `hooks.ts`.
- [ ] Step 4: Write `useUrlState.ts` (serialize/parse pure functions + the hook).
- [ ] Step 5: Write `useUrlState.test.ts` covering the round-trip cases above.
- [ ] Step 6: Grep for existing zero-arg `useAnalytics()` call sites and update them to
      pass `{}` explicitly or rely on the default parameter (should be source-compatible
      since `params` now defaults to `{}` — confirm no caller destructures a shape that
      changed):
      `grep -rn "useAnalytics(" frontend/src`

**Verify:**
```bash
cd frontend
npm run test -- --run src/lib/useUrlState.test.ts
npm run typecheck
```
Expected: round-trip tests pass; no type errors from the `AnalyticsSummary` extension
(the old `analytics/page.tsx` will still compile against the additive type — it only
reads fields that still exist).

- [ ] Step 7: Commit.

---

## Task 4: MetricCard brand fix + `useAnalyticsFilters` + `FilterBar` widget

**Files:**
- Modify: `frontend/src/components/ui/MetricCard.tsx`
- Create: `frontend/src/lib/analytics/useAnalyticsFilters.ts`
- Create: `frontend/src/lib/analytics/dateRanges.ts`
- Create: `frontend/src/lib/analytics/dateRanges.test.ts`
- Create: `frontend/src/components/analytics/FilterBar.tsx`

**Details:**

**MetricCard fix** (BRAND.md §11/§7 violation: uppercase label, decorative icon not in
the component's brand-approved list of `MetricCard` fields — BRAND.md's Instructions
section defines `MetricCard` without an icon prop, and §7 says labels are sentence case,
never uppercase):
```tsx
// Before: <span className="text-caption font-medium uppercase tracking-wide text-text-muted">
// After:
<span className="text-caption font-medium text-text-muted">{label}</span>
```
Remove the `icon`/`Icon` prop entirely (and its rendering) — MetricCard becomes
label/value/suffix/sub/accent only. This is a breaking prop change; Task 9 (existing
Dashboard/Analytics callers) must be swept for `icon={...}` usage.

`dateRanges.ts` — pure preset resolution (today is a parameter so it's testable without
mocking the clock):
```ts
export type RangePreset = "7d" | "30d" | "90d" | "month" | "custom";

export interface ResolvedRange {
  start_date: string; // YYYY-MM-DD
  end_date: string;   // YYYY-MM-DD
}

/** Resolve a preset (or explicit custom bounds) to concrete YYYY-MM-DD bounds,
 *  inclusive, ending "today" (UTC) unless custom bounds are given. */
export function resolvePreset(
  preset: RangePreset,
  today: Date,
  custom?: { start_date?: string; end_date?: string },
): ResolvedRange {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const t = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  if (preset === "custom") {
    return {
      start_date: custom?.start_date ?? iso(t),
      end_date: custom?.end_date ?? iso(t),
    };
  }
  if (preset === "month") {
    const start = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), 1));
    return { start_date: iso(start), end_date: iso(t) };
  }
  const days = preset === "7d" ? 6 : preset === "30d" ? 29 : 89; // inclusive span
  const start = new Date(t);
  start.setUTCDate(start.getUTCDate() - days);
  return { start_date: iso(start), end_date: iso(t) };
}

export const RANGE_PRESET_LABELS: Record<RangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  month: "This month",
  custom: "Custom range",
};

export const DEFAULT_PRESET: RangePreset = "30d";
export const DEFAULT_BUCKET = "daily" as const;
```

`dateRanges.test.ts` — fix `today` to a known UTC date (e.g. `new Date("2026-07-08T00:00:00Z")`)
and assert: `"7d"` → 7-day span ending today; `"30d"` → 30-day span ending today; `"90d"`
→ 90-day span; `"month"` → start on the 1st of the current month through today (including
the edge case where today IS the 1st, span = 1 day); `"custom"` passes through given
bounds unchanged, and falls back to today when bounds are omitted.

`useAnalyticsFilters.ts` — composes `useUrlState` (Task 3) + `resolvePreset`:
```ts
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
};
const ALLOWED_KEYS = ["range", "bucket", "from", "to"] as const;

export function useAnalyticsFilters() {
  const [urlState, setUrlState] = useUrlState(DEFAULTS, [...ALLOWED_KEYS]);

  const preset = (urlState.range as RangePreset) || DEFAULT_PRESET;
  const bucket = (urlState.bucket as Bucket) || DEFAULT_BUCKET;

  const resolved = useMemo(
    () => resolvePreset(preset, new Date(), { start_date: urlState.from, end_date: urlState.to }),
    [preset, urlState.from, urlState.to],
  );

  const params: AnalyticsParams = {
    start_date: resolved.start_date,
    end_date: resolved.end_date,
    bucket,
    group_by: "none", // Phase A never sets this to anything else
  };

  function setPreset(next: RangePreset) {
    setUrlState({ range: next, from: undefined, to: undefined });
  }
  function setCustomRange(from: string, to: string) {
    setUrlState({ range: "custom", from, to });
  }
  function setBucket(next: Bucket) {
    setUrlState({ bucket: next });
  }

  return { preset, bucket, resolved, params, setPreset, setCustomRange, setBucket };
}
```

`FilterBar.tsx` — the widget rendered directly under the page H1. Reuses `Button` for
the segmented bucket control and a native `<select>`/popover-free date pickers for
simplicity (no new date-picker dependency — use two `<input type="date">` fields shown
only when `preset === "custom"`, styled to match the existing `history/page.tsx` search
input pattern: `h-9 rounded-md border border-border bg-surface px-3 text-body-sm`).
Caption line uses `formatDateRange` (Task 1) fed by `period`/`previous_period` from the
analytics response — **not** recomputed client-side from the preset, since the backend's
resolved period is the source of truth (it may differ subtly, e.g. `"month"` semantics).
Render:
```
[Last 7d] [Last 30d] [Last 90d] [This month] [Custom ▾]      [Daily] [Weekly] [Monthly]
Jun 8–Jul 7 · compared with May 9–Jun 7
```
- Segmented controls use `bg-surface-2 text-text` for the selected pill (same pattern as
  `history/page.tsx`'s band filter, lines 95-111) and `--accent` only for the focus ring,
  not the resting selected state (selected = neutral fill, per accent ≤10% rule).
- All buttons/inputs are ≥44px tall on touch (`min-h-[44px] sm:min-h-0` pattern already
  used in `Button.tsx`) — for the segmented controls reuse that class approach.
- The whole bar wraps (`flex flex-wrap gap-3`) at ≤1024px per Task 10.

- [ ] Step 1: Fix `MetricCard.tsx` (remove uppercase, remove icon prop/rendering).
- [ ] Step 2: Write `dateRanges.ts` + `dateRanges.test.ts`.
- [ ] Step 3: Write `useAnalyticsFilters.ts`.
- [ ] Step 4: Write `FilterBar.tsx`.
- [ ] Step 5: Grep every existing `<MetricCard` usage for the removed `icon` prop and
      strip it (do NOT wire the new Analytics page yet — that's Task 9 — but any
      **other** page using MetricCard with an icon must not break the build):
      `grep -rn "MetricCard" frontend/src --include=*.tsx -l`

**Verify:**
```bash
cd frontend
npm run test -- --run src/lib/analytics/dateRanges.test.ts
npm run typecheck
npm run build
```
Expected: date-range tests pass; build succeeds (confirms no other page still passes
`icon=` to `MetricCard`, which would now be a type error under strict mode).

- [ ] Step 6: Commit.

---

## Task 5: Insight + delta pure logic (`insights.ts`, `deltas.ts`)

**Files:**
- Create: `frontend/src/lib/analytics/deltas.ts`
- Create: `frontend/src/lib/analytics/deltas.test.ts`
- Create: `frontend/src/lib/analytics/insights.ts`
- Create: `frontend/src/lib/analytics/insights.test.ts`

**Details:**

`deltas.ts` — the shared "worded delta, colored by good/bad-for-integrity, small-sample
guarded" primitive used by every KPI card:
```ts
export type DeltaDirection = "up" | "down" | "flat";
export type DeltaSentiment = "good" | "bad" | "neutral"; // for-integrity, not for-vanity

export interface Delta {
  direction: DeltaDirection;
  sentiment: DeltaSentiment;
  /** null when the previous-period sample is too small to trust (see MIN_PREV_N). */
  words: string | null;
  insufficientHistory: boolean;
}

export const MIN_PREV_N = 20;

/**
 * higherIsBad: true for suspect-rate-like metrics (a rise is bad for integrity);
 * false for avg-score-like metrics (a rise is good). Falling suspect rate = green;
 * rising suspect rate = red — the metric's OWN semantics decide color, not the sign.
 */
export function computeDelta(
  current: number,
  previous: number,
  prevN: number,
  opts: { higherIsBad: boolean; unit: "pts" | "pct" | "count"; minPrevN?: number },
): Delta {
  const minN = opts.minPrevN ?? MIN_PREV_N;
  if (prevN < minN) {
    return { direction: "flat", sentiment: "neutral", words: null, insufficientHistory: true };
  }
  const diff = current - previous;
  const direction: DeltaDirection = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  const rising = diff > 0;
  const sentiment: DeltaSentiment =
    direction === "flat" ? "neutral" : rising === opts.higherIsBad ? "bad" : "good";
  const worded =
    opts.unit === "count"
      ? `${diff > 0 ? "+" : ""}${Math.round(diff)} vs previous period`
      : opts.unit === "pts"
        ? `${formatSignedPts(diff)} vs previous period`
        : `${formatSignedRelPct(diff)} vs previous period`;
  return { direction, sentiment, words: worded, insufficientHistory: false };
}

/** Relative change for the ≥20% relative threshold rule used by insights.ts. */
export function relativeChangePct(current: number, previous: number): number {
  if (previous === 0) return current === 0 ? 0 : Infinity;
  return ((current - previous) / previous) * 100;
}
```
(Import `formatSignedPts`/`formatSignedRelPct` from `@/lib/format`, Task 1.)

`deltas.test.ts` — cover: `prevN < 20` → `insufficientHistory: true`, `words: null`,
regardless of the diff; suspect-rate rising (`higherIsBad: true`) with `prevN >= 20` →
`sentiment: "bad"`; suspect-rate falling → `sentiment: "good"`; avg-score rising
(`higherIsBad: false`) → `"good"`; avg-score falling → `"bad"`; zero diff → `"neutral"`,
`direction: "flat"`; `relativeChangePct` with `previous = 0` and `current > 0` → `Infinity`;
`previous = 0, current = 0` → `0`; a normal case (50 → 65) → `30` (%).

`insights.ts` — the 3–5 computed bullets. Pure function taking the already-fetched
`AnalyticsSummary` (plus `Band`/`TopReason` types) and returning an ordered, capped list:
```ts
import type { AnalyticsSummary } from "@/lib/api/types";
import { relativeChangePct } from "./deltas";

export type InsightSeverity = "info" | "warn" | "high";

export interface Insight {
  id: string;
  text: string;          // full sentence, ready to render — plain language, no jargon
  severity: InsightSeverity;
}

const MAX_INSIGHTS = 5;
const MIN_INSIGHTS_FALLBACK = 0;

/** Rule 1: suspect-rate delta >= 20% relative AND >= 10 absolute suspects in current period. */
function suspectRateShift(a: AnalyticsSummary): Insight | null {
  const cur = a.band_distribution.Suspect;
  const prev = a.previous.suspect;
  if (cur < 10) return null;
  const rel = relativeChangePct(cur, prev);
  if (!Number.isFinite(rel) || Math.abs(rel) < 20) return null;
  const rising = rel > 0;
  return {
    id: "suspect-rate-shift",
    severity: rising ? "high" : "info",
    text: rising
      ? `Suspect volume rose ${Math.round(rel)}% vs the previous period (${cur} vs ${prev}).`
      : `Suspect volume fell ${Math.round(Math.abs(rel))}% vs the previous period (${cur} vs ${prev}).`,
  };
}

/** Rule 2: a single top reason accounts for >= 30% of all flagged (non-clear) verdicts. */
function dominantReason(a: AnalyticsSummary): Insight | null {
  const flagged = a.top_reasons.filter((r) => r.reason_code !== "clear");
  const totalFlagged = flagged.reduce((s, r) => s + r.count, 0);
  if (totalFlagged === 0) return null;
  const top = flagged[0];
  const share = (top.count / totalFlagged) * 100;
  if (share < 30) return null;
  return {
    id: "dominant-reason",
    severity: "warn",
    text: `"${top.short_label}" accounts for ${Math.round(share)}% of flagged verdicts (${top.count} of ${totalFlagged}).`,
  };
}

/** Rule 3: avg-score delta >= 5 pts AND previous-period n >= 30. */
function avgScoreShift(a: AnalyticsSummary): Insight | null {
  if (a.previous.total < 30) return null;
  const diff = a.avg_score - a.previous.avg_score;
  if (Math.abs(diff) < 5) return null;
  const rising = diff > 0;
  return {
    id: "avg-score-shift",
    severity: rising ? "info" : "warn",
    text: rising
      ? `Average score improved ${diff.toFixed(1)} pts vs the previous period.`
      : `Average score dropped ${Math.abs(diff).toFixed(1)} pts vs the previous period.`,
  };
}

/** Rule 4: duplicates_caught relative delta >= 20% (needs previous.duplicates_caught —
 *  see Task 6's note: this is passed in explicitly since it isn't on `previous`). */
function duplicatesShift(current: number, previous: number): Insight | null {
  if (current < 5 && previous < 5) return null; // both negligible, not worth a bullet
  const rel = relativeChangePct(current, previous);
  if (!Number.isFinite(rel) || Math.abs(rel) < 20) return null;
  const rising = rel > 0;
  return {
    id: "duplicates-shift",
    severity: rising ? "warn" : "info",
    text: rising
      ? `Duplicate captures rose ${Math.round(rel)}% vs the previous period (${current} vs ${previous}).`
      : `Duplicate captures fell ${Math.round(Math.abs(rel))}% vs the previous period (${current} vs ${previous}).`,
  };
}

export function computeInsights(
  a: AnalyticsSummary,
  prevDuplicatesCaught: number | null,
): Insight[] {
  const candidates = [
    suspectRateShift(a),
    dominantReason(a),
    avgScoreShift(a),
    prevDuplicatesCaught == null
      ? null
      : duplicatesShift(a.duplicates_caught, prevDuplicatesCaught),
  ].filter((x): x is Insight => x !== null);

  // Stable order: high severity first, then warn, then info; cap at 5.
  const order: Record<InsightSeverity, number> = { high: 0, warn: 1, info: 2 };
  candidates.sort((x, y) => order[x.severity] - order[y.severity]);
  return candidates.slice(0, MAX_INSIGHTS);
}

export const NO_SHIFTS_FALLBACK = "No significant shifts this period.";
```

Note the explicit `prevDuplicatesCaught: number | null` parameter — this is the value
resolved by Task 6's second lightweight query (see the flagged risk in the contract
section above). When `null` (still loading, or the second query failed), the duplicates
insight rule is simply skipped, never fabricated.

`insights.test.ts` — for EACH rule, test both the fire and no-fire boundary explicitly:
- `suspectRateShift`: `cur=9, prev=5` → null (below the `cur>=10` absolute gate) even
  though relative change is huge; `cur=10, prev=8` → relative change 25% ≥ 20% → fires;
  `cur=10, prev=9` → relative change ~11% < 20% → null; `prev=0, cur=10` → `Infinity`
  relative → fires (treat "went from zero" as a real shift).
- `dominantReason`: top share exactly 30% → fires (`>=`, not `>`); top share 29.9% → null;
  empty `top_reasons` → null (no divide-by-zero).
- `avgScoreShift`: `previous.total=29` → null regardless of diff (small-sample guard);
  `previous.total=30, diff=5.0` → fires (`>=`); `diff=4.9` → null.
- `duplicatesShift`: both under 5 → null even with 100% relative change; `current=5,
  previous=4` → 25% relative ≥ 20% → fires; `current=6, previous=5` → 20% → fires
  (boundary inclusive); `current=5, previous=4.9...` use integers only, no float edge.
- `computeInsights`: 0 firing rules → returns `[]` (caller renders `NO_SHIFTS_FALLBACK`,
  tested at the component-usage level, not here); all 4 firing → capped/sorted so `high`
  precedes `warn` precedes `info`; exactly `MAX_INSIGHTS` respected when more rules exist
  in the future (test guards the cap even though only 4 rules exist today).

- [ ] Step 1: Write `deltas.ts` + `deltas.test.ts`.
- [ ] Step 2: Write `insights.ts` + `insights.test.ts` per the fire/no-fire matrix above.
- [ ] Step 3: Run and fix until green.

**Verify:**
```bash
cd frontend
npm run test -- --run src/lib/analytics/deltas.test.ts src/lib/analytics/insights.test.ts
npm run typecheck
```
Expected: all listed boundary cases pass.

- [ ] Step 4: Commit.

---

## Task 6: `InsightsPanel` + `KpiRow` widgets (composition, not new logic)

**Files:**
- Create: `frontend/src/components/analytics/InsightsPanel.tsx`
- Create: `frontend/src/components/analytics/KpiRow.tsx`

**Details:**

`InsightsPanel.tsx` — renders `computeInsights` output (Task 5) as a bulleted list, each
with a small severity dot (verdict-colored: `high`→`--verdict-suspect`, `warn`→
`--verdict-doubtful`, `info`→`--text-muted`, NOT `--verdict-clear` since "info" isn't a
verdict — reuse the dot pattern but with a neutral gray for info, only warn/high borrow
verdict hues since they genuinely mean "worth attention"/"needs review"). Never labeled
"AI" or "AI-generated" anywhere in copy per BRAND.md §14. Placed as the **first block**
on the page, above the KPI row, per the task brief's ordering.
```tsx
"use client";
import type { AnalyticsSummary } from "@/lib/api/types";
import { computeInsights, NO_SHIFTS_FALLBACK, type InsightSeverity } from "@/lib/analytics/insights";
import { Card, CardHeader } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

const DOT: Record<InsightSeverity, string> = {
  high: "bg-verdict-suspect",
  warn: "bg-verdict-doubtful",
  info: "bg-text-muted",
};

export function InsightsPanel({
  analytics,
  prevDuplicatesCaught,
}: {
  analytics: AnalyticsSummary;
  prevDuplicatesCaught: number | null;
}) {
  const insights = computeInsights(analytics, prevDuplicatesCaught);
  return (
    <Card>
      <CardHeader title="What changed" subtitle="Computed from this period vs the previous one." />
      <div className="p-4">
        {insights.length === 0 ? (
          <p className="text-body-sm text-text-secondary">{NO_SHIFTS_FALLBACK}</p>
        ) : (
          <ul className="space-y-2.5">
            {insights.map((i) => (
              <li key={i.id} className="flex items-start gap-2.5 text-body-sm text-text">
                <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", DOT[i.severity])} aria-hidden />
                <span>{i.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
```
Title "What changed" (sentence case, no "AI Insights" / "Smart Insights" branding — the
brief is explicit that this must never be labeled AI).

`KpiRow.tsx` — 4 `MetricCard`s in an equal-height grid, each with a worded delta from
`computeDelta` (Task 5):
```tsx
"use client";
import { MetricCard } from "@/components/ui/MetricCard";
import { formatCount, formatPct, formatScore } from "@/lib/format";
import { computeDelta } from "@/lib/analytics/deltas";
import type { AnalyticsSummary } from "@/lib/api/types";

export function KpiRow({
  analytics,
  prevDuplicatesCaught,
}: {
  analytics: AnalyticsSummary;
  prevDuplicatesCaught: number | null;
}) {
  const a = analytics;
  const totalDelta = computeDelta(a.total, a.previous.total, a.previous.total, {
    higherIsBad: false,
    unit: "count",
  });
  const suspectRateDelta = computeDelta(a.suspect_pct, ratePct(a.previous), a.previous.total, {
    higherIsBad: true,
    unit: "pts",
  });
  const avgScoreDelta = computeDelta(a.avg_score, a.previous.avg_score, a.previous.total, {
    higherIsBad: false,
    unit: "pts",
  });
  const dupDelta =
    prevDuplicatesCaught == null
      ? null
      : computeDelta(a.duplicates_caught, prevDuplicatesCaught, a.previous.total, {
          higherIsBad: true,
          unit: "count",
        });

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <MetricCard label="Total scored" value={formatCount(a.total)} sub={deltaSub(totalDelta)} />
      <MetricCard label="Suspect rate" value={formatPct(a.suspect_pct)} sub={deltaSub(suspectRateDelta)} accent />
      <MetricCard label="Avg score" value={formatScore(a.avg_score)} suffix="/ 100" sub={deltaSub(avgScoreDelta)} />
      <MetricCard
        label="Duplicates caught"
        value={formatCount(a.duplicates_caught)}
        sub={dupDelta ? deltaSub(dupDelta) : "Loading previous period…"}
      />
    </div>
  );
}

function ratePct(p: { suspect: number; total: number }): number {
  return p.total ? (p.suspect / p.total) * 100 : 0;
}

function deltaSub(d: ReturnType<typeof computeDelta>): string {
  if (d.insufficientHistory) return "Insufficient history";
  return d.words ?? "No change vs previous period";
}
```
Delta text color: since `MetricCard`'s `sub` renders in `--text-muted` today (neutral),
and BRAND.md forbids color-alone meaning anyway, the delta **word choice already carries
the sentiment** ("rose"/"fell", "+"/"-") — no additional color coding is required on the
`sub` line to stay compliant, but for visual scanability this task adds a small optional
color affordance: extend `MetricCard`'s `sub` rendering (in this same task, alongside
Task 4's icon-removal edit) to accept a `subTone?: "good" | "bad" | "neutral"` prop that
maps to `text-verdict-clear-fg` / `text-verdict-suspect-fg` / `text-text-muted`
respectively — still always paired with the worded text, never color alone. `KpiRow`
passes `subTone={d.sentiment}` mapped (`"good"→"good"`, `"bad"→"bad"`,
`"neutral"→"neutral"`).

Equal height: `grid grid-cols-2 gap-4 lg:grid-cols-4` with each `MetricCard` already
using `flex flex-col gap-2 p-4` (uniform internal structure) — CSS grid rows naturally
equalize height across a row as long as no card has a variable-height element (the
`sub` line, worst case, wraps to 2 lines — verified in Task 11's QA pass across all 4
cards to confirm none looks visually shorter/taller).

- [ ] Step 1: Extend `MetricCard.tsx` with the optional `subTone` prop (small addition to
      the same file touched in Task 4 — confirm Task 4 is complete first).
- [ ] Step 2: Write `InsightsPanel.tsx`.
- [ ] Step 3: Write `KpiRow.tsx`.
- [ ] Step 4: `prevDuplicatesCaught` sourcing: document (code comment, not implementation
      yet — the actual fetch is wired in Task 9) that the page-level component will run a
      second `useAnalytics({ start_date: previous_period.from, end_date: previous_period.to,
      bucket: "daily" })` query and pass its `.data?.duplicates_caught ?? null` down to both
      `InsightsPanel` and `KpiRow`.

**Verify:**
```bash
cd frontend
npm run typecheck
```
Expected: clean (no runtime/page wiring yet, so no build/lint needed until Task 9
assembles the full page — but typecheck must pass in isolation for these two new files
plus the `MetricCard` prop addition).

- [ ] Step 5: Commit.

---

## Task 7: `CaptureRiskTrend` (line chart) + `BandMixChart` (100% stacked)

**Files:**
- Create: `frontend/src/components/analytics/CaptureRiskTrend.tsx`
- Create: `frontend/src/components/analytics/BandMixChart.tsx`

**Details:**

Both consume `analytics.buckets` (`AnalyticsBucket[]`, Task 3) — NOT the legacy `series`
(day-only). Both charts are 280px tall (`ChartCard`'s `height` prop, default was 260 —
override to `280` per the brief), reuse `ChartCard` for the title/subtitle/border chrome.

`CaptureRiskTrend.tsx` — suspect rate per bucket, line chart, incomplete bucket visually
distinct (dashed segment or a lighter/hollow point — recharts supports per-point styling
via a custom dot renderer keyed on `payload.incomplete`), tooltip shows current AND
previous period's equivalent value where available. Since `previous` has no per-bucket
breakdown (confirmed in the contract section), the tooltip's "previous" reference is the
**previous period's overall suspect rate** (`a.previous.suspect / a.previous.total`), shown
as a static reference — not a second line series. Render this as a subtle horizontal
reference line (recharts `ReferenceLine`, `strokeDasharray`, `--text-muted`, NOT
`--accent` since it's not the primary interactive series) labeled "Previous period avg."

```tsx
"use client";
import { Line, LineChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import type { AnalyticsBucket, PeriodAggregate } from "@/lib/api/types";
import { formatPct } from "@/lib/format";

export function CaptureRiskTrend({
  buckets,
  previous,
}: {
  buckets: AnalyticsBucket[];
  previous: PeriodAggregate;
}) {
  const data = buckets.map((b) => ({
    label: b.bucket_label,
    rate: b.total ? (b.suspect / b.total) * 100 : 0,
    incomplete: b.incomplete,
    total: b.total,
  }));
  const prevRate = previous.total ? (previous.suspect / previous.total) * 100 : 0;

  return (
    <ChartCard title="Capture-risk trend" subtitle="Suspect rate per period, vs the previous period's average." height={280}>
      {data.length < 2 ? (
        <p className="grid h-full place-items-center text-body-sm text-text-muted">
          Not enough buckets yet to chart a trend.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
            <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
            <ReferenceLine y={prevRate} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: "Previous period avg", position: "insideTopRight", fontSize: 11, fill: "var(--text-muted)" }} />
            <Tooltip content={<TrendTooltip prevRate={prevRate} />} />
            <Line
              type="monotone"
              dataKey="rate"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={(props) => <TrendDot {...props} />}
              isAnimationActive
              animationDuration={350}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}
```
(`TrendDot` and `TrendTooltip` are small local components: `TrendDot` renders a hollow
circle with `strokeDasharray`-like styling — actually for a *point*, render it as an open
circle `fill="var(--surface)" stroke="var(--accent)"` vs a filled circle for complete
buckets, to visually mark "incomplete, don't over-read this point" — plus the tooltip
explicitly states "(in progress)" for that bucket. `TrendTooltip` shows: bucket label,
current rate (`formatPct`), "vs previous period: {formatPct(prevRate)}" line, and total
count for context.)

`animationDuration={350}` respects the ≤400ms chart draw-in ceiling (BRAND.md §11);
`isAnimationActive` still respects `prefers-reduced-motion` globally since recharts reads
no user preference itself — confirm in Task 11's QA pass that reduced-motion actually
suppresses this (recharts animations use `requestAnimationFrame`, not CSS, so the global
`transition-duration`/`animation-duration` override in `globals.css` does **not** catch
them — this is a known recharts gap). **Mitigation required in this task:** read
`window.matchMedia("(prefers-reduced-motion: reduce)").matches` (client-only, via a tiny
`usePrefersReducedMotion()` hook) and set `isAnimationActive={!prefersReduced}` explicitly
on both charts in this task AND the band-mix chart below — this is the one place recharts
needs manual reduced-motion wiring since the CSS-only global rule can't reach it.

`BandMixChart.tsx` — 100% stacked verdict-colored bars, one bar per bucket, **only
buckets with `total > 0` rendered** (per the brief: "only buckets with data"); if fewer
than 3 such buckets remain, render a caption instead of the chart ("Not enough scored
volume yet to show a band mix — check back once more buckets have data.") reusing the
`ChartCard`'s body slot. Percentages, not raw counts, drive bar height (100% stacked);
raw counts appear in the tooltip. Legend at the bottom, consistent with
`CaptureRiskTrend`'s omission of a legend (trend has one series, doesn't need one) —
for cross-chart consistency, BOTH charts place any legend at the bottom when present.

```tsx
"use client";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import type { AnalyticsBucket } from "@/lib/api/types";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

export function BandMixChart({ buckets }: { buckets: AnalyticsBucket[] }) {
  const withData = buckets.filter((b) => b.total > 0);
  const reducedMotion = usePrefersReducedMotion();

  if (withData.length < 3) {
    return (
      <ChartCard title="Band mix" subtitle="Clear / Doubtful / Suspect share per period." height={280}>
        <p className="grid h-full place-items-center text-body-sm text-text-muted">
          Not enough scored volume yet to show a band mix — check back once more periods have data.
        </p>
      </ChartCard>
    );
  }

  const data = withData.map((b) => {
    const sum = b.total || 1;
    return {
      label: b.bucket_label,
      Clear: (b.clear / sum) * 100,
      Doubtful: (b.doubtful / sum) * 100,
      Suspect: (b.suspect / sum) * 100,
      rawClear: b.clear,
      rawDoubtful: b.doubtful,
      rawSuspect: b.suspect,
      total: b.total,
    };
  });

  return (
    <ChartCard title="Band mix" subtitle="Clear / Doubtful / Suspect share per period." height={280}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
          <YAxis tickFormatter={(v) => `${v}%`} domain={[0, 100]} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
          <Tooltip content={<BandMixTooltip />} />
          <Legend iconType="square" iconSize={10} verticalAlign="bottom" wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
          <Bar dataKey="Clear" stackId="mix" fill="var(--verdict-clear)" isAnimationActive={!reducedMotion} animationDuration={350} />
          <Bar dataKey="Doubtful" stackId="mix" fill="var(--verdict-doubtful)" isAnimationActive={!reducedMotion} animationDuration={350} />
          <Bar dataKey="Suspect" stackId="mix" fill="var(--verdict-suspect)" radius={[3, 3, 0, 0]} isAnimationActive={!reducedMotion} animationDuration={350} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
```

Both charts' baselines/card tops must align when placed side-by-side (Task 9 lays them
out in a `grid lg:grid-cols-2 gap-6` — same pattern as the existing `analytics/page.tsx`
lines 144-234 — both use `height={280}` and `ChartCard`'s identical header chrome, so
baseline alignment is automatic as long as neither chart adds extra top/bottom padding
inside its body slot).

`usePrefersReducedMotion.ts` (new, tiny, colocated in `frontend/src/lib/`):
```ts
"use client";
import { useEffect, useState } from "react";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
```

- [ ] Step 1: Write `usePrefersReducedMotion.ts`.
- [ ] Step 2: Write `CaptureRiskTrend.tsx` (line, incomplete-bucket dot styling, previous
      reference line, tooltip with current+previous).
- [ ] Step 3: Write `BandMixChart.tsx` (100% stacked, ≥3-bucket gate, caption fallback).
- [ ] Step 4: Confirm both use verdict colors ONLY in `BandMixChart` (data literally
      encodes verdicts) and `--accent` ONLY in `CaptureRiskTrend`'s single line (the one
      interactive/highlighted series) — grep the two files for any other color literal.

**Verify:**
```bash
cd frontend
npm run typecheck
```
(No build yet — these aren't wired into a page until Task 9. Typecheck confirms prop
shapes match Task 3's types.)

- [ ] Step 5: Commit.

---

## Task 8: `TopFlagReasons` (ranked list widget)

**Files:**
- Create: `frontend/src/components/analytics/TopFlagReasons.tsx`

**Details:**

Ranked list, `short_label` as the primary label (not the verbatim `reason` — BRAND.md
still requires the verbatim string be available, so it goes in a `title` attribute /
tooltip, never truncated, never rewritten). Count + percentage-of-flagged + neutral bar
(NOT verdict-colored — these are reason codes, not verdict bands; using verdict red here
would violate "verdict color only where data encodes verdicts"). Default to showing the
top 5 (`"Top5 default"` per the brief) with a "Show all" toggle if more exist.

```tsx
"use client";
import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { TopReason } from "@/lib/api/types";
import { formatCount } from "@/lib/format";

const DEFAULT_SHOWN = 5;

export function TopFlagReasons({ topReasons }: { topReasons: TopReason[] }) {
  const [showAll, setShowAll] = useState(false);
  const flagged = topReasons.filter((r) => r.reason_code !== "clear");
  const totalFlagged = flagged.reduce((s, r) => s + r.count, 0) || 1;
  const max = Math.max(1, ...flagged.map((r) => r.count));
  const shown = showAll ? flagged : flagged.slice(0, DEFAULT_SHOWN);

  return (
    <Card>
      <CardHeader title="Top flag reasons" subtitle="What is actually driving Doubtful and Suspect verdicts." />
      <div className="p-4">
        {flagged.length === 0 ? (
          <p className="text-body-sm text-text-muted">No flags yet — every verdict is Clear.</p>
        ) : (
          <>
            <ol className="space-y-3">
              {shown.map((r, i) => {
                const pct = Math.round((r.count / totalFlagged) * 100);
                return (
                  <li key={r.reason_code} title={r.reason} className="space-y-1.5">
                    <div className="flex items-baseline justify-between gap-3 text-body-sm">
                      <span className="flex items-center gap-2 text-text">
                        <span className="w-4 shrink-0 text-caption tabular-nums text-text-muted">{i + 1}</span>
                        {r.short_label}
                      </span>
                      <span className="shrink-0 tabular-nums text-text-secondary">
                        {formatCount(r.count)} · {pct}%
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
                      <div className="h-full rounded-full bg-text-secondary" style={{ width: `${(r.count / max) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
            </ol>
            {flagged.length > DEFAULT_SHOWN && (
              <Button variant="ghost" className="mt-3 px-0" onClick={() => setShowAll((s) => !s)}>
                {showAll ? "Show top 5" : `Show all ${flagged.length}`}
              </Button>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
```

- [ ] Step 1: Write `TopFlagReasons.tsx` per above.
- [ ] Step 2: Confirm the `title` attribute carries the verbatim `reason` (hover tooltip
      via native browser title, satisfying "full sentence tooltip" from the brief without
      a new tooltip dependency — acceptable since it's supplementary, not the primary
      information channel).

**Verify:**
```bash
cd frontend
npm run typecheck
```

- [ ] Step 3: Commit.

---

## Task 9: Assemble the page — states, wiring, Sidebar/uppercase fixes

**Files:**
- Modify: `frontend/src/app/(app)/analytics/page.tsx` (near-total rewrite)
- Modify: `frontend/src/components/layout/Sidebar.tsx` (remove left accent bar)
- Modify: `frontend/src/lib/nav.ts` (only if active-state styling needs a hook — likely
  no change needed; confirm)

**Details:**

**Sidebar fix** (BRAND.md §9/§11 violation: "no left border bars" — `SidebarInner`
currently renders a 3px `bg-brand-crimson` active-indicator bar, lines 42-49 of the
current file):
```tsx
// Remove this entire block:
// <span className={cn("h-4 w-[3px] rounded-full transition-colors", active ? "bg-brand-crimson" : "bg-transparent")} aria-hidden />
```
Replace the active-state text/icon color with `--accent` (per BRAND.md §9: "Active state:
`--surface-2` fill + accent text"), not `--text`:
```tsx
className={cn(
  "flex items-center gap-3 rounded-md px-3 py-2 text-body-sm font-medium transition-colors",
  active
    ? "bg-surface-2 text-accent"
    : "text-text-secondary hover:bg-surface-2 hover:text-text",
)}
```
And the icon should inherit: change `<Icon size={17} className="shrink-0" />` to
`<Icon size={17} className={cn("shrink-0", active && "text-accent")} />` (icons use
`--text-secondary` per the icon rules EXCEPT when they carry the active-nav accent, which
BRAND.md's own §9 sanctions explicitly — "active state: ... + accent text").

**Page assembly** (`analytics/page.tsx`):
```tsx
"use client";

import { BarChart3 } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton, CardsSkeleton } from "@/components/ui/Skeleton";
import { FilterBar } from "@/components/analytics/FilterBar";
import { InsightsPanel } from "@/components/analytics/InsightsPanel";
import { KpiRow } from "@/components/analytics/KpiRow";
import { CaptureRiskTrend } from "@/components/analytics/CaptureRiskTrend";
import { BandMixChart } from "@/components/analytics/BandMixChart";
import { TopFlagReasons } from "@/components/analytics/TopFlagReasons";
import { useAnalytics } from "@/lib/api/hooks";
import { useAnalyticsFilters } from "@/lib/analytics/useAnalyticsFilters";

export default function AnalyticsPage() {
  const { params, ...filterProps } = useAnalyticsFilters();
  const { data: a, isLoading, isError, refetch, isPlaceholderData } = useAnalytics(params);

  // Second, cheap query for the previous period's duplicates_caught (not on `previous`).
  const prevWindow = a
    ? { start_date: a.previous_period.from, end_date: a.previous_period.to, bucket: "daily" as const }
    : undefined;
  const { data: prevA } = useAnalytics(prevWindow ?? {});
  const prevDuplicatesCaught = prevWindow ? (prevA?.duplicates_caught ?? null) : null;

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics" description="Is capture risk trending up, and where should you look?" />
      <FilterBar {...filterProps} period={a?.period} previousPeriod={a?.previous_period} />

      {isError ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
          <p className="text-body-sm text-text-secondary">Couldn&apos;t load analytics from the API.</p>
          <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
        </Card>
      ) : isLoading || !a ? (
        <div className="space-y-8">
          <Skeleton className="h-24 w-full" />
          <CardsSkeleton count={4} />
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-[340px] w-full" />
            <Skeleton className="h-[340px] w-full" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : a.total === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No data to chart yet"
          what="Analytics summarise scored verdicts for the selected range. Score photos, widen the date range, or seed the demo to populate the charts."
          cta={{ label: "Analyze a photo", href: "/analyze" }}
        />
      ) : (
        <div className={cn("space-y-8 transition-opacity", isPlaceholderData && "opacity-60")}>
          <InsightsPanel analytics={a} prevDuplicatesCaught={prevDuplicatesCaught} />
          <KpiRow analytics={a} prevDuplicatesCaught={prevDuplicatesCaught} />
          <div className="grid gap-6 lg:grid-cols-2">
            <CaptureRiskTrend buckets={a.buckets} previous={a.previous} />
            <BandMixChart buckets={a.buckets} />
          </div>
          <TopFlagReasons topReasons={a.top_reasons} />
        </div>
      )}
    </div>
  );
}
```
(Import `cn` from `@/lib/utils`.)

Notes on this wiring:
- `isPlaceholderData` (from React Query's `placeholderData: (prev) => prev`, Task 3)
  drives a subtle opacity dim during a filter-triggered refetch instead of a full skeleton
  remount — "skeletons on refetch" per the brief is satisfied for the FIRST load (the
  `isLoading || !a` branch); subsequent filter changes show the previous data dimmed
  while the debounced+refetched data streams in, which is the calmer, more Stripe-like
  behavior and avoids a jarring full-page skeleton flash on every filter click. If the
  brief's "skeletons on refetch" is interpreted stricter (skeleton on EVERY param change,
  not just first load), swap the `isPlaceholderData` dimming for a full skeleton branch
  keyed on `isFetching && !isLoading` — flag this as a judgment call for review in Task 9's
  PR description; default to the dimming approach since full-skeleton-per-click reads as
  more sluggish, not calmer.
- `a.total === 0` empty state is checked only in the success branch, matching the
  existing page's behavior (line 107 of the current file) — preserved, not regressed.
- `FilterBar` receives `period`/`previous_period` once loaded so its caption line can
  read the backend-resolved bounds (Task 4's design note).

- [ ] Step 1: Fix `Sidebar.tsx`'s `SidebarInner` (remove the accent bar span; recolor
      active text/icon to `text-accent`).
- [ ] Step 2: Rewrite `analytics/page.tsx` per above.
- [ ] Step 3: Confirm `FilterBar`'s props interface (from Task 4) actually accepts
      `period`/`previousPeriod` — extend `FilterBar.tsx` if Task 4 didn't already include
      these props (Task 4 was written before this wiring was finalized; add them now if
      missing, defaulting to `undefined` and rendering no caption until the first
      successful fetch resolves real bounds).
- [ ] Step 4: Manually load `/analytics` in dev (`npm run dev`) and click through all 4
      range presets + all 3 buckets + a custom range; confirm the URL updates and a
      hard-reload on the resulting URL reproduces the same view (this is the
      URL-reproducibility hard requirement — verify it now, don't defer to Task 11).

**Verify:**
```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```
Expected: all three clean. `next build` is the strongest signal here since it type-checks
+ lints + statically analyzes every route, including the new client components.

- [ ] Step 5: Commit.

---

## Task 10: Responsive pass (§12 requirement — KPI 2×2 ≤1024px, charts stack)

**Files:**
- Modify: `frontend/src/components/analytics/KpiRow.tsx` (confirm/adjust grid breakpoints)
- Modify: `frontend/src/components/analytics/FilterBar.tsx` (confirm wrap behavior)
- Modify: `frontend/src/app/(app)/analytics/page.tsx` (confirm chart grid breakpoint)

**Details:**

This task is primarily **verification + small breakpoint corrections**, since Tasks 4-9
already used `lg:grid-cols-4` / `lg:grid-cols-2` (Tailwind's `lg` = 1024px), which
already satisfies "KPI 2×2 ≤1024px" (the `grid-cols-2` base applies below `lg`) and
"charts stack" (`grid-cols-1` implied base before `lg:grid-cols-2`). Confirm this
explicitly rather than assume:

- `KpiRow`: base class must be `grid grid-cols-2 gap-4 lg:grid-cols-4` (2×2 below 1024px,
  4-across at/above) — already written this way in Task 6; verify no stray
  `md:grid-cols-3` or similar breaks the 2×2 requirement at exactly 1024px.
- Chart grid in `page.tsx`: `grid gap-6 lg:grid-cols-2` (stacked/1-column below 1024px,
  side-by-side at/above) — already written this way in Task 9; verify.
- `FilterBar`: `flex flex-wrap gap-3` must not overflow horizontally at narrow widths;
  the custom-date inputs (when `preset === "custom"`) must wrap onto their own line
  rather than causing horizontal scroll — verify by resizing to 375px (mobile) as well as
  1024px, even though the brief's explicit gate is "≤1024px."
- `TopFlagReasons`/`InsightsPanel`: single-column `Card`s already stack naturally (block
  layout, no grid) — confirm padding doesn't force a min-width wider than the viewport at
  375px (e.g. long `short_label` text must wrap, not truncate silently beyond what the
  `title` tooltip covers — check no `whitespace-nowrap` leaked in from a copied pattern).
- Use Chrome DevTools responsive mode (or resize an actual browser window) at exactly
  1024px, 1023px, 768px, 375px — screenshot each per the QA task's requirement, but this
  task's job is to FIX anything ragged before Task 11 formally captures it.

- [ ] Step 1: Run the dev server, open `/analytics`, resize to 1024px/1023px/768px/375px,
      note any overflow/wrapping/height-mismatch issues.
- [ ] Step 2: Fix any breakpoint issues found (adjust Tailwind classes only — no new
      component logic should be needed if Tasks 4-9 were followed as written).
- [ ] Step 3: Re-check after fixes.

**Verify:**
```bash
cd frontend
npm run build
```
Plus manual resize-and-look (no automated responsive test in Phase A — visual, captured
formally in Task 11).

- [ ] Step 4: Commit (only if fixes were needed — otherwise note "no changes required,
      verified compliant" and skip the commit).

---

## Task 11: Visual & SaaS-hygiene QA pass (final gate)

**Files:** none expected (fix-only task); may touch any file from Tasks 2-10 if an issue
is found.

**Details:**

Run the app (`npm run dev` from `frontend/`) and manually walk `/analytics` end-to-end:

1. **Screenshot every widget in BOTH themes** (toggle via the existing `ThemeToggle`
   component) at desktop width: FilterBar, InsightsPanel, all 4 KPI cards, both charts,
   TopFlagReasons. That's a minimum of 7 widgets × 2 themes = 14 screenshots (use the
   `run` skill or manual browser screenshots — whichever this environment supports; if
   headless screenshotting isn't available, a careful manual visual read-through with
   DevTools open in both `prefers-color-scheme` states is the fallback, but attempt real
   screenshots first).
2. **Screenshot the full page at ≤1024px width** (exactly 1024px and one narrower, e.g.
   768px) in at least one theme, confirming the Task 10 layout.
3. Explicitly check, and fix anything ragged, against this list:
   - **Spacing:** one consistent scale, aligned grids, **equal card heights per row**
     (the 4 KPI cards — check the `sub` line doesn't wrap to 2 lines on one card and 1
     line on another, breaking equal height; if it does, reserve a fixed min-height on
     the `sub` slot in `MetricCard`), uniform padding, consistent section gaps (32px
     between the FilterBar/Insights/KPIs/Charts/TopReasons sections — confirm
     `space-y-8` renders this consistently).
   - **Numbers:** thousands separators present everywhere (`formatCount` used, not raw
     `a.total`), consistent decimals per metric (avg score always 1 decimal, suspect
     rate always 1 decimal, counts always whole), tabular numerals visible (numbers in a
     column/list actually align vertically — check `TopFlagReasons`' count column and
     the KPI values), deltas signed+worded (never a bare arrow/color).
   - **Organization:** each widget answers one question, sentence-case labels
     everywhere (re-grep for any stray `uppercase` class introduced in new components:
     `grep -rn "uppercase" frontend/src/components/analytics`), scannable at a glance.
   - **Alignment/polish:** the two charts' baselines and card tops align when side by
     side; legends (only `BandMixChart` has one) sit at the bottom consistently; loading
     → empty → error states all render correctly in BOTH themes (force each by: throttling
     network for loading, temporarily pointing `NEXT_PUBLIC_API_URL` at a dead port for
     error, and using a date range with no data for empty); real hover states on
     `TopFlagReasons` rows and FilterBar buttons (not just default browser `cursor:
     pointer` — confirm the `hover:bg-surface-2` etc. classes actually apply).
   - **Restraint:** accent color coverage is visibly ≤10% of the screen (the FilterBar's
     selected-state should NOT be accent-filled per Task 4's design — only focus rings,
     the trend line, and active-nav text should be accent; scan for accidental
     `bg-accent` on a large region).
   - **Accessibility spot-check:** tab through the FilterBar and TopFlagReasons "Show
     all" toggle with keyboard only — confirm a visible focus ring appears on each
     (this validates Task 2's `:focus-visible` change actually renders, not just
     compiles).
   - **Reduced motion:** enable `prefers-reduced-motion: reduce` (OS setting or DevTools
     emulation) and confirm the two charts do NOT animate on load (validates Task 7's
     manual `usePrefersReducedMotion` wiring — this is the one spot that's easy to miss
     since recharts ignores the CSS-only global rule).
4. Fix anything found. Re-screenshot only the fixed widgets to confirm.

- [ ] Step 1: Start `npm run dev`, open `/analytics` with the demo/seeded backend running
      (`npm run seed:demo` if the store is empty — needed to see non-empty states).
- [ ] Step 2: Capture the 14+ screenshots (both themes × widgets) and the 2 responsive
      widths.
- [ ] Step 3: Walk the explicit checklist above; log every issue found.
- [ ] Step 4: Fix each issue in its owning file (from Tasks 2-10).
- [ ] Step 5: Re-run the full verification suite once more, end to end.

**Verify:**
```bash
cd frontend
npm run test -- --run
npm run typecheck
npm run lint
npm run build
```
Expected: all four green. This is the final gate before Phase A is considered done —
every prior task's verify command should also still pass (no regressions introduced
during QA fixes).

- [ ] Step 6: Commit (message should summarize what the QA pass fixed, if anything).

---

## Self-Review

- **Spec coverage:** data layer + URL state (Task 3/4), filter bar + defaults + caption
  (Task 4), insights with exact thresholds (Task 5/6), 4 KPI cards with worded/colored
  deltas + small-sample guard + MetricCard fixes (Task 4/6), capture-risk trend with
  incomplete-bucket distinction + current/previous tooltip (Task 7), band-mix 100%
  stacked with data-gate (Task 7), top flag reasons ranked/Top5/tooltip (Task 8), all
  widget states (Task 9), BRAND §11 fixes — Sidebar accent bar, uppercase, motion ceiling,
  tabular numerals, contrast, focus rings (Tasks 2/4/9/11), responsive (Task 10), final
  QA pass (Task 11). Group-by/hierarchy explicitly excluded per scope and noted wherever
  the type/hook surface touches it (Task 3's `AnalyticsGroup`/`GroupBy` types exist for
  completeness only).
- **Placeholder scan:** no task ends in a vague "wire it up" — every task gives exact
  file contents or precise diffs, and every task has a runnable verify command. The one
  documented open judgment call (Task 9's placeholder-dimming vs full-skeleton-per-filter-
  change) is flagged explicitly as a reviewable decision, not hidden.
- **Type consistency:** `AnalyticsSummary`/`AnalyticsBucket`/`PeriodAggregate`/
  `PeriodBounds`/`TopReason` (Task 3) are the single shape threaded through
  `InsightsPanel`, `KpiRow`, `CaptureRiskTrend`, `BandMixChart`, `TopFlagReasons` (Tasks
  6-8) and the page (Task 9) with no re-declaration — all match the field names
  confirmed against the live backend source (`src/prooflens/api/scoring.py` and
  `analytics.py`), not assumed from the prose spec alone.
- **Known real gap flagged, not papered over:** `previous.duplicates_caught` does not
  exist in the backend response; Task 9 wires a second `useAnalytics` call against
  `previous_period` bounds to source it, and Tasks 5/6 accept it as an explicit nullable
  parameter rather than fabricating a number.
