# BRAND.md — ProofLens

**The identity, personality, and visual language of the ProofLens platform.**
This document is the design constitution. It supersedes the visual-identity portions of
`docs/DESIGN_PRINCIPLES.md` (the interaction principles there still apply) and revises one
earlier rule: ABSLI crimson is no longer the interface masthead color — see §6 and §9.
Claude Code implements what is written here without making subjective design decisions.

---

## 1. Brand Positioning

**Who is this product?**
ProofLens is a Capture Integrity Platform: the trust layer between field evidence and
business decisions. Field teams capture photos as proof of work; ProofLens tells the
organization which of those captures deserve confidence and which deserve a second look.

**Why does it exist?**
Because organizations run on evidence they cannot personally witness. Thousands of field
interactions produce thousands of images, and no human can audit them all. ProofLens gives
every image a fair, consistent, explainable examination — instantly, at scale.

**What problem does it solve?**
Not "fraud detection" — that overclaims. ProofLens solves *attention allocation*: it raises
the cost of faking, catches careless deception, and directs scarce human review to the
submissions that warrant it. It scores and flags; it never blocks, and it never accuses.

**How should users feel?**
Like they have a tireless, meticulous analyst on staff — one who examines everything,
explains every conclusion in plain language, states its confidence honestly, and admits
what it cannot know. Calm. Informed. In control. Never surveilled, never policed.

**Category language.** We say "Capture Integrity," not "fraud detection." We say
"flagged for review," never "caught." We describe images, never people.

---

## 2. Brand Personality

Seven traits. Each is derived from a product truth, not chosen for flavor.

1. **Precise** — The product's value is exactness: a score, a reason, a confidence. The
   brand never uses vague language where a specific statement exists.
2. **Calm** — It fails open, never blocks, never panics. The interface has no alarms,
   no red flashing, no urgency theater. Risk is stated, not performed.
3. **Candid** — Its deepest differentiator. ProofLens says what it found *and what it
   couldn't check*. Honesty about limits is the trust strategy.
4. **Vigilant** — Quietly always-on. The brand conveys steady watchfulness — a lens,
   not a siren.
5. **Restrained** — Every element earns its place. No decoration, no gradients-for-mood,
   no mascots. Restraint reads as confidence.
6. **Assured** — It presents conclusions without hedging theatrics, and presents
   uncertainty without apology. Both are stated plainly.
7. **Invisible** — At its best, ProofLens disappears into the workflow. The verdict
   matters; the interface should not compete with it.

---

## 3. Brand Voice

**General register:** a senior analyst speaking to a colleague. Short sentences. Concrete
nouns. Active voice. No exclamation marks anywhere in the product. No "Oops!". No
enterprise jargon ("leverage," "utilize," "actionable insights"). No AI mysticism
("our advanced AI detected…").

**The one inviolable grammar rule:** describe the *image*, never the *person*.
- Right: "This image appears to be a photo of another screen."
- Wrong: "This agent submitted a fake photo."
This is a legal and ethical guardrail, not a style preference.

**Alerts / flags** — state evidence, then next step. Never dramatize.
> "Flagged: matches an image submitted on 12 Mar. Compare both in review."

**Success** — quiet confirmation, no celebration.
> "Scored. Clear — no integrity signals found."

**Errors / degraded states** — honest, specific, forward-looking.
> "Scored without content analysis — the vision service didn't respond. The score reflects
> the remaining checks; it will not be retried automatically."

**AI explanations** — always four beats: *what was found → why it matters → how confident →
what to do next.* Verdict reason strings come verbatim from `docs/VERDICT_COPY.md`; the UI
never rewrites, truncates, or paraphrases them.

**Empty states** — teaching voice, one next action (see §13).

---

## 4. Product Naming

**Evaluation of "ProofLens."** Strengths: it says exactly what the product does (a lens
that examines proof); two concrete words, instantly pronounceable in Indian and global
English; already carries internal equity (repo, docs, demos, stakeholder memory).
Weaknesses: "-Lens" is a crowded SaaS suffix, and the name is descriptive rather than
evocative — it will never carry mystery. Neither weakness is disqualifying.

**Twenty alternatives**, scored 1–5 on Distinctiveness, Clarity, Expandability (platform
future), Global pronunciation, Timelessness (max 25):

