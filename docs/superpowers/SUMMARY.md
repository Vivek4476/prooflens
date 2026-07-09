# ProofLens Analytics v4 — Delivery Summary

Branch: `frontend/analytics-v4` (off Phase A `frontend/analytics-redesign`). Every change is
**additive** — scoring / engine / webhook / golden set are byte-for-byte unchanged. Full spec
saved at `docs/superpowers/specs/2026-07-09-analytics-v4-consolidated-spec.md`.

Governing authorities: `docs/BRAND.md` + `docs/VERDICT_COPY.md`. Non-negotiables held throughout:
honest states (no fake AI, no fabricated data), small-sample guards, verbatim verdict sentences on
verdict surfaces (short labels only in aggregates), the drill-down contract, and zero scoring change.

---

## The page's four questions → what serves each (decision audit)

Every component maps to one of the four questions the page must answer, in order:

| Question | Components that answer it |
|---|---|
| **1 · Is capture risk rising?** | Suspect-rate KPI (+delta) · Capture-risk trend (vs previous-period avg) · "What changed" rail (suspect/avg-score/duplicate shifts) |
| **2 · What is driving flags?** | Top flag reasons (bar list) · Band mix per period · "dominant reason" insight |
| **3 · Where — which teams?** | "Where to look" team-hotspot bar list (branch/city/SM/RSM/SRSM/zone) |
| **4 · What should I do?** | "Review flagged captures" CTA · Flag-precision (are the flags trustworthy?) · drill-down from reasons/insights → /history |
| *(cross-cutting)* | System-health line (Pain 9), export (CSV/PDF), insights-rail freshness stamp — keep the four answers honest and actionable |

No component fails to serve one of the four. Removals are logged below.

## Root causes (Pains 1–2)

- **Pain 1 (overflow):** the reasons card locked to a 280px `ChartCard` while the row-count control
  sat *inside the body* and each reason rendered as two lines (label line + a separate bar). At
  Top 10 the ten two-line rows + the header + the in-body selector exceeded 280px, and the
  non-scrolling branch had no overflow containment → the card spilled. (The card-grid "overflow"
  the earlier report flagged was a *false positive* — CSS `scrollWidth` on a `.truncate` element.)
  Fix: rebuilt as a single-line bar list; selector moved to the card header; list always scrolls
  inside the card.
- **Pain 2 (rough tooltips):** each chart had its own bespoke recharts tooltip, so charts read as
  different products and hover felt inconsistent. Fix: one shared `ChartTooltip` (tokens, reduced-
  motion-gated fade, honest previous-period handling).

## Supersessions

- Pain 1 "card-grid overflow" → superseded by "false positive; the *reasons list* overflow was the
  real bug," fixed in `aa284d8`. Kept a Playwright regression guard.
- The earlier Phase B plan (`docs/superpowers/plans/2026-07-09-analytics-frontend-phaseB.md`) is
  superseded by the v4 gate plans; left untracked, not committed.
- `InsightsPanel` (top full-width card) → superseded by `InsightsRail` (Pain 7).
- Draft double-ring logomark → superseded by the chosen "Aperture & check" mark.

## Per-pain status

| Pain | Status | Key commits |
|---|---|---|
| 1 · Overflow | ✅ bar-list rebuild + regression guard | `2450d7b`, `aa284d8` |
| 2 · Shared tooltip | ✅ | `a49f1f6` |
| 3 · Realistic seed | ✅ source col + pure logic + 266-agent CSV + runnable CLI | `bbb3155` `5967d11` `7208fac` `1fb1782` |
| 4 · Review loop / flag precision | ✅ backend agg + seeded reviews + Review-quality card | `c8efec4`, `98b993d` |
| 5 · Brand architecture | ✅ option (a): ProofLens hosts, ABSLI bottom chip; + logomark & favicon | `7db0515`, `f7f2a46` |
| 6 · Cohesion + states audit | ✅ audited (see QA matrix); fixes folded in | — |
| 7 · Right-side insights rail | ✅ sticky rail xl+, full-width block <1280 | `2916056` |
| 8 · Per-card aggregation override | ✅ Daily/Weekly/Monthly override + "differs from page" chip + `trend_agg`/`bandmix_agg` URL state; span-gated (weekly ≥14d, monthly ≥60d) | `7b5dcb6` |
| 9 · System health | ✅ %-no-content + median-time-to-score line + methodology page; incomplete-bucket already distinct | `d204d52`, `68b7eb6` |
| 10 · Export | ✅ By-Team/series CSV + print-clean PDF | `d6aa3b7` |
| 11 · On-page faceting | ▸ fenced/documented (needs a faceted endpoint) | `6a9295c` |
| 12 · Component budget | ✅ rule in DESIGN_PRINCIPLES.md | `6a9295c` |
| 13 · Hierarchy_node mapping seam | ▸ documented in BACKEND_REQUIREMENTS.md | `6a9295c` |
| 14 · Usage counters | ▸ fenced/documented (design + table shape) | `6a9295c` |
| 15 · Chart annotations | ▸ fenced/documented (design + table shape) | `6a9295c` |
| Drill-down contract | ✅ reasons/insights → /history?filters → removable chips | `74650c4` |
| Infinity% honesty bug | ✅ small-sample guard in insights (caught by adversarial review) | `504e58e` |

## Removals + rationale

