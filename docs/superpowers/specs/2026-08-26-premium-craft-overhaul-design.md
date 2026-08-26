# ProofLens — Premium Craft Overhaul (Design Spec)

**Date:** 2026-08-26
**Status:** Approved (brainstorm) — ready for implementation planning
**Scope:** Frontend visual craft only. No new routes, no new data, no backend changes.
**Branch:** `feature/premium-craft-overhaul`

---

## 1. Problem & Goal

The Glass Cockpit frontend (Phases 1–3, now on `main`) is **competent but not premium**. The
system is disciplined — tightly scoped crimson, correct verdict semantics, a clean sidebar+topbar
shell — but it reads as a *tasteful admin dashboard*, not a high-end product. The gap is **craft**,
not features: typographic authority, considered depth/materiality, purposeful motion, and confident
data density.

**Goal:** elevate the existing screens to a premium presence that (a) wins an ABSLI leadership demo
and (b) survives daily operator use — **"demo-first, both."** Achieved through a single upgraded
token layer and rebuilt shared components applied across the current pages. **No information
architecture changes** (the "make it a CRM" instinct is deliberately rejected — ProofLens is fully
automated; the human watches the machine, they do not act on records).

**Non-goals (explicitly out of scope for this pass):**
- New pages / entity profiles (rep, branch) — deferred to a future "entity layer" phase.
- Command palette (⌘K), saved views, new tables of data.
- Any backend, scoring, API, or data-model change.

## 2. Direction

**One token system, two moods:**
- **Light mode = "Editorial Trust"** — the default. Warm bone canvas, serif *display* face for
  headline authority, a single gold hairline as the only ornament, generous air, layered elevation.
  Boardroom-native; prints cleanly for compliance.
- **Dark mode = "Cockpit Noir"** — the demo mood. Near-black ground, glass surfaces with inset
  highlight + faint indigo bloom, verdicts as saturated signal, monospace numerals. The "live
  machine is watching" moment.
- **Density DNA from "Signal Console"** folded into both: monospace tabular numerals for all data,
  compact-but-breathable table rows, tighter interaction affordances.

Because dark mode already exists, this is not "light vs dark" — the two are two faces of one
identity. Reference mockup (approved): the three-direction comparison artifact rendered on Mission
Control with representative data.

## 3. Foundation — `frontend/src/styles/tokens.css`

`tokens.css` remains the single source of truth. Additions/expansions (all CSS custom properties;
**no framework or Tailwind-config rewrite** beyond mapping new tokens):

### 3.1 Typography
- Add a serif **display** face via `next/font` (build-time, no CDN runtime dependency): **Newsreader**
  (recommended — editorial, compliance-safe). *Fraunces* is the more characterful alternative;
  decision recorded as Newsreader unless changed during implementation.
- Keep **Geist Sans** (body) — already in use. Add **Geist Mono** for numerals.
- Define a modular **type scale** with named roles as tokens + Tailwind utilities:
  `display` (serif, headlines), `title`, `body`, `body-sm`, `label` (uppercase, +tracking),
  `mono` (tabular numerals). Each role fixes size / weight / line-height / letter-spacing.
- **Default data numerals** to `font-variant-numeric: tabular-nums`.
- Editorial uses the serif display for page titles and key figures' context; Noir uses tight sans
  headings + mono numerals (serif optional, secondary).

### 3.2 Elevation & materiality
- Expand elevation from 2 → **4 levels** (`--shadow-0/1/2/3`).
  - Light: layered soft shadows (existing style, extended).
  - Dark (Noir): glass — `inset 0 1px 0 rgba(255,255,255,.05)` top-highlight + a faint indigo
    bloom on primary panels; deeper drop shadows.
- Add a **`--hairline-gold`** token; its ONLY sanctioned use remains the 2px underline beneath the
  masthead logo (existing brand rule — unchanged, not expanded).

### 3.3 Motion
- Add motion tokens: `--dur-fast/base/slow`, `--ease-out`, `--ease-spring`.
- Add two keyframes: `pulse` (live status dot) and `cascade` (incoming decision row entry).
- All motion gated behind `@media (prefers-reduced-motion: reduce)`.

### 3.4 Invariants (do NOT change)
- Verdict semantics: `clear`/`doubtful`/`suspect` hues + always paired with the word; `unassessed`
  = neutral slate (absence of assessment, not a risk grade).
- Crimson scope: masthead/sidebar header + primary buttons only, accent ≤10%.
- AA contrast on every color pair (light and dark). New pairs must be verified.