| # | Name | D | C | E | G | T | Total | Note |
|---|------|---|---|---|---|---|-------|------|
| 1 | **ProofLens** | 3 | 5 | 4 | 5 | 4 | **21** | Incumbent; descriptive, proven |
| 2 | Verity | 4 | 4 | 4 | 5 | 4 | 21 | Elegant; common word, crowded mark |
| 3 | Attest | 3 | 4 | 4 | 5 | 5 | 21 | Strong verb; hard to trademark |
| 4 | Provenance | 4 | 4 | 5 | 3 | 5 | 21 | Perfect meaning; long, hard to say fast |
| 5 | Argus | 5 | 2 | 5 | 4 | 5 | 21 | Hundred-eyed watchman; surveillance vibe risk |
| 6 | Candor | 4 | 3 | 4 | 5 | 4 | 20 | On-personality; abstract |
| 7 | Vouch | 4 | 4 | 3 | 5 | 4 | 20 | Warm; existing startups in adjacent space |
| 8 | Evident | 3 | 4 | 4 | 5 | 4 | 20 | Clean; adjective-as-name is weak |
| 9 | Intact | 3 | 4 | 4 | 5 | 4 | 20 | Integrity root; generic |
| 10 | Veracity | 3 | 4 | 4 | 4 | 4 | 19 | Meaningful; corporate flavor |
| 11 | Aperture | 4 | 3 | 4 | 4 | 4 | 19 | Beautiful metaphor; photo-brand crowding |
| 12 | Clarus | 4 | 3 | 4 | 4 | 4 | 19 | Latin-clean; forgettable |
| 13 | Tessera | 5 | 2 | 4 | 4 | 4 | 19 | Ancient ID token; needs explaining |
| 14 | Axiom | 4 | 2 | 5 | 4 | 4 | 19 | Premium sound; meaning mismatch |
| 15 | Cairn | 5 | 2 | 4 | 3 | 5 | 19 | Trail-marker of truth; obscure |
| 16 | Optica | 4 | 3 | 3 | 4 | 4 | 18 | Lens family; sounds like eyewear |
| 17 | Meridian | 3 | 2 | 5 | 4 | 4 | 18 | Expansive; says nothing about proof |
| 18 | TrueFrame | 3 | 5 | 3 | 4 | 3 | 18 | Literal; compound-name dated fast |
| 19 | Sentinel | 2 | 4 | 4 | 4 | 3 | 17 | Overused in security |
| 20 | Warrant | 3 | 3 | 3 | 5 | 3 | 17 | Legal-threat connotation |
| 21 | Bonafide | 3 | 4 | 3 | 4 | 3 | 17 | Right meaning; casual register |

**Recommendation: keep ProofLens.** It ties for the top score *before* counting its real
advantages — zero migration cost, existing stakeholder equity, and a name that never needs
explaining in a leadership room. Renaming now would be novelty spend with no clarity gain;
consistency is worth more. Platform naming pattern for future modules: **ProofLens Photo,
ProofLens Geo, ProofLens Docs, ProofLens Audit** — the platform is the brand, modules are
plain nouns. (Caveat: a formal trademark search is legal's job and required regardless of
this recommendation; if it fails, Verity and Argus are the runners-up.)

---

## 5. Logo Direction

*(Descriptions only — no drawing. Geometry specified so any designer produces the same mark.)*

**Concept A — The Lens Pair (recommended).** Two equal circles overlapping horizontally so
their centers sit one radius apart; the vesica (almond) where they intersect is filled
solid. Symbolism: one circle is the *claim*, the other the *evidence*; where they overlap
is *proof*. It encodes the product's entire logic in two shapes. Monoline stroke on the
circles (1.5 units at 24-unit grid), filled intersection. Reads at 16px. Timeless because
it is pure geometry — no trend to age out of.

**Concept B — The Focus Ring.** A single circle with a 30° gap at 45°, a small solid dot
sitting in the gap. Symbolism: a camera focus ring resolving to a verdict point. Quieter,
more abstract; risks reading as a loading spinner.

**Concept C — The Aperture P.** Hexagonal shutter blades whose negative space suggests a
"P." Clever, but clever ages; rejected on the "remembered after one viewing" test —
Concept A wins that test.

**System (Concept A):**
- **Proportions:** built on a 24×24 grid; circles r=8, centers at (8,12) and (16,12).
- **Wordmark:** "ProofLens" set in the UI typeface at 600 weight, single color, letter-spacing −1%; mark sits left of wordmark at cap height, gap = 0.5× cap height.
- **Monochrome:** the primary form. Ink on light, paper-white on dark. Color versions use Accent (see §6) only — never gradients.
- **Favicon:** the filled vesica alone (the almond shape), no circles — unmistakable at 16px.
- **App icon:** the full mark, paper-white, centered on the dark canvas color (§6), 20% padding, continuous-corner rounding.