- **`InsightsPanel`** (top full-width "What changed" card) — removed; its content moved into the
  right-side rail (Pain 7). Served Q1/Q2 in a worse position (competed with data the user hadn't
  seen). No functionality lost.
- **`AbsliMasthead` / `PoweredByProofLens`** — removed; replaced by `ProofLensMasthead` +
  `TenantChip` (Pain 5). The old pair inverted BRAND §9.
- Nothing else removed — every surviving component maps to one of the four questions.

## Backend: made (additive) vs documented (pending)

**Made (additive, tested, zero scoring change):**
- `source="seed"` stored column + migration `0005` (Pain 3).
- Seeded review decisions via the existing review path (Pain 4).
- `flag_precision` block on `/v1/analytics/summary` (Pain 4).
- `system_health` block (`scored_without_content_pct`, `median_processing_ms`) (Pain 9).
- `/v1/results` already honoured `band`/`reason`/`rep_id`/`from`/`to` — used by the drill-down.

**Documented (pending, fenced — in `frontend/BACKEND_REQUIREMENTS.md`):**
- On-page faceting → needs a faceted analytics endpoint (Pain 11).
- `bucket=quarterly` for per-card override (Pain 8 quarterly).
- Viewer→hierarchy_node mapping (Pain 13).
- Usage counters table + increment/read (Pain 14).
- Chart-annotations table + CRUD (Pain 15).
- Scheduled email digest (Pain 10 next phase).
- A `/v1/results` node/branch filter (would let the team-hotspot rows drill down).

## Component inventory (reused vs new)

**Reused:** `Card`/`CardHeader`, `ChartCard` (extended with an `action` slot), `Button`,
`EmptyState`, `Skeleton`, `PageHeader` (`actions` slot), `TenantLogo`, `useUrlState`,
`useAnalytics`, the pure `insights`/`deltas`/`chartData`/`topFlagReasons`/`format` libs.

**New:** `ChartTooltip`, `ByTeamPanel` + `hotspots.ts`, `ReviewQuality`, `ExportControls` +
`exportCsv.ts`, `InsightsRail`, `SystemHealthLine`, `ProofLensMasthead`, `TenantChip`,
`ProofLensLogo` + `app/icon.svg`, `/methodology` page, drill-down chips on `/history`.

## Salesforce-doctrine audit

- **Borrowed well:** the Tremor bar-list pattern (reasons + team hotspots), rebuilt in our own
  tokens with **no dependency added**; drill-down-to-detail.
- **Deliberately NOT adopted:** splitting the page into tabs/sub-pages (breaks the
  What→Why→Where→What-next narrative) and Salesforce's high visual density — documented as the
  component-budget rule (max 7 top-level components; new widgets replace/relocate, never stack).
- **Borrowed incompletely, now fenced:** in-place faceting (Pain 11) — implemented as drill-out to
  /history for now; true in-place faceting needs a faceted endpoint (documented).

## Manual QA matrix

Verified live (Playwright, real API+DB) unless noted. Legend: ✅ pass · n/a not applicable.

| Surface | Light | Dark | 1440 | 1024 | 768/390 | hover | override | empty | loading | error |
|---|---|---|---|---|---|---|---|---|---|---|
| Shell (masthead/chip/nav) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | n/a | n/a | n/a |
| KPI row + deltas | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ✅ (insufficient-history) | ✅ | ✅ |
| System-health line | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ✅ (—) | n/a | n/a |
| Insights rail | ✅ | ✅ | ✅ (sticky) | ✅ (block) | ✅ (block) | ✅ (links) | n/a | ✅ (no-shifts) | ✅ | n/a |
| Capture-risk trend | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (tooltip) | ✅ (per-card) | ✅ | ✅ | ✅ |
| Band mix | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (tooltip) | ✅ (per-card) | ✅ | ✅ | ✅ |
| Top flag reasons | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Top-N | ✅ (all-clear) | ✅ | n/a |
| Where to look | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | dimension | ✅ (low-volume) | ✅ | ✅ |
| Flag precision | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | n/a | ✅ (<10 reviewed) | n/a | n/a |
| /history drill-down chips | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | removable | ✅ | ✅ | ✅ |
| Export CSV / print-PDF | ✅ | ✅ | ✅ | ✅ | ✅ (icons) | n/a | n/a | n/a | n/a | n/a |
| Methodology page | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | n/a | n/a | n/a | n/a |

On-page faceting is fenced (drill-out to /history instead), so the "facet" column is n/a.

## Independent review

Three adversarial reviews (two whole-branch code + one live-page visual) were run across the project.
They confirmed the data layer holds up and caught real bugs the author had missed — the "Last 90 days"
`Infinity%` honesty bug (fixed `504e58e`), the reasons overflow / chart clipping (fixed `aa284d8`),
the "Unmapped 50% hotspot" (excluded from ranking, noted as coverage), and — in the final pre-PR
review — a **Critical** URL-state clobber where the three `useUrlState` instances wiped each other's
params (per-card override snapped the page back to defaults); fixed by merging patches onto the full
querystring (`87a8ef6`, verified live). Two minors from that review were also fixed (favicon hex,
median including 0-ms rows). *Demo note:* the seed uses stub (instant) scoring, so "median
time-to-score" reads 0 ms in the demo — honest for stub data; a real deployment shows real times.

## Test + build state

Frontend: vitest green, typecheck + lint clean, production build green. Backend: pytest green
(209+), ruff + mypy clean, golden set intact. All changes additive.
