# Analytics v4 — Gate 1 Implementation Plan

**Worktree:** `/Users/vivekyadav/Desktop/prooflens-phase-b` (monorepo: backend `src/prooflens` +
`frontend/`). Backend venv: `.venv` (Python 3.14, `pytest`/`ruff`/`mypy` installed via
`pip install -e ".[service,dev]"`; `numpy`/`scipy` already present, no `faker`).
Branch: `frontend/analytics-v4` (per `.superpowers/sdd/progress.md`), built off Phase A
(`frontend/analytics-redesign`, PR #14 open — build onto it, don't finish it).

This is **Gate 1 of 4** in the v4 spec. Gate 1 = the three P0 credibility fixes (pains 1–3)
plus governing SaaS-hygiene and the gate's own verification. Gates 2–4 (cohesion/rail,
reviews/exports, fenced features) are out of scope here.

---

## Goal

Fix the three things that make the current `/analytics` page look unfinished/broken to
anyone evaluating it, without touching scoring/engine/webhook behavior:

1. **Top Flag Reasons never overflows its card**, at any content length or breakpoint —
   verified by an audited screenshot pass across every analytics card, not just this one.
2. **Every chart on the page shares one tooltip system** — anchored, themed, animated,
   and data-shaped identically — so the page reads as one product, not three prototypes
   stitched together.
3. **The demo data is credible.** Today's local seed produces 72 records at a 70.8%
   suspect rate and an average score of 32.8 — numbers that read as "broken demo," not
   "working fraud detector." A new realistic seed script fixes this for demos and QA,
   without faking API responses or burning vision-model calls on thousands of images.

## Current state (verified by reading the code, not assumed)