## 4. Signature Elements

Three ownable "tells" that make the product recognizable:
1. **Verdict ring / seal** — elevate the existing `ScoreRing` into *the* motif: score + band encoded
   in one mark. Primary use in the decision drawer and Live Score Theater (`/present`, `/analyze`).
2. **Gold hairline** under the masthead — the single brand ornament.
3. **Live pulse** — the "auto-scoring, in real time" cue on Mission Control's live status.

## 5. Shared Components (the bulk of the work)

Rebuild these to the new scale (`frontend/src/components/ui/` and layout/domain components).
Interfaces/props unchanged where possible — this is a visual refit, not an API change.

| Component | Treatment |
|---|---|
| `Card` / `CardHeader` | New elevation + header type; serif title in Editorial, tight sans in Noir. |
| `MetricCard` | Large mono tabular number; semantic **delta chip** (arrow + `up/flat/down` color); uppercase tracked label. |
| Verdict `pill` / badge | Refined; score in mono; correct light + dark (Noir) variants. |
| Tables — `ResultsTable`, Ledger, History | Signal density: compact rows, tabular numeric columns, sticky header, hover state, aligned rhythm. |
| `Sidebar` / `Topbar` | Masthead + gold hairline; refined nav active state; tenant chip. |
| Buttons / inputs | Accent-driven; **visible keyboard focus ring** on every interactive element. |
| Charts (Recharts) | Area fills, faint grid, emphasized endpoint, on-brand palette; tabular-nums axes. |
| `DecisionStream` rows | Avatar/initials, name+branch, verdict pill+score, reason, mono timestamp; cascade-in for fresh rows. |

## 6. Dark Mode = Cockpit Noir

The `.dark` token block in `tokens.css` is re-derived as the Noir treatment (near-black ground,
glass panels, indigo-glow accent, saturated verdict signal). No separate theme system, no new
provider — the existing `next-themes` toggle simply reveals a well-crafted dark identity.

## 7. Application Order (skin-only, per surface)

1. **Mission Control** (`/mission-control`) — the flagship / demo surface, done first and best.
2. **Analytics** (`/analytics`, `/team`).
3. **Ledger** + **History**.
4. **Analyze** (`/analyze`) + **Present** (`/present`) — verdict ring shines here.
5. **DSE**, **Settings**, **Methodology**.

Each surface: apply tokens, upgraded components, spacing/type/depth; **no structural change**.

## 8. Motion Pass

- Mission Control: live pulse + incoming-row cascade on the stream.
- Metric count-up on load (reuse the Phase-3 reveal engine — `revealSchedule`/`useScoreReveal`).
- Restrained in Editorial (quiet), more alive in Noir (glow, pulse).
- Everything reduced-motion safe.

## 9. Rollout, Testing & Guardrails

- **Preview:** ship behind the DigitalOcean droplet preview
  (`prooflens.68-183-94-47.sslip.io`); A/B the demo look before any durable prod cutover.
- **Testing:** extend the existing vitest suite with component/interaction tests for the rebuilt
  primitives (MetricCard delta, verdict pill variants, table density, focus visibility). Keep
  `tsc + eslint + build` green. CI note: pin/observe `ruff` — irrelevant here (frontend), but the
  frontend lint/build gate must stay green.
- **Accessibility:** AA contrast on all new pairs (light + dark); visible focus; reduced motion.
- **Brand guardrails (enforced in review):** crimson ≤10% and scoped; verdict color always with the
  word; gold hairline only under the masthead.
- **Backend:** untouched. No migrations, no API changes.

## 10. Success Criteria

- Side-by-side, the new Mission Control reads as a premium product, not an admin dashboard.
- Light mode is boardroom-safe and prints cleanly; dark mode is demo-grade.
- No regression: all routes 200 on preview; vitest + tsc + eslint + build green; brand rules intact.
- One coherent token system drives both moods — no per-page one-off styling.

## 11. Risks & Mitigations

- **Two moods = more work than one skin.** Mitigate by sequencing: nail tokens + Mission Control
  in both modes first; later surfaces inherit.
- **Serif display could feel off-brand.** Mitigate: Newsreader is restrained; validate on Mission
  Control before rolling out; Fraunces is the fallback lever, single-face swap.
- **Motion overreach reads as "AI-generated."** Mitigate: motion is scarce and purposeful; Editorial
  stays quiet; strict reduced-motion.
- **Contrast regressions in Noir glass.** Mitigate: verify every new dark pair against AA; tokens
  file already documents contrast intent.