---

## 6. Color Philosophy

Color in ProofLens is *semantic first, brand second, decorative never.* Three color
families with strict, non-overlapping jobs:

**Family 1 — Neutrals (the interface).** ~90% of every screen. Warm-neutral light theme,
true-neutral dark theme. Neutrals do the layout work: hierarchy comes from tone, spacing,
and weight — not from color.

**Family 2 — Verdict colors (the meaning).** Reserved exclusively for integrity semantics.
They may never be used decoratively, and they always appear with the verdict word
(never color alone):
- **Clear** — green `#1F9D57`: examined and unremarkable. Not "success"; *absence of signal*.
- **Doubtful** — amber `#E08A00`: worth a human's attention. Not danger; *attention*.
- **Suspect** — signal red `#DC2F45`: strong integrity signals; review first. Deliberately
  a different red from any tenant's brand red, so risk is never confused with branding.

**Family 3 — Accent (the product's hand).** One accent: **Focus Indigo `#4C5FD5`** —
interactive elements, primary buttons, links, focus rings, selection. Indigo because it
signals analysis and trust, sits far from all three verdict hues (no collision), and reads
as product, not tenant. Accent coverage ≤10% of any screen.

**Tenant brand (a guest, not a family).** The customer's identity (ABSLI crimson
`#C8102E`, sunburst logo) lives *only* in the tenant identity chip (§9) and in exported
reports' headers. It is never interface chrome, never a button, never a chart color. This
is the Stripe model: the dashboard is Stripe's; your logo marks whose data it is.

**Token set:**

| Token | Light | Dark | Job |
|---|---|---|---|
| `--canvas` | `#FAFAF9` | `#0E0E11` | Page background |
| `--surface` | `#FFFFFF` | `#17171B` | Cards, panels |
| `--surface-2` | `#F4F4F2` | `#1F1F24` | Insets, table headers |
| `--border` | `#E8E7E3` | `#2A2A30` | Hairlines only |
| `--ink` | `#17171A` | `#EDEDEF` | Primary text |
| `--ink-2` | `#5C5B57` | `#A4A3A9` | Secondary text |
| `--ink-3` | `#8F8E88` | `#6E6D74` | Captions, meta |
| `--accent` | `#4C5FD5` | `#7B8CFF` | Interaction |
| `--clear` | `#1F9D57` | `#34C77B` | Verdict: Clear |
| `--doubtful` | `#E08A00` | `#F2A93B` | Verdict: Doubtful |
| `--suspect` | `#DC2F45` | `#FF5C71` | Verdict: Suspect |
| `--tenant-brand` | per-tenant | per-tenant | Tenant chip only |

**Charts & data visualization:** default series in neutrals (`--ink-2` scale) with accent
for the highlighted series. Verdict colors appear in charts *only* when the data encodes
verdicts (band distribution). Never rainbow palettes; never color to make a chart "pop."

---

## 7. Typography

**One family: Inter** (variable), with `font-feature-settings: "tnum" 1, "cv11" 1` on all
numeric data. One family keeps the system coherent; Inter's tabular numerals make scores
and tables align like instrumentation.

**The complete scale (nothing outside it):**

| Role | Size/Line | Weight | Use |
|---|---|---|---|
| Display | 32/38 | 650 | The score, one hero number per screen |
| H1 | 22/28 | 600 | Page title (one per page) |
| H2 | 16/24 | 600 | Section headers |
| Body | 14/22 | 450 | Default text, table cells |
| Body-strong | 14/22 | 600 | Emphasis inside body — sparingly |
| Caption | 12/16 | 450 | Meta, timestamps, footnotes |

**Rhythm & rules:** labels are Caption in `--ink-3`, uppercase never (sentence case
everywhere); values are Body or Display in `--ink` — a label must never visually compete
with its value. Large numbers get whitespace equal to at least their own height above and
beside them. Tables: Body at 450, numeric columns right-aligned tabular, row height 44px.
Reading measure for prose ≤ 65ch. Weight creates hierarchy before size does; size changes
only at role boundaries.

---

## 8. Design Principles

The ten laws. Every screen is audited against them before merge.

1. **Verdict first.** The band word leads every result, list row, and export. The score
   supports; the reason explains. Never bury the verdict below the fold.
2. **Evidence is the interface.** Every conclusion is accompanied by what was found, in
   plain language. A number without a reason is a bug.
