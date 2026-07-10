# ProofLens Analytics — Final Consolidated Spec (v4)

> Saved verbatim from the owner's pasted prompt (2026-07-09) so it can't be lost.
> Supersedes ALL prior analytics prompts and addenda. Record supersessions in SUMMARY.md.

AUTHORITIES: docs/BRAND.md + docs/VERDICT_COPY.md govern all visual and copy decisions and
win over any instinct or reference pattern below.

## Non-negotiables (fenced — no redesign may touch these)
- Honest states: no fake AI, no fabricated data, no simulated judgments; computed insights
  are never labeled/styled as AI-generated.
- Small-sample guards: no delta/insight renders when the comparison base is below its
  threshold — "insufficient history" instead.
- Verbatim verdict sentences on verdict surfaces; short_labels only in aggregates.
- Drill-down contract: aggregates navigate to /history with querystring filters, rendered
  there as removable chips.
- Scoring pipeline, engine, and webhook flow change ZERO.

THE PAGE'S JOB — answer in order: (1) Is capture risk rising? (2) What is driving flags?
(3) Where — which teams? (4) What should I do? Every component must serve one of those four
or be removed (log removals + rationale in SUMMARY.md).

## P0 — Credibility & hygiene
- **Pain 1** — Content escapes its container (Top Flag Reasons overflows). short_label
  single-line truncation + ellipsis; full verdict sentence in tooltip; fixed card height
  matched to row neighbor; internal scroll only beyond Top 10; audit every card at
  1440/1024/768.
- **Pain 2** — Rough chart tooltips. ONE shared tooltip: anchored, 120ms fade + 2px rise,
  surface+border+shadow tokens, current AND previous-period values, sibling opacity
  de-emphasis, reduced-motion instant.
- **Pain 3** — Demo data sabotages the product. scripts/seed-realistic: 60–90 days, several
  thousand records, ~2–5% suspect / ~8–12% doubtful, plausible reason mix, working-hours
  timestamps, rep_ids → bundled sample hierarchy, seeded through the REAL results path
  (source="seed"). Document in README.
- **Pain 4** — Analytics can't answer "were the flags right?". Backend additive: reviews
  table (tenant_id, result_id, decision: confirmed|cleared|false_positive, reviewer, note,
  decided_at) + POST /v1/reviews + Review Queue actions. Analytics gains "Flag precision"
  KPI (confirmed ÷ reviewed, n≥20 guard) + reviewed-coverage %. Honest "pending review
  data" state if deferred; never a fabricated precision number.
- **Pain 5** — Brand architecture ambiguous on the live shell (tenant logo as hero,
  ProofLens as footer — inverting BRAND.md §9). ASK before implementing — (a) BRAND.md
  compliance (ProofLens hosts, tenant chip at sidebar bottom) or (b) deliberate configurable
  white-label per tenant. Default (a). Either way, remove the red left-border nav active
  state (active = surface-2 fill + accent text). **Owner answered: (a).**

## P1 — Structure & trust
- **Pain 6** — Cohesion. One grid/rhythm: 32px section gaps, equal card heights per row,
  two 280px charts flush. One card anatomy (header H2+caption left / controls right, body,
  optional footer). One chart language. Six BRAND type roles only; tabular numerals. Full
  states audit per widget in both themes × three breakpoints.
- **Pain 7** — Right-side insights rail (~300px sticky): main col = KPIs → Capture Risk
  Trend → Band Mix → Top Flag Reasons → By Team; rail = comparison-window caption, insight
  bullets (severity dot + drill link), data-freshness stamp. Below 1280px rail becomes a
  full-width block AFTER the KPI row. Header "What changed", caption "Computed from your
  data · vs previous {period}".
- **Pain 8** — Global-first with visible per-card override: cards follow the global filter;
  a card-header control overrides that card only (aggregation gated to data span; weekly
  Week 1..N chips). Overridden card wears "Viewing: Quarterly · differs from page" ✕ to
  resync. Card state serializes to URL.
- **Pain 9** — System-health: two quiet KPIs ("% scored without content check", "median
  time-to-score") as a compact line under KPIs or in rail; "How scores work" methodology
  link near freshness stamp. Current incomplete bucket visually distinct (reduced opacity +
  "in progress").
- **Pain 10** — Export: By-Team CSV + full-page print-clean PDF (tenant logo permitted in
  export header). Scheduled email digest documented-only in BACKEND_REQUIREMENTS.

## P2 — Doctrine & platform seams (rules now, builds fenced)
- **Pain 11** — On-page faceting (fenced): clicking a Band Mix segment or reason row
  re-filters the OTHER widgets in place, shown as removable chip ("Faceted: Suspect ×");
  drill-out to /history becomes an explicit "view submissions" action. Implement ONLY if it
  reuses the single-query + client-filter model; if it forces per-widget queries, write it
  up in BACKEND_REQUIREMENTS instead and stop.
- **Pain 12** — Component budget rule in docs/DESIGN_PRINCIPLES.md: max 7 top-level
  components on this page (currently 6 + system-health line); any future widget must replace
  or relocate, never stack. NOT adopted from Salesforce: tabs/pages splitting; their density.
- **Pain 13** — Design the seam only: document an optional user→hierarchy_node mapping in
  BACKEND_REQUIREMENTS (when present, /analytics defaults group_by scope to viewer's node).
  Do NOT build the mapping UI now.
- **Pain 14** — Privacy-safe tenant-scoped usage counters (page views, filter changes,
  drill-downs, exports — no per-user tracking, no PII); surface "last 7 days page views" in
  Settings → System health.
- **Pain 15** — Chart annotations (P2, small): tenant-scoped dated markers ("Camera lock
  enforced · Jul 1") as a subtle vertical rule + label on time charts; admin CRUD in
  Settings.

## Build order
- Gate 1: Pains 1, 2, 3 (hygiene + seed). → show reseeded page.
- Gate 2: Pains 6, 7, 8, 9 (cohesion, rail, overrides, trust signals).
- Gate 3: Pains 4, 10 (review loop + exports). → PAUSE for review.
- Gate 4: Pains 11–15 fenced/documented.
- Pain 5 (brand) implements at whichever gate follows the owner's answer; default (a) if
  unanswered by Gate 2.

ASK BEFORE GUESSING: brand (a) vs (b); whether review-decision UX needs a mandatory approval
note; SMTP/digest infra (defer if unknown).

DELIVER: implemented redesign + SUMMARY.md (root causes of Pains 1–2, supersessions, per-
section decision audit mapping each component to one of the four questions, removals +
rationale, backend made-vs-documented, component inventory reused-vs-new, Salesforce-doctrine
audit, manual QA list: both themes × three breakpoints × hover/override/facet/empty/loading/
error). Bar: passes design review at Linear and enterprise eval at Stripe — cohesion over
decoration, honesty over polish, restraint over cleverness.