- `TopFlagReasons.tsx` (`frontend/src/components/analytics/TopFlagReasons.tsx`) already
  has a fixed `CARD_HEIGHT = 280`, `truncate` on the short label, a `title={r.reason}`
  native-tooltip attribute, and internal `overflow-y-auto` scrolling gated by
  `shouldScroll()` (`frontend/src/lib/analytics/topFlagReasons.ts`) for the `20`/`"all"`
  limit options. **This means Pain 1 may already be substantially mitigated** — Task 1
  below starts by reproducing the overflow with Playwright before changing anything, and
  only touches code where a real overflow is observed. `title=` is a native browser
  tooltip, not the shared hover/focus tooltip Pain 2 asks for elsewhere; it stays as a
  baseline accessible fallback but does not need to become the shared `ChartTooltip`
  (it's a list row, not a chart).
- `CaptureRiskTrend.tsx` and `BandMixChart.tsx` each define their own local
  `<Tooltip content={...}>` render function (`TrendTooltip`, `BandMixTooltip`) with
  near-identical markup (`rounded-lg border border-border bg-surface p-3 text-body-sm
  shadow-2`) but diverging structure — this is exactly the duplication Pain 2 targets.
  Neither currently shows a fade/rise entrance transition; recharts' `<Tooltip>` mounts
  the content div directly with no animation hook today.
- `usePrefersReducedMotion()` (`frontend/src/lib/usePrefersReducedMotion.ts`) exists and
  is already used by both charts for their draw-in animation (`isAnimationActive`) — the
  shared tooltip's fade/rise reuses this hook rather than relying on the global CSS
  reduced-motion override (recharts/portal content doesn't inherit it — documented in the
  hook's own comment).
- `tokens.css` (`frontend/src/styles/tokens.css`) already has real `--accent` (`#4c5fd5`),
  `--verdict-suspect` (`#dc2f45`/`#f0596e`), `--surface`, `--border`, `--shadow-2`, etc.
  It still carries `--brand-crimson` (ABSLI) for the tenant chip — untouched by this gate.
  `tailwind.config.ts` has `transitionDuration.DEFAULT = "180ms"` and keyframes `fade-in`
  (180ms ease-out), `slide-up` (200ms ease-out), `shimmer` — no keyframe exists yet for a
  120ms fade+2px-rise tooltip entrance; Task 4 adds one inside the existing ceiling.
- Backend: `ResultView.source` (`src/prooflens/service/views.py`) is a plain `str` field
  documented as `"webhook" | "direct"`. **It is not read from storage** — both
  `InMemoryRepo.record_result`/`_to_view`-equivalent (`src/prooflens/service/repo.py`)
  and the real `PostgresRepo._to_view` (`src/prooflens/db/repo.py:262`) **derive** it live
  as `"webhook" if job_id else "direct"`. There is no `source` column on `Result`
  (`src/prooflens/db/models.py:123`) at all. This means adding `source="seed"` is not a
  one-line change — it requires a real (additive) column, a migration, and updates to two
  `record_result` implementations and two derivation sites. Task 8 below scopes this
  precisely.
- `Repo.replace_hierarchy(tenant_id, rows, upload_id)` already exists and is exercised by
  `POST /v1/admin/hierarchy` (`src/prooflens/api/hierarchy_admin.py`); the CSV contract is
  `agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from` (`NODE_FIELDS` in
  `src/prooflens/service/hierarchy.py`). The seed script uploads through this exact path,
  not a hand-rolled insert, so hierarchy resolution (`service/hierarchy.py:resolve_node`)
  behaves identically to a real customer upload.
- No Playwright is installed in `frontend/` today (only transitive references inside
  other packages' `node_modules`). Task 2 and Task 10 add `@playwright/test` as a real
  devDependency.

## Architecture

- **Frontend chart tooltip:** one new component,
  `frontend/src/components/analytics/ChartTooltip.tsx`, plus a small shaping helper module
  `frontend/src/lib/analytics/chartTooltip.ts` (pure, unit-testable) that both
  `CaptureRiskTrend` and `BandMixChart` import. The component takes a generic
  `rows: TooltipRow[]` (label, current value, previous value, color) + `title`/`caption`
  props so both line and stacked-bar charts can feed it without chart-specific branching
  inside the shared component.
- **Frontend overflow audit:** a Playwright spec,
  `frontend/tests/e2e/analytics-overflow.spec.ts`, driven by `npm run dev` (or `next
  start` against a built app) with the API mocked/seeded, screenshotting every analytics
  card at 1440/1024/768px in both themes and asserting `scrollWidth <= clientWidth` /
  `scrollHeight` bounds on each `Card`.
- **Backend seed:** additive DB column `results.source`, an additive `Repo.record_result(
  ..., source: str = "direct")` parameter (both `InMemoryRepo` and `PostgresRepo`), a
  Python module `scripts/lib/seed_data.py` (pure generation logic, unit-testable with
  pytest, no DB/network) driven by a thin CLI `scripts/seed-realistic.py`, and a bundled
  fixture `scripts/sample-hierarchy.csv`. The seed calls `Repo.record_result(...,
  source="seed")` and `Repo.replace_hierarchy(...)` directly against a `PostgresRepo` built
  from `DATABASE_URL` — no HTTP, no vision-model calls.

## Tech stack

- Frontend: Next.js 15 (App Router), React 18, TypeScript, Tailwind, Recharts 2.13,
  `@tanstack/react-query`, Vitest + Testing Library (existing), Playwright (new
  devDependency, this gate).
- Backend: FastAPI/SQLAlchemy 2/Alembic/Postgres (`[service]` extra), pytest/ruff/mypy
  (`[dev]` extra), stdlib `random`/`datetime` + `numpy` for the seed's statistical
  distributions (already installed — no new backend dependency required).

## Global constraints (apply to every task)

- **BRAND.md is the only source of design truth.** Use real tokens only:
  `--text` / `--text-secondary` / `--text-muted`, `--surface` / `-2` / `-3`, `--border` /
  `-strong`, `--verdict-clear|doubtful|suspect` + paired `-bg`/`-fg`, `--accent` +
  `--accent-fg`, `--radius` (10px cards), `--shadow-1`/`--shadow-2`. Do **not** invent or
  port tokens like `--ink-3` or `--dur-1`/`--ease` from any prior spec draft — they do not
  exist in `tokens.css`. Where a spec phrase names a nonexistent token, map it to the real
  one and say so in the commit/PR (e.g. "axis labels" → `--text-muted`; a named duration →
  a literal ms value inside the Tailwind `transitionDuration`/keyframe system).
- **Motion ceiling:** nothing exceeds 300ms (BRAND.md §11). The tooltip's "~120ms fade + 2px
  rise" is a real CSS transition (`transition-[opacity,transform] duration-150` or a new
  Tailwind keyframe alongside `fade-in`/`slide-up`), gated by `usePrefersReducedMotion()`
  for any recharts-rendered content and by the global reduced-motion CSS for anything else.
  Under reduced motion the transition collapses to ~0 (instant show/hide, no slide).
- **Sentence case, no exclamation marks, no jargon** (BRAND.md §3) in every new string.
- **Accent ≤10% of any screen** — the shared tooltip uses `--surface`/`--border`, never an
  accent-filled background; only small accent touches (e.g. a focus ring) are permitted.
- **Verdict color is always paired with the verdict word** — the tooltip never shows a bare
  color swatch without the Clear/Doubtful/Suspect label next to it.
- **De-emphasis is opacity-only, never scale** — hovering one chart segment/series dims its
  siblings via `opacity`; nothing resizes or shifts layout on hover.
- **Tabular numerals, ≥12px, both themes** — reuse `formatCount`/`formatPct`/`formatScore`
  from `frontend/src/lib/format.ts` for every number the tooltip renders; never hand-format
  a number inline.
- **Backend changes are strictly additive.** No change to `src/prooflens/engine/**`
  (scoring, fusion, verdict precedence), no change to webhook behavior, no change to the
  golden set's expected outcomes (`tests/golden/labels.csv` and
  `tests/golden/test_golden.py` stay green untouched). New DB columns are nullable with a
  safe default and backfilled the same way `0004_hierarchy_and_result_ids.py` backfills
  `rep_id`/`opportunity_id` — follow that migration's shape exactly.
- **Honest states only** (BRAND.md §8, rule 6): the seed script never claims a simulated
  distribution is a live model judgement; seeded results carry `source="seed"` precisely so
  the UI (a later gate) can label them, and so this gate's own verification can distinguish
  seed rows from real scored rows in a shared database.
- **SaaS hygiene (governing, all tasks):** equal card heights within a row, aligned grids,
  thousands separators via `formatCount`, sentence-case labels, calm density (no
  card-in-card, no double borders), accent ≤10%, verified in both light and dark themes.
- **Testing bar per task type:** pure logic (chart data shaping, seed distribution math) →
  Vitest/pytest unit tests. Components → existing Testing Library patterns where already
  used, otherwise typecheck/lint/build as the floor. The overflow claim (Pain 1) and the
  final Gate 1 claim are **not considered done without a Playwright screenshot**, per the
  project's `verification-before-completion` discipline — no "should work" without
  evidence.
- Every task ends in a runnable verification command; no task is marked done on inspection
  alone.

---

## Task list

Numbered, dependency-ordered. Each task is sized to be independently reviewable.

### Task 1 — Reproduce Pain 1 with evidence before changing anything

Add Playwright as a frontend devDependency (`@playwright/test`, pinned to the version
already resolvable in the lockfile via `next`'s peer range) and a minimal
`frontend/playwright.config.ts` (baseURL from `PLAYWRIGHT_BASE_URL` env, default
`http://localhost:3000`, projects for `chromium` only — no cross-browser matrix needed for
an internal audit). Write `frontend/tests/e2e/analytics-overflow.spec.ts` that:
- Navigates to `/analytics` with a mocked or seeded API response containing a
  deliberately adversarial `top_reasons` payload (long `short_label` strings, 20+ distinct
  reasons) to force worst-case content.
- At 1440×900, 1024×768, and 768×1024 viewports, in both `light` and `dark` (toggle via
  the app's theme mechanism — check `frontend/src/app/**/providers.tsx` for how
  `next-themes` is wired), screenshots the `TopFlagReasons` card and asserts
  `element.scrollHeight <= element.clientHeight` and `scrollWidth <= clientWidth` on the
  card's outer `Card` element and on each row's label span.
- Saves screenshots to `frontend/tests/e2e/__screenshots__/` (gitignored) for manual
  review, and fails the test (not just logs) on any overflow.

Run it against the current code first. **Expected outcome given the code review above:**
this likely passes already for the default `limit=5`/`10` states (fixed height + truncate
+ scroll are already in place), but may reveal a real gap at `limit="all"` with many
distinct reasons if the internal `overflow-y-auto` list's `min-h-0` isn't actually
constraining flex-shrink correctly, or a horizontal overflow if a `short_label` has no
`min-w-0` ancestor somewhere in the row. Whatever the test finds is what Task 2 fixes —
do not pre-guess the fix before the screenshot exists.

**Verification:** `npx playwright test analytics-overflow` run and its output (pass/fail +
screenshot paths) captured in the PR description.

### Task 2 — Fix whatever Task 1's evidence shows, and lock the card height contract

Using Task 1's findings:
- If overflow is real, fix it in `frontend/src/components/analytics/TopFlagReasons.tsx`
  and/or `frontend/src/lib/analytics/topFlagReasons.ts` — likely candidates: ensure every
  ancestor of the truncating `<span>` has `min-w-0` (flex children default to
  `min-width: auto`, which defeats `truncate`), and confirm the `ol` with
  `overflow-y-auto` has a bounded parent height (the `flex h-full flex-col` wrapper should
  already do this, but verify with devtools computed height, not assumption).
- If Task 1 finds no overflow at all, this task becomes a no-op *except*: still assert in
  code (not just by eyeballing) that `CARD_HEIGHT` (280) matches the same constant the two
  charts pass to `ChartCard` (`height={280}` in `CaptureRiskTrend.tsx` and
  `BandMixChart.tsx`) — today this is three separate magic numbers (`280`, `280`, `280`)
  with no shared constant. Extract a single exported constant,
  `ANALYTICS_CARD_HEIGHT = 280`, from `frontend/src/lib/analytics/chartData.ts` (or a new
  small `frontend/src/lib/analytics/layout.ts`), and import it in all three components so
  the row-alignment is enforced by the type system, not by three developers remembering
  the same number.
- Full sentence stays in the tooltip on hover/focus, never in the row itself (already true
  via `title=`) — confirm this still holds after any edit.

**Verification:** re-run Task 1's Playwright spec — it must pass. `npm run typecheck` and
existing `frontend/src/lib/analytics/topFlagReasons.test.ts` (Vitest) still green.

### Task 3 — Audit every analytics card for overflow at 1440/1024/768px

Extend `analytics-overflow.spec.ts` (or add a sibling spec,
`frontend/tests/e2e/analytics-audit.spec.ts`) to cover the **whole** `/analytics` page, not
just `TopFlagReasons`: `KpiRow` cards, `InsightsPanel`, `FilterBar` (including the custom
date-range control and the bucket selector at narrow widths), `CaptureRiskTrend`,
`BandMixChart`. For each card, assert no element's `scrollWidth`/`scrollHeight` exceeds its
`clientWidth`/`clientHeight`, using adversarial data where relevant (e.g. a long insight
sentence in `InsightsPanel`, a long custom-range date string in `FilterBar`). Capture one
full-page screenshot per (breakpoint × theme) combination — 6 screenshots — for the PR and
for reuse in Task 12's final verification.

Fix anything this finds using the same principles as Task 2 (min-w-0 on truncating flex
children, bounded heights, no `w-screen`/negative-margin escapes). If nothing is found,
this task still produces the 6 baseline screenshots as evidence and is not skipped.

**Verification:** `npx playwright test analytics-audit`, all green; screenshots attached to
the PR.

### Task 4 — Build the shared `ChartTooltip` component

New files:
- `frontend/src/lib/analytics/chartTooltip.ts` — pure types + a shaping helper,
  `type TooltipRow = { label: string; color?: string; current: string; previous?: string
  }`, and small formatters that wrap `formatCount`/`formatPct` (never inline-format inside
  the component). Unit-tested (Vitest) for edge cases: no previous-period value, zero
  rows, long labels.
- `frontend/src/components/analytics/ChartTooltip.tsx` — the shared presentational
  component. Props: `title: string`, `caption?: string` (e.g. "(in progress)" for
  incomplete buckets, matching existing copy), `rows: TooltipRow[]`, `footer?: {label:
  string; value: string}` (e.g. the "Total" row `BandMixChart` shows today). Renders:
  `rounded-lg border border-border bg-surface p-3 shadow-2 text-body-sm`, tabular-numeral
  values via a `tabular-nums` class already used elsewhere, verdict-colored dot + label
  pairs where `color` is set (reusing the existing inline `style={{ backgroundColor:
  ... }}` swatch pattern from `BandMixTooltip`), and a current-vs-previous two-column row
  per `TooltipRow` when `previous` is present.
- Entrance animation: add a Tailwind keyframe (e.g. `tooltip-in`) to
  `frontend/tailwind.config.ts` alongside the existing `fade-in`/`slide-up` —
  `{ from: { opacity: "0", transform: "translateY(2px)" }, to: { opacity: "1", transform:
  "translateY(0)" } }`, animation `tooltip-in 150ms ease-out` (inside the 300ms ceiling;
  ~120–150ms matches the "micro" 120ms motion class in BRAND.md §11 closely enough given
  the existing 180ms `DEFAULT`/`fade-in`/`slide-up` precedent — do not invent a bespoke
  100ms value that has no sibling in the token system). Gate the animation class behind
  `usePrefersReducedMotion()` (import from `frontend/src/lib/usePrefersReducedMotion.ts`)
  — when reduced, render with the animation class omitted (instant, no transform) exactly
  as the existing charts already do for their draw-in animation.
- Sibling de-emphasis: expose an optional `dim?: boolean` per-row flag (or handle it at
  the call site via each chart's own `onMouseEnter`/`activeIndex` state) so hovering one
  series sets `opacity-40` (a value already used pattern-wise elsewhere, e.g. skeleton/
  disabled states — confirm exact class in `tailwind.config.ts`/existing components) on
  sibling Bar/Line elements — recharts supports per-datum `fillOpacity`/`opacity` props
  driven by component state; never `transform: scale`.

**Verification:** Vitest unit tests for `chartTooltip.ts` pass; a small RTL smoke test
(`ChartTooltip.test.tsx`, following the pattern of existing `.test.ts` files in
`frontend/src/lib/analytics/`) renders the component with/without `previous`, with/without
reduced motion, and asserts the verdict dot+label pairing rule (BRAND.md: color never
alone) — i.e. every rendered swatch has an adjacent text label in the same row.

### Task 5 — Refactor `CaptureRiskTrend` onto the shared tooltip

Replace `TrendTooltip` in `frontend/src/components/analytics/CaptureRiskTrend.tsx` with
`<Tooltip content={<CaptureRiskTooltip .../>} />` where `CaptureRiskTooltip` is a thin
adapter that shapes `TrendPoint` (from `frontend/src/lib/analytics/chartData.ts`) into
`ChartTooltip`'s `rows`/`title`/`caption` props: title = `point.label` (+ "(in progress)"
caption when `point.incomplete`), one row "Suspect rate" with `current = formatPct(point.rate)`
and `previous = formatPct(prevRate)` (the existing reference-line comparison value), and a
footer row for the image count (existing `formatCount(point.total)` + "image(s) scored"
pluralization — keep the existing singular/plural logic, don't regress it). Delete the
now-dead `TrendTooltip` function. No change to `toTrendData`/`previousPeriodRate` in
`chartData.ts` — those stay chart-data-shaping only, tooltip-shaping is a separate adapter
so `chartData.ts`'s existing Vitest coverage (`chartData.test.ts`) is unaffected.

**Verification:** `npm run typecheck`; existing `frontend/src/lib/analytics/chartData.test.ts`
still green (untouched); manual/Playwright hover screenshot showing the shared tooltip
renders correctly on this chart (can be folded into Task 6's combined check).

### Task 6 — Refactor `BandMixChart` onto the shared tooltip

Same pattern in `frontend/src/components/analytics/BandMixChart.tsx`: replace
`BandMixTooltip` with an adapter feeding `ChartTooltip` three rows (Clear/Doubtful/Suspect,
each with its `--verdict-*` color dot, `current = formatCount(point.rawClear|...)`) plus a
`footer` row for `Total`. This chart doesn't currently have a "previous period" value wired
into its tooltip at all (only `CaptureRiskTrend` does, via the reference line) — decide
explicitly: either (a) leave `previous` unset per row for this chart (acceptable — the
brief says the shared *system* supports current+previous, not that every chart must use
both), or (b) if band-mix previous-period data is cheaply available from
`AnalyticsSummary.previous` already fetched by the page, wire it in for parity. Prefer (a)
for Gate 1 scope discipline — note (b) as a follow-up rather than silently expanding scope;
record the decision in the PR description. Delete the now-dead `BandMixTooltip` function.
Also wire sibling de-emphasis here specifically: hovering one stacked-bar segment
(Clear/Doubtful/Suspect) should dim the other two via opacity, using recharts' `Bar`
`onMouseEnter`/`onMouseLeave` + a component-level `activeSeries` state feeding each `Bar`'s
`fillOpacity`.

**Verification:** `npm run typecheck`; visual check (Playwright screenshot, hover state) that
sibling segments dim via opacity (diff two screenshots: hover vs. no-hover, confirm no
layout/size shift — only color/opacity changes between them).

### Task 7 — Cross-chart consistency pass + de-dup check

With both charts refactored, grep for any remaining chart-local tooltip markup
(`bg-surface p-3.*shadow-2` pattern) outside `ChartTooltip.tsx` to confirm zero duplication
remains. Confirm both charts' tooltips: same border-radius, same padding, same font sizes
(12px caption / 13px body-sm per BRAND.md §7 scale — verify computed styles match, not just
class names, since Tailwind's `text-caption`/`text-body-sm` utilities must resolve to the
same px values used elsewhere), same shadow token (`shadow-2`), same animation timing.
This is the task that proves "a chart here must be unmistakably the same product as every
other" — do it with a side-by-side screenshot (both tooltips visible, or two sequential
screenshots) attached to the PR, not just a code-reading claim.

**Verification:** `grep -rn "border-border bg-surface p-3" frontend/src/components/analytics/`
returns matches only inside `ChartTooltip.tsx`; side-by-side screenshot in the PR.

### Task 8 — Backend: additive `source="seed"` plumbing

This is the precise minimal change identified during research (see "Current state" above
— `source` is derived, not stored):

1. **Migration** `migrations/versions/0005_result_source.py` (follows
   `0004_hierarchy_and_result_ids.py`'s shape exactly): `op.add_column("results",
   sa.Column("source", sa.String(16), nullable=False, server_default="direct"))`. Backfill
   existing rows: `UPDATE results SET source = 'webhook' WHERE job_id IS NOT NULL` (the
   `server_default='direct'` already covers the direct/null-job_id rows). Downgrade drops
   the column. This is additive and backward-compatible — no existing row's *observed*
   `source` value changes (webhook rows still say "webhook", direct rows still say
   "direct"); only seeded rows will ever show `"seed"`.
2. **`src/prooflens/db/models.py`**: add `source: Mapped[str] = mapped_column(String(16),
   default="direct")` to `Result`.
3. **`src/prooflens/service/repo.py`** (`Repo` protocol + `InMemoryRepo`): add
   `source: str = "direct"` keyword-only param to `record_result`; `InMemoryRepo` stores it
   directly on the `ResultView` instead of deriving `"webhook" if job_id else "direct"` —
   but preserve back-compat by defaulting the derivation only when `source` isn't
   explicitly passed as `"seed"` (i.e. keep existing webhook/direct call sites unchanged —
   they don't pass `source` at all, so the derived default logic must stay for them; only
   the new seed call site passes `source="seed"` explicitly). Simplest correct
   implementation: keep the two real callers (`processor.py` for webhook jobs, `scoring.py`
   for direct `/v1/score`) passing nothing, defaulting to the existing derivation logic
   inline in `record_result` itself: `source = source_override or ("webhook" if job_id else
   "direct")`.
4. **`src/prooflens/db/repo.py`** (`PostgresRepo`): same `record_result` signature change,
   write `source` to the new column; `_to_view` reads `r.source` directly instead of
   deriving it from `r.job_id` (this is the one behavior change — verify it against
   existing integration tests, since a NULL/legacy row now reads its persisted `source`
   column, which the migration backfills correctly so no test should observe a difference).
5. Check callers: `src/prooflens/service/processor.py` (webhook path) and
   `src/prooflens/api/scoring.py` (direct `/v1/score` path) — confirm neither needs to
   change (they should keep calling `record_result` without a `source` kwarg, relying on
   the job_id-based default), and add a one-line comment at each call site noting `source`
   defaults from `job_id` unless a caller (e.g. the seed script) overrides it.
6. **`src/prooflens/service/views.py`**: widen `ResultView.source`'s docstring/type comment
   from `"webhook" | "direct"` to `"webhook" | "direct" | "seed"` (still a plain `str`
   field, no enum — matches the existing style).

**Verification:** `alembic upgrade head` runs clean against a scratch local Postgres (or
`alembic check`/`alembic upgrade head --sql` dry-run if no local Postgres is available in
this environment); `pytest -q` (all existing suites, esp.
`tests/unit/test_result_view_review.py`, `tests/integration/test_scoring_api.py`,
`tests/integration/test_webhook_e2e.py`) green; `ruff check src tests scripts migrations`
and `mypy src` clean; a new small unit test
`tests/unit/test_result_source.py` asserting: (a) a direct-scored result has
`source == "direct"`, (b) a webhook-scored result has `source == "webhook"`, (c) a result
recorded with `record_result(..., source="seed")` round-trips as `source == "seed"` through
both `InMemoryRepo` and (if a test Postgres is available in CI) `PostgresRepo`.

### Task 9 — `scripts/sample-hierarchy.csv` + seed generation logic (pure, unit-tested)

1. `scripts/sample-hierarchy.csv`: a realistic tree matching the exact
   `agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from` header
   (`_HEADER`/`NODE_FIELDS` contract in `src/prooflens/api/hierarchy_admin.py` /
   `src/prooflens/service/hierarchy.py`). Build ~150–300 `agent_id` rows spanning a
   plausible org: 4–5 zones (`zonal_head`), 2–3 `srsm` per zone, 2–4 `rsm` per srsm, 3–6
   `sm` per rsm, each `sm` owning 3–8 agents, each with a `branch`/`city` pair from a small
   realistic Indian-city list (matches ABSLI's domain — see `docs/BRAND.md` tenant
   context). Single `valid_from` (today or the seed window's start) — no historical
   hierarchy versioning needed for Gate 1. `agent_id` values must be the same ones the
   seed's result generation uses for `rep_id` (case/whitespace-normalized the same way
   `service/ids.py:normalize_id` does, so `hierarchy_status()`'s match rate reads ~100%,
   not "unmapped").
2. `scripts/lib/seed_data.py` — pure Python, **no DB/network import**, unit-testable:
   - `generate_agent_pool(hierarchy_csv_path) -> list[str]`: reads the CSV, returns
     normalized agent_ids.
   - `sample_timestamp(day: date, rng: random.Random) -> datetime`: weekday-biased
     (weekends get materially fewer records — e.g. 10–20% of a weekday's volume, not zero,
     since some field visits happen weekends too), clustered in working hours (~9am–7pm
     IST-equivalent, bell-shaped/triangular around midday, not uniform).
   - `sample_verdict(rng: random.Random) -> Verdict`: draws a band from a target mix
     (~2–5% Suspect, ~8–12% Doubtful, rest Clear — sample the exact percentages within
     those ranges per run so repeated seeds aren't suspiciously identical), then within
     Suspect/Doubtful draws a `reason_code` from a plausible distribution (recycled +
     screen_recapture + designed_graphic + no_people_or_irrelevant dominate Suspect;
     too_blurred + no_content_analysis dominate Doubtful — weight using the
     `REASON_PRIORITY` ordering in `src/prooflens/engine/verdicts.py` as a guide for
     relative plausibility, not a hard rule), a `score` consistent with the chosen band's
     range from `docs/VERDICT_COPY.md`'s table (Clear ≥70, Doubtful 40–69, Suspect <40,
     sampled with light noise, not always the boundary value), and constructs a real
     `Verdict` dataclass (`src/prooflens/engine/types.py`) with `reason =
     REASON_TEXT[reason_code]` and `reason_code = reason_code.value` pulled from the actual
     `REASON_TEXT`/`Reason` enum in `engine/verdicts.py` — **never a hand-typed string** —
     so a future copy change in `verdicts.py` can't silently desync the seed from reality.
     `checks=[]` (empty is valid — `CheckOutcome.available=False` entries are also
     acceptable filler but not required for Gate 1) and `rubric_version` set to the
     current default (check `src/prooflens/engine/scoring_config.py` /
     `migrations/versions/0003_default_vision_groq.py` for the live default rather than
     hardcoding a stale one).
   - `generate_seed_plan(days: int, records_per_day_range: tuple[int,int], agent_pool:
     list[str], rng: random.Random) -> list[SeedRecord]`: the top-level pure generator —
     `SeedRecord = (created_at: datetime, rep_id: str, verdict: Verdict,
     opportunity_id: str)` — producing "several thousand" records (target: pick a
     per-day range, e.g. 30–90/day, that lands the 60–90-day total in the low-to-mid
     thousands) across the requested window, each timestamp from `sample_timestamp`, each
     `rep_id` drawn from `agent_pool`, each `opportunity_id` a synthetic but stable id
     (e.g. `f"OPP-{i:06d}"`).
3. **pytest** `tests/unit/test_seed_data.py` (or `scripts/tests/test_seed_data.py` if the
   project's convention keeps script tests separate — check `tests/unit/` for the existing
   pattern and match it) covering: band distribution lands within the target ranges over a
   large sample (statistical assertion with tolerance, seeded RNG for determinism), reason
   distribution only ever uses real `Reason` enum values with matching `REASON_TEXT`,
   weekday bias is real (weekday timestamp count > weekend count, non-zero on both),
   working-hours clustering (e.g. assert >80% of timestamps fall in a 9am–7pm band), every
   generated `rep_id` is present in the sample hierarchy's agent pool.

**Verification:** `pytest tests/unit/test_seed_data.py -q` green; `ruff check
scripts` and `mypy src` (if `scripts/lib` is included in mypy's scope — check
`pyproject.toml`'s `[tool.mypy]` `files`/`mypy_path` and add `scripts/lib` if it isn't
already covered, since the plan requires this to be additive-quality code, not
untyped throwaway).

### Task 10 — `scripts/seed-realistic.py` — the real-repo-path CLI

Thin CLI wrapping Task 9's pure logic:
- Reads `DATABASE_URL` from the environment (same variable the app/`alembic` use — see
  `src/prooflens/config.py` and `README.md`'s "Without Docker" section); refuses to run
  with a clear, honest-state error message if unset (BRAND.md voice: specific,
  forward-looking, no "oops") rather than silently defaulting anywhere.
- Accepts flags: `--days` (default 75, within the 60–90 spec range), `--tenant-slug`
  (default `dev`, matching `scripts/seed_dev_tenant.py`'s `DEV_SLUG`), `--seed` (RNG seed,
  for reproducible demo runs), `--hierarchy-csv` (default
  `scripts/sample-hierarchy.csv`), `--dry-run` (prints the planned record count + band/
  reason distribution summary without writing).
- Resolves the tenant via `PostgresRepo`/`get_tenant_by_slug` (fails clearly if the tenant
  doesn't exist yet — tells the operator to run `scripts/seed_dev_tenant.py` first rather
  than creating one implicitly, keeping this script single-purpose).
- Calls `repo.replace_hierarchy(tenant_id, rows, upload_id)` once with the parsed
  `sample-hierarchy.csv` (reuse the exact same CSV-row-dict shape
  `hierarchy_admin.py:_parse_csv` produces, so this never drifts from the real upload
  contract — consider importing `_parse_csv`-equivalent parsing logic or literally reusing
  the CSV row shape/normalization).
- Iterates `generate_seed_plan(...)` and calls
  `repo.record_result(tenant_id, job_id=None, verdict, opportunity_id=..., rep_id=...,
  source="seed")` per record, batching `repo.commit()` periodically (e.g. every 500
  records) rather than once per record (perf) and once at the end.
- Idempotency note: **not** idempotent by design (unlike `seed_dev_tenant.py`) — reseeding
  adds more rows. Document this explicitly in the script's docstring and in Task 11's
  README addition, with a suggested `TRUNCATE results, hierarchy;` (or a
  `--wipe-existing-seed` flag deleting only `WHERE source = 'seed'`) as the safe re-run
  path. Prefer adding the `--wipe-existing-seed` flag (deletes only `source='seed'` rows —
  never touches real `direct`/`webhook` rows) since a demo database is likely to be
  reseeded more than once; this is a small additive convenience, not scope creep.
- Progress output to stdout (record count as it goes) — this will run for thousands of
  inserts and should not look hung.

**Verification:** `python scripts/seed-realistic.py --dry-run --days 75` prints a plausible
summary with no DB connection required for the dry-run path; against a real local
Postgres (`docker compose -f deploy/docker-compose.yml up -d db` + `alembic upgrade head` +
`python scripts/seed_dev_tenant.py`), a full run completes, `GET /v1/analytics` (or a
direct SQL count) shows several thousand rows with suspect_pct in the 2–5% range and
`source='seed'` on all of them; `ruff check scripts` / `mypy src` clean.

### Task 11 — README: document the seed as the demo-setup step

Update `README.md`'s existing demo section (currently `python
scripts/generate_demo_images.py` + `npm run seed:demo`, lines ~122–124) to add the
realistic-data path as an alternative/complement: after `alembic upgrade head` and
`scripts/seed_dev_tenant.py`, add:

```bash
export DATABASE_URL=postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens
python scripts/seed-realistic.py --days 75
```

Explain in prose (matching the surrounding doc's terse style): this populates several
thousand realistic historical results plus a sample org hierarchy so Analytics/History/
By-Team views have credible data immediately, as distinct from
`generate_demo_images.py`/`seed:demo` which push a handful of real images through the live
vision model for the Analyze-page demo. Note explicitly that `seed-realistic.py` never
calls the vision backend and is safe to run without a `GROQ_API_KEY`.

**Verification:** README renders correctly (manual read-through); no broken relative links;
matches the doc's existing voice (checked against BRAND.md §3 — no jargon, no exclamation
marks).

### Task 12 — Gate 1 verification: show the reseeded page

The gate isn't done on inspection — it's done on screenshot evidence, per this project's
`verification-before-completion` discipline. Two paths, pick based on what's feasible in
this environment (document the choice, don't silently skip):

- **Preferred:** stand up a local Postgres (`docker compose -f deploy/docker-compose.yml
  up -d db`, or a local `postgres` if Docker isn't available), run `alembic upgrade head`,
  `scripts/seed_dev_tenant.py`, then `scripts/seed-realistic.py --days 75`, start the API
  (`uvicorn prooflens.api.app:app --port 8000`) and the frontend (`npm run dev`), and run a
  Playwright spec against the **real seeded page** (not mocked data) —
  `frontend/tests/e2e/analytics-gate1-verify.spec.ts` — capturing full-page screenshots at
  1440/1024/768px × light/dark (6 screenshots minimum) of `/analytics` with real seeded
  data, plus one hover-state screenshot per chart showing the shared `ChartTooltip`.
- **Fallback (if a local Postgres genuinely isn't available in this execution
  environment):** document precisely why, and instead run the same Playwright spec against
  mocked API data shaped like the seed script's realistic output (reuse
  `generate_seed_plan`'s distribution to build a mock `AnalyticsSummary` fixture) — this
  still proves the frontend fixes (Pains 1 and 2) render correctly with realistic-shaped
  data, and separately prove the seed script's DB-writing path via Task 10's pytest +
  `--dry-run` evidence plus a code walkthrough of the exact `record_result`/
  `replace_hierarchy` calls. State clearly in the PR which path was taken.

Either way, the verification task explicitly confirms and records in the PR description:
- No overflow in any card at any of the 3 breakpoints, either theme (cross-reference
  against Task 3's audit).
- The shared `ChartTooltip` renders identically (same visual language) on both
  `CaptureRiskTrend` and `BandMixChart`.
- Which database the seed ran against (local Docker Postgres vs. mocked-fixture fallback)
  — and an explicit note that pointing `scripts/seed-realistic.py` at the production
  Render Postgres is **an operator decision the script deliberately does not make** (no
  environment auto-detection, no default that could accidentally hit prod — `DATABASE_URL`
  must be explicitly exported by whoever runs it).

**Verification:** the Playwright spec's pass/fail output plus all screenshots attached to
the PR; a one-paragraph summary in the PR description stating which of the two paths above
was used and why.

---

## Risks (flagged for review, not silently resolved)

1. **Seed-through-real-path approach.** Calling `Repo.record_result` directly (thousands
   of times) against a `PostgresRepo` is the only way to get `source="seed"` provenance
   and real hierarchy resolution without re-running the vision model or faking HTTP — but
   it means the seed script imports backend internals (`PostgresRepo`, `Verdict`,
   `Reason`) directly rather than going through the API. This is correct for Gate 1's
   stated constraint ("not by faking API responses and NOT by re-running the vision model
   on thousands of images") but it does mean the script has to stay in lockstep with
   `Repo`'s protocol — if `record_result`'s signature changes later, this script breaks
   silently unless it's covered by a test that imports it (Task 9's pytest coverage
   partially mitigates this by testing the pure logic, but the DB-writing CLI path itself
   is not covered by CI without a Postgres service — flagged as a gap, not fixed here).
2. **`source="seed"` plumbing touches two `record_result` implementations and two
   `_to_view` derivation sites** (`InMemoryRepo` in `service/repo.py`, `PostgresRepo` in
   `db/repo.py`) plus a new migration. This is the single riskiest backend change in this
   gate because `_to_view`'s behavior changes from *derived* to *stored* — Task 8's
   verification leans hard on existing integration tests
   (`test_scoring_api.py`, `test_webhook_e2e.py`, `test_result_view_review.py`) staying
   green specifically to catch any regression in the existing webhook/direct source
   values, since those are relied on elsewhere (e.g. any existing UI badge or filter — grep
   for `source ===` / `source ==` usage in `frontend/` before merging to confirm nothing
   assumes only two possible values).
3. **Which database the seed runs against is an explicit operator decision, not
   automated.** The script takes `DATABASE_URL` from the environment with no default and
   no environment-detection logic — this is deliberate (prevents an accidental seed run
   against the production Render Postgres) but means Task 12's "show the reseeded page"
   verification is only as good as whichever database the operator running this plan
   points it at. The plan's preferred path is a local/Docker Postgres; seeding the actual
   Render production database is explicitly out of scope for this gate and should require
   a separate, deliberate, human-approved step if ever done.
4. **No Playwright currently in the repo.** Tasks 1, 3, and 12 all depend on adding it as a
   new devDependency and getting it working in this environment (browser binaries via
   `npx playwright install chromium`, which needs network access) — if that install fails
   in a sandboxed CI/agent environment, Tasks 1/3/12's screenshot evidence may need to run
   in a different environment than the one authoring the code. Flagged, not resolved here.
5. **Chart tooltip `previous`-period parity is intentionally partial** (Task 6): only
   `CaptureRiskTrend` currently has a natural "previous" comparison value; `BandMixChart`
   does not without extra data plumbing. The plan defers full parity rather than silently
   fetching more data than the page currently loads, to keep Gate 1's blast radius
   contained — call this out explicitly in review rather than treating it as done.