3. **One decision per screen.** Each page answers one question and offers one primary
   action. If a screen serves two decisions, it is two screens.
4. **Describe images, never people.** No copy, chart, or label may characterize an
   agent — only submissions.
5. **Color is meaning.** Verdict colors for verdicts, accent for interaction, neutrals for
   everything else. Any other use of color is decoration and is removed.
6. **Honest states only.** Never simulate analysis, fake progress, or display checks that
   didn't run. Degraded results say so. The stub backend is always labeled simulated.
7. **Tables for operations, cards for KPIs.** Operational data is dense, aligned, and
   scannable; cards exist only for the few numbers that drive today's decision.
8. **Motion communicates state.** Loading, resolution, success, navigation — nothing else
   moves. ≤250ms, ease-out, no bounce, reduced-motion respected.
9. **Whitespace is structure.** Increase spacing before adding borders; add borders before
   adding backgrounds; never card-in-card.
10. **The product is the host; the tenant is a guest.** ProofLens owns the interface;
    customer branding lives in its designated slot and nowhere else.

---

## 9. Sidebar Philosophy

**ProofLens is the hero; ABSLI is the workspace.** The sidebar is the platform's spine and
carries the platform's identity.

- **Top:** ProofLens mark + wordmark (monochrome ink), gold-free, crimson-free. This is
  the only place the logo appears in the app shell.
- **Navigation:** a single quiet list — Dashboard, Analyze, History, Review, Analytics,
  Settings. Icon (20px, 1.5px stroke) + label, 40px row height. Active state: `--surface-2`
  fill + accent text — no left border bars, no filled pills, no accent backgrounds.
  Future modules (Geo, Docs) arrive as a second labeled group, not a redesign.
- **Bottom: the tenant identity chip.** The customer's logo on a small light chip (their
  artwork assumes light backgrounds) + tenant name in Body. This is the *only* home of
  tenant branding in the shell. On a multi-tenant deployment it doubles as the workspace
  switcher.
- **Feel:** the sidebar never scrolls independently at this nav size, never collapses to
  icons by default, and contains zero badges except a single count on Review when items
  are pending — the one number that represents waiting human work.

Why this hierarchy: reviewers spend hours here; the shell must feel like a stable
instrument, not a co-branded portal. The tenant chip answers "whose data" without
letting brand crimson colonize an interface where red must mean Suspect.

---

## 10. Dashboard Philosophy

**What the generic version gets wrong:** a grid of eight metric cards is a report, not a
tool. "Images processed: 1,204" answers no question. Vanity density is the enterprise
default; we reject it.

**The ProofLens dashboard answers exactly one question: "Is today normal — and if not,
where do I look?"**

- **Hero (the one focal point):** today's Suspect rate as the Display number, with its
  delta against the trailing-30-day norm in words — "2.1% · typical" or "6.8% · above your
  usual range." Anomaly framing turns a statistic into a judgment.
- **Primary action:** Review queue — "14 awaiting review" — one accent button. Pending
  human work is the only number that demands action.
- **The signature element — the Integrity Strip:** one slim horizontal band showing today's
  verdict distribution as proportional segments (Clear/Doubtful/Suspect in verdict colors,
  labeled). Quiet, instantly readable, ownable — the one visual a leadership audience
  remembers. It replaces three pie charts.
- **Supporting:** one table — the most recent flagged submissions (band-first columns) —
  and three small KPI cards at most (images today, avg score, avg processing time). Nothing
  else. Duplicate-count, model-latency histograms, and other operator metrics live in
  Analytics and Settings, where their decision-owners look.

**Memorable = one strong judgment rendered calmly**, not many widgets rendered loudly.

---

## 11. Motion System

Motion is a status channel. Durations: **120ms** micro (hover, toggles), **200ms** standard
(reveals, dialogs), **300ms** ceiling (page transitions). Easing: `cubic-bezier(0.2, 0, 0, 1)`
(decisive ease-out). No bounce, no spring, no parallax, ever.

- **Hover:** background/tone shift only — no scale, no lift-shadows.
- **Page transitions:** 150ms fade + 4px rise on content; the shell never moves.
- **Loading:** skeletons matching final layout, one subtle shimmer; never spinners on
  full pages, never fake progress bars.
- **Analysis (the one theatrical moment, earned):** the pipeline stepper resolves each real
  check as its result arrives — state change as narrative. If results return in one
  response, steps resolve at ≤300ms intervals *derived from real check data*, clearly not
  simulated judgment.
- **The score:** counts up once, ≤500ms, then never animates again. A verdict is stable.
- **Charts:** one draw-in on mount, ≤400ms, no per-datapoint choreography.
- **Counters/badges:** update by instant swap, not rolling digits.
- `prefers-reduced-motion`: all of the above become instant state changes.

---

## 12. Illustration Style

**No photography** (stock handshakes are the insurance cliché this brand exists to avoid).
**No 3D, no Lottie mascots, no "AI brain" art** — mascots contradict Invisible; 3D ages in
eighteen months; abstract neural swooshes are the new clip art.

**One system: geometric line compositions derived from the logo.** Circles, arcs, and
vesica intersections in `--ink-3` single-weight strokes with at most one accent element —
used only in empty states, onboarding, and error pages. They extend the mark's geometry, so
every illustration is unmistakably ProofLens without a signature. Icons throughout the
product: Lucide, 20px, 1.5px stroke, `--ink-2` — never filled, never multicolor.

---

## 13. Empty States

An empty state is a teaching moment with one exit. Formula: *what this page does → why it's
empty → the one next action.* Geometry illustration (§12) above, H2 + Body, one accent
button. Never bare "No data." Never two CTAs.

- **History, first run:** "Every scored submission lands here. Nothing has been analyzed
  yet — score your first photo to start the record." → *Analyze a photo*
- **Review queue, empty:** "Doubtful and Suspect submissions wait here for a human
  decision. The queue is clear — nothing needs your judgment right now." (No CTA; an empty
  queue is the goal state, and it should feel like one.)
- **Analytics, <7 days of data:** "Trends need history. Charts unlock as scoring data
  accumulates — check back once a week of submissions has flowed through."
- **Search, no results:** "Nothing matches. Try a broader date range, or clear filters." →
  *Clear filters*

---

## 14. AI Identity

**The AI is an analyst, not a character.** No name, no avatar, no chat bubble, no
first-person "I found…". Findings are presented as the system's analysis in neutral third
person: "This image appears…", "Three integrity signals were found."

**Explaining a suspicious photo — always the four beats:**
> **Suspect · 28/100** — *"Appears to be a photo of another screen — glare and screen-edge
> detected."* Confidence: high. Recommended: compare with the agent's original submission
> in review.

**Confidence** is shown as a word + number pair — "High · 92", "Moderate · 61", "Low · 34"
— word first (humans read words), number for the record. Thresholds: High ≥80,
Moderate 50–79, Low <50. Never a lone percentage, never five-decimal precision theater.

**Uncertainty is a first-class state, stated plainly:** "Scored without content analysis —
the vision service was unavailable. This score reflects sharpness, uniqueness, and
recapture checks only." Low confidence lowers the visual emphasis of the verdict, never
hides it.

**Never:** "AI magic," "99.9% accurate," anthropomorphized apologies, or any implication a
person committed fraud. The system evaluates captures; humans evaluate people.

---

## 15. Future Vision

Five years out, ProofLens is not a dashboard someone opens — it is the integrity layer
field operations assume, the way payments assume Stripe. Modules (Photo, Geo, Docs, Audit)
share one mark, one voice, one verdict grammar; "ProofLens Clear" appears inside customers'
own tools via API and embeds. The brand grows *quieter* as it grows larger: more assumed,
less announced — an infrastructure brand whose presence is a small mark and a verdict word
that entire organizations have learned to trust. The measure of brand success in year five
is that "prooflensed" is what an ops manager calls a verified submission.

---

## Instructions for Claude Code

Implementation rules. No subjective decisions remain; where this section conflicts with
earlier documents, **this section wins.** Update `frontend/src/styles/tokens.css` and
`docs/DESIGN_PRINCIPLES.md` references to match.

### Migration notes (supersessions — apply first)
1. ABSLI crimson `#C8102E` is removed from all interface chrome (masthead, buttons,
   headers). It appears only in the tenant identity chip (sidebar bottom) and report
   exports. The gold rule under the masthead is removed.
2. Verdict Suspect changes from `#C8102E` to `#DC2F45` (dark `#FF5C71`) so risk ≠ tenant
   brand. Update `--verdict-suspect` and golden-set visual references.
3. Primary interactive color is Focus Indigo `#4C5FD5` (dark `#7B8CFF`), replacing any
   crimson-primary buttons.
4. App shell logo: ProofLens mark (per §5 Concept A geometry) + wordmark, monochrome ink.
   The ABC logo file moves to the tenant chip component.

### Color rules
- Implement the full token table from §6 as CSS custom properties; themes switch via
  `data-theme` on `<html>`. No hex values outside `tokens.css`.
- Verdict colors only where data encodes verdicts, always paired with the verdict word.
- Accent ≤10% of any screen: buttons (one primary per view), links, focus rings,
  active-nav text, selected states. Never backgrounds of large regions.
- Charts: neutral series + accent highlight; verdict palette only for band-encoded data.

### Typography rules
- Inter variable, `"tnum" 1` on any element containing data numerals.
- Only the six roles in §7's table; implement as utility classes
  (`.text-display`, `.text-h1`, `.text-h2`, `.text-body`, `.text-body-strong`,
  `.text-caption`). Any font-size not in the scale fails review.
- Numeric table columns right-aligned; labels sentence case, `--ink-3`, Caption role.

### Spacing & layout rules
- 4px base; allowed steps: 4, 8, 12, 16, 24, 32, 48, 64. No arbitrary values.
- Shell: sidebar fixed 240px; content max-width 1200px, centered; page padding 32px
  (desktop) / 16px (tablet); vertical section gap 32px; intra-card gap 16px.
- Radii: 8px controls, 12px cards, 999px pills/badges. Shadows: exactly two elevations —
  `0 1px 2px rgb(0 0 0 / 0.05)` (resting) and `0 4px 16px rgb(0 0 0 / 0.08)` (overlays).
  Nothing else. No border + shadow + background stacking; pick one separator.

### Component rules
- One component per concept, reused everywhere: `VerdictBadge` (word + color, pill,
  Caption 600), `ScoreDisplay` (Display role + "/100" Caption), `ConfidenceLabel`
  (word · number), `IntegrityStrip` (proportional band bar), `PipelineStepper`,
  `ChecksList` (renders only checks[] the backend returned), `HistoryTable`, `MetricCard`
  (max 3 per screen), `EmptyState` (illustration + H2 + Body + ≤1 CTA), `TenantChip`.
- Buttons: primary (accent fill, white text), secondary (surface + border), ghost (text).
  One primary per view. 44px min height. No icon-only buttons without tooltips.
- Tables: 44px rows, `--surface-2` header, hairline `--border` row separators, hover =
  `--surface-2` row tint. No zebra stripes, no card-per-row lists for operational data.

### Icon rules
- Lucide only, 20px default (16px inside dense tables), 1.5px stroke, `--ink-2`;
  verdict/status icons may take verdict colors. Never filled variants, never emoji in UI.

### Animation rules
- Tokens: `--dur-1: 120ms; --dur-2: 200ms; --dur-3: 300ms;
  --ease: cubic-bezier(0.2, 0, 0, 1)`. Nothing exceeds `--dur-3`.
- Permitted animations: hover tone shifts, 150ms page content fade+rise, skeletons,
  stepper state resolution, one score count-up (≤500ms), one chart draw-in (≤400ms),
  toast enter/exit. Everything else is instant.
- `prefers-reduced-motion: reduce` → all durations 0; skeletons static.

### Branding rules
- ProofLens mark per §5 geometry; monochrome in-app. Favicon = filled vesica. Tenant
  logo renders only inside `TenantChip` (light chip in dark mode) and print/PDF exports.
- Never mix tenant color into charts, buttons, or verdict UI.

### Page layout rules
- Every page: one H1, one primary action, one focal point. Dashboard per §10 exactly
  (hero anomaly number, review CTA, Integrity Strip, one table, ≤3 KPI cards).
- Results view: VerdictBadge → ScoreDisplay → verbatim reason → ChecksList inline.
  Explainability is never a separate navigation hop from a result.
- Empty states per §13 copy; error states follow §3 voice (specific, forward-looking).

### Voice rules (enforced in code review)
- All user-facing strings: sentence case, no exclamation marks, no "oops," no jargon.
- Verdict reasons rendered verbatim from the backend (`VERDICT_COPY.md` vocabulary);
  any UI truncation is a bug — wrap, don't clip.
- Copy must describe images/submissions, never agents' character or intent.
- Stub-backend verdicts always carry the visible label "Simulated — not a model judgment."

### Accessibility rules
- WCAG AA contrast in both themes (verify verdict colors on both canvases).
- Meaning never by color alone — verdict word always present.
- Full keyboard navigation; visible focus ring (2px accent outline, 2px offset).
- Interactive targets ≥44×44px. `aria-live="polite"` on score/verdict updates.
- All animation gated on reduced-motion; all images/icons carry labels or are
  `aria-hidden` when decorative.
