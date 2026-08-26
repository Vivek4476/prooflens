# Premium Craft Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate the existing ProofLens frontend to a premium presence via one upgraded token system and rebuilt shared components — light mode = "Editorial Trust", dark mode = "Cockpit Noir" — with no IA, route, data, or backend changes.

**Architecture:** All visual identity flows from `frontend/src/styles/tokens.css` (CSS custom properties) mapped to Tailwind utilities in `tailwind.config.ts`. Shared primitives in `frontend/src/components/{ui,layout,verdict,mission,history}` are refit to the expanded scale; pages inherit the new look through those primitives. A serif display face (Newsreader) is added via `next/font`. Dark mode is re-derived as a glass "Noir" treatment on the same tokens.

**Tech Stack:** Next.js 15 (App Router) · React 18 · TypeScript · Tailwind CSS 3 (`darkMode: "class"`) · geist fonts · next/font · framer-motion · Recharts · lucide-react · next-themes · Vitest + Testing Library.

## Global Constraints

- **No new routes, no new data, no backend change.** Visual/craft layer only.
- **Verdict color is meaning:** `clear`/`doubtful`/`suspect`/`unassessed` hues appear ONLY as a verdict, always paired with the band word. Never use verdict green/amber/red for generic UI, KPIs, or deltas.
- **Metric deltas stay NEUTRAL:** a volume/score/rate movement is not a verdict — delta glyphs use a neutral (`text-text-muted`) color and a ↗/↘ arrow, never verdict green/red. (Preserves existing `MetricCard` behavior.)
- **Crimson is brand-scoped:** masthead/sidebar header + primary buttons only; accent ≤10% of surface. Interaction color is Focus Indigo (`--accent`), not crimson.
- **Gold rule:** the gold hairline (`--brand-gold`) appears ONLY as the 2px underline beneath the masthead logo — nowhere else.
- **Accessibility:** every new color pair passes AA (light AND dark); every interactive element has a visible `:focus-visible` state; all motion respects `prefers-reduced-motion`.
- **Green gate for every task:** `npm run build`, `npx tsc --noEmit`, `npx eslint .`, and `npx vitest run` must all pass before commit.
- **`tokens.css` is the single source of truth.** No hard-coded hex in components — use tokens/Tailwind utilities.

---

## File Touch Map

| File | Responsibility | Tasks |
|---|---|---|
| `src/app/layout.tsx` | Load Newsreader serif; expose `--font-newsreader` | 1 |
| `src/styles/tokens.css` | Type/elevation/motion tokens; re-derive `.dark` as Noir | 1 |
| `tailwind.config.ts` | Map fonts, type roles, 4-step shadows, motion keyframes | 1 |
| `src/app/globals.css` | `.card` elevation + glass dark; glow util; base polish | 1 |
| `src/components/ui/MetricCard.tsx` | Mono headline number; neutral delta (unchanged rule) | 2 |
| `src/components/ui/Card.tsx` | Elevation + optional serif title | 3 |
| `src/components/verdict/VerdictBadge.tsx` | Refined pill; mono score; light+dark | 4 |
| `src/components/verdict/ScoreRing.tsx` | Signature seal; dark glow | 5 |
| `src/components/ui/Button.tsx` | Variants + visible focus ring | 6 |
| `src/components/layout/{Sidebar,Topbar}.tsx`, `src/components/brand/ProofLensMasthead.tsx` | Masthead hairline; nav active state | 7 |
| `src/components/mission/DecisionStream.tsx` | Density + cascade-in motion | 8 |
| `src/components/history/ResultsTable.tsx` | Table density, tabular columns, sticky header | 9 |
| `src/lib/charts/theme.ts` (new), `src/components/ui/ChartCard.tsx` | Shared Recharts theme | 10 |
| `src/app/(app)/mission-control/page.tsx` | Flagship surface polish | 11 |
| Remaining `(app)/*/page.tsx` | Sweep + final QA | 12 |

---

## Task 1: Foundation — fonts, tokens, Tailwind, glass

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`
- Test: `frontend/src/styles/foundation.test.tsx` (create)

**Interfaces:**
- Produces: Tailwind utilities `font-serif`, `font-mono`, `text-display-lg`, `text-label`, `shadow-0`, `shadow-3`, `animate-pulse-dot`, `animate-cascade-in`; CSS vars `--dur-fast/base/slow`, `--ease-out/spring`, `--hairline-gold`, `--shadow-0/3`; component class `.card-glow`. All later tasks consume these.

- [ ] **Step 1: Add the serif display font** in `frontend/src/app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Newsreader } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

const newsreader = Newsreader({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-newsreader",
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "ABSLI Capture Integrity · ProofLens",
  description: "Image-authenticity scoring for proof-of-visit photos.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} ${newsreader.variable}`}
    >
      <body style={{ fontFamily: "var(--font-geist-sans), system-ui, sans-serif" }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Extend `tokens.css`** — append motion + elevation tokens inside `:root` (before the closing `}` at line ~64), and the Noir dark equivalents inside `.dark` (before its closing `}` at line ~105).

Into `:root`:
```css
  /* Elevation — extend to 4 levels (0 = hairline, 3 = high) */
  --shadow-0: 0 1px 0 rgba(20, 20, 18, 0.03);
  --shadow-3: 0 12px 32px rgba(20, 20, 18, 0.10), 0 4px 8px rgba(20, 20, 18, 0.05);
  /* Signature hairline — ONLY under the masthead logo */
  --hairline-gold: var(--brand-gold);
  /* Motion */
  --dur-fast: 120ms;
  --dur-base: 200ms;
  --dur-slow: 420ms;
  --ease-out: cubic-bezier(0.2, 0.7, 0.2, 1);
  --ease-spring: cubic-bezier(0.3, 1.3, 0.5, 1);
```

Into `.dark` (Cockpit Noir — deeper, glass):
```css
  --shadow-0: 0 1px 0 rgba(255, 255, 255, 0.03);
  --shadow-3: 0 18px 50px rgba(0, 0, 0, 0.6), 0 4px 12px rgba(0, 0, 0, 0.5);
```

- [ ] **Step 3: Add the `cascade-in` keyframe** to `tokens.css` (next to the existing `fadein` keyframe at line ~107):

```css
@keyframes cascade-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
@keyframes pulse-dot {
  0% { box-shadow: 0 0 0 0 var(--pulse-color, rgba(31, 157, 87, 0.5)); }
  70% { box-shadow: 0 0 0 7px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
```

- [ ] **Step 4: Map new tokens in `tailwind.config.ts`** — replace the `fontSize`, `boxShadow`, `keyframes`, `animation` blocks and add `fontFamily`:

```ts
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
        serif: ["var(--font-newsreader)", "ui-serif", "Georgia", "serif"],
      },
      fontSize: {
        "display-lg": ["2.75rem", { lineHeight: "1.05", letterSpacing: "-0.02em", fontWeight: "560" }],
        display: ["2rem", { lineHeight: "2.4rem", letterSpacing: "-0.02em", fontWeight: "600" }],
        h1: ["1.375rem", { lineHeight: "1.75rem", letterSpacing: "-0.01em", fontWeight: "600" }],
        h2: ["1.0625rem", { lineHeight: "1.4rem", fontWeight: "600" }],
        body: ["0.9375rem", { lineHeight: "1.4rem" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.2rem" }],
        label: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.08em", fontWeight: "600" }],
        caption: ["0.75rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
      },
      boxShadow: {
        0: "var(--shadow-0)",
        1: "var(--shadow-1)",
        2: "var(--shadow-2)",
        3: "var(--shadow-3)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "tooltip-in": { from: { opacity: "0", transform: "translateY(2px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "cascade-in": { from: { opacity: "0", transform: "translateY(-6px)" }, to: { opacity: "1", transform: "none" } },
        "pulse-dot": {
          "0%": { boxShadow: "0 0 0 0 var(--pulse-color, rgba(31,157,87,0.5))" },
          "70%": { boxShadow: "0 0 0 7px transparent" },
          "100%": { boxShadow: "0 0 0 0 transparent" },
        },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        "slide-up": "slide-up 200ms ease-out",
        "tooltip-in": "tooltip-in 120ms ease-out",
        "cascade-in": "cascade-in 320ms cubic-bezier(0.2,0.7,0.2,1)",
        "pulse-dot": "pulse-dot 2.2s infinite",
      },
```

- [ ] **Step 5: Add glass elevation + glow util in `globals.css`** — inside `@layer components`, after the `.card` block (line ~46):

```css
  /* Cockpit Noir: cards become glass — inset top-highlight over deeper ground */
  .dark .card {
    box-shadow: var(--shadow-2), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  /* Opt-in emphasis surface (flagship panels): faint indigo bloom in dark */
  .card-glow {
    box-shadow: var(--shadow-2);
  }
  .dark .card-glow {
    box-shadow: var(--shadow-3), 0 0 40px -12px color-mix(in srgb, var(--accent) 40%, transparent),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }
  /* Uppercase tracked label helper */
  .u-label {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
  }
```

- [ ] **Step 6: Write a smoke test** at `frontend/src/styles/foundation.test.tsx` — proves the new utilities compile and render (guards against a typo'd token silently dropping):

```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("foundation utilities", () => {
  it("applies new type + shadow + font utilities without error", () => {
    const { container } = render(
      <div className="font-serif text-display-lg shadow-3 animate-cascade-in card-glow">ProofLens</div>,
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("font-serif");
    expect(el.className).toContain("text-display-lg");
    expect(el.className).toContain("card-glow");
  });
});
```

- [ ] **Step 7: Run the gate**

Run: `cd frontend && npx vitest run src/styles/foundation.test.tsx && npx tsc --noEmit && npm run build`
Expected: test PASS; tsc clean; build succeeds (Newsreader fetched at build time).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/styles/tokens.css frontend/tailwind.config.ts frontend/src/app/globals.css frontend/src/styles/foundation.test.tsx
git commit -m "feat(design): foundation — serif display, 4-step elevation, motion tokens, Noir glass"
```

---

## Task 2: MetricCard — mono headline, neutral delta preserved

**Files:**
- Modify: `frontend/src/components/ui/MetricCard.tsx`
- Test: `frontend/src/components/ui/MetricCard.test.tsx` (create)

**Interfaces:**
- Consumes: `text-display`, `font-mono` (Task 1). Props unchanged (`label`, `value`, `suffix`, `sub`, `subDirection`, `accent`, `className`).
- Produces: unchanged public API.

- [ ] **Step 1: Write the failing test** at `frontend/src/components/ui/MetricCard.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("renders value in tabular mono and keeps the delta NEUTRAL (no verdict color)", () => {
    render(<MetricCard label="Suspect / fraud" value="6.2%" sub="+2.1 pts vs 7-day" subDirection="up" />);
    const value = screen.getByText("6.2%");
    expect(value.className).toContain("tabular-nums");
    expect(value.className).toContain("font-mono");
    const delta = screen.getByText(/2.1 pts/).closest("span")!;
    // BRAND: a rate movement is not a verdict — never verdict-suspect red/green.
    expect(delta.className).not.toMatch(/verdict/);
    expect(delta.className).toContain("text-text-secondary");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ui/MetricCard.test.tsx`
Expected: FAIL — value lacks `font-mono`.

- [ ] **Step 3: Update the value span** in `MetricCard.tsx` — line 35 becomes:

```tsx
        <span className="text-display font-mono leading-none tabular-nums text-text">{value}</span>
```

And make the label a tracked u-label (line 33):

```tsx
      <span className="u-label text-caption font-medium">{label}</span>
```

(The delta block at lines 38–44 is unchanged — arrows stay `text-text-muted`, delta text `text-text-secondary`. This is the invariant.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ui/MetricCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/MetricCard.tsx frontend/src/components/ui/MetricCard.test.tsx
git commit -m "feat(design): MetricCard mono headline + tracked label; neutral delta preserved"
```

---

## Task 3: Card — elevation + optional serif title

**Files:**
- Modify: `frontend/src/components/ui/Card.tsx`
- Test: `frontend/src/components/ui/Card.test.tsx` (create)

**Interfaces:**
- Consumes: `.card`/`.card-glow` (Task 1), `font-serif`.
- Produces: `Card` gains optional `glow?: boolean`; `CardHeader` gains optional `serif?: boolean` (default false). Existing call sites keep working (new props optional).

- [ ] **Step 1: Write the failing test** at `frontend/src/components/ui/Card.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardHeader } from "./Card";

describe("Card", () => {
  it("adds card-glow when glow is set", () => {
    const { container } = render(<Card glow>x</Card>);
    expect((container.firstChild as HTMLElement).className).toContain("card-glow");
  });
  it("CardHeader renders a serif title when serif is set", () => {
    render(<CardHeader title="Live decision stream" serif />);
    expect(screen.getByText("Live decision stream").className).toContain("font-serif");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ui/Card.test.tsx`
Expected: FAIL — `glow`/`serif` props don't exist.

- [ ] **Step 3: Implement** `frontend/src/components/ui/Card.tsx`

```tsx
import { cn } from "@/lib/utils";

export function Card({
  className,
  glow,
  children,
}: {
  className?: string;
  glow?: boolean;
  children: React.ReactNode;
}) {
  return <div className={cn("card", glow && "card-glow", className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  action,
  serif,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  serif?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div>
        <h2 className={cn("text-h2 text-text", serif && "font-serif text-h1 font-semibold tracking-tight")}>
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-caption text-text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ui/Card.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Card.tsx frontend/src/components/ui/Card.test.tsx
git commit -m "feat(design): Card glow variant + optional serif CardHeader title"
```

---

## Task 4: VerdictBadge — refined pill, mono score

**Files:**
- Modify: `frontend/src/components/verdict/VerdictBadge.tsx`
- Test: `frontend/src/components/verdict/VerdictBadge.test.tsx` (create if absent)

**Interfaces:**
- Consumes: `BAND_META` from `@/lib/verdict` (`fg`/`bg`/`dot` classes), `font-mono`.
- Produces: unchanged public API. If the component doesn't already accept a `score`, add optional `score?: number` rendered in mono after the band word.

- [ ] **Step 1: Read the current component** to learn its exact props.

Run: `sed -n '1,80p' frontend/src/components/verdict/VerdictBadge.tsx`

- [ ] **Step 2: Write the failing test** at `frontend/src/components/verdict/VerdictBadge.test.tsx` — verdict word is always present and the score (when given) is mono/tabular:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerdictBadge } from "./VerdictBadge";

describe("VerdictBadge", () => {
  it("always shows the band word and renders score in mono tabular", () => {
    render(<VerdictBadge band="Suspect" score={18} />);
    expect(screen.getByText(/Suspect/)).toBeInTheDocument();
    const score = screen.getByText("18");
    expect(score.className).toContain("font-mono");
    expect(score.className).toContain("tabular-nums");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/verdict/VerdictBadge.test.tsx`
Expected: FAIL (no `score` prop / no mono span).

- [ ] **Step 4: Implement** — keep `BAND_META`-driven `fg`/`bg`; add the optional mono score span; refine radii/padding. Preserve the "always with the word" rule. Representative body:

```tsx
import { cn } from "@/lib/utils";
import { BAND_META } from "@/lib/verdict";
import type { Band } from "@/lib/api/types";

export function VerdictBadge({ band, score, className }: { band: Band; score?: number; className?: string }) {
  const m = BAND_META[band];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-body-sm font-semibold",
        m.bg,
        m.fg,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} aria-hidden />
      {m.label}
      {score != null && band !== "Unassessed" && (
        <span className="font-mono tabular-nums opacity-90">{Math.round(score)}</span>
      )}
    </span>
  );
}
```

(Adjust to match the real prop names discovered in Step 1 — do NOT drop existing props.)

- [ ] **Step 5: Run test + typecheck**

Run: `cd frontend && npx vitest run src/components/verdict/VerdictBadge.test.tsx && npx tsc --noEmit`
Expected: PASS + clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/verdict/VerdictBadge.tsx frontend/src/components/verdict/VerdictBadge.test.tsx
git commit -m "feat(design): refined VerdictBadge with mono score, band word preserved"
```

---

## Task 5: ScoreRing — signature seal with dark glow

**Files:**
- Modify: `frontend/src/components/verdict/ScoreRing.tsx`
- Test: `frontend/src/components/verdict/ScoreRing.test.tsx` (create)

**Interfaces:**
- Consumes: `BAND_META[band].ring`, `useReducedMotion`.
- Produces: unchanged API (`score`, `band`, `size?`). Adds an optional soft `drop-shadow` glow keyed to the band color (visible mainly in dark).

- [ ] **Step 1: Write the failing test** at `frontend/src/components/verdict/ScoreRing.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreRing } from "./ScoreRing";

describe("ScoreRing", () => {
  it("renders the rounded score and applies a band-colored progress stroke", () => {
    const { container } = render(<ScoreRing score={90.6} band="Clear" />);
    expect(screen.getByText("91")).toBeInTheDocument();
    const progress = container.querySelectorAll("circle")[1];
    expect(progress.getAttribute("stroke")).toBe("var(--verdict-clear)");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/verdict/ScoreRing.test.tsx`
Expected: FAIL (module renders but assertions confirm behavior — if it passes as-is, keep it as a regression guard and proceed to Step 3 for the glow).

- [ ] **Step 3: Add the seal glow** — wrap the `<svg>` with a band-colored drop shadow via inline style on the outer div (line ~19):

```tsx
    <div
      className="relative"
      style={{ width: size, height: size, filter: `drop-shadow(0 0 10px color-mix(in srgb, ${color} 35%, transparent))` }}
    >
```

Respect reduced motion (the existing animation guards stay). The glow is static, so no extra motion gating needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/verdict/ScoreRing.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/verdict/ScoreRing.tsx frontend/src/components/verdict/ScoreRing.test.tsx
git commit -m "feat(design): ScoreRing signature seal glow (band-keyed)"
```

---

## Task 6: Button + inputs — variants and visible focus

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx` (create)

**Interfaces:**
- Consumes: `--accent`, `--brand-crimson`. Base `:focus-visible` already exists globally (globals.css) — this task adds an explicit component-level `focus-visible:` ring so buttons read as interactive even against colored fills.
- Produces: unchanged API; ensure a `primary` (crimson) and default variant both carry a visible focus ring.

- [ ] **Step 1: Read current Button** for its variant API.

Run: `sed -n '1,60p' frontend/src/components/ui/Button.tsx`

- [ ] **Step 2: Write the failing test** at `frontend/src/components/ui/Button.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("carries a visible focus-visible ring", () => {
    render(<Button>Re-run</Button>);
    expect(screen.getByRole("button").className).toContain("focus-visible:ring");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Add focus-visible ring** to the shared button class string (merge, don't remove existing classes):

```tsx
// add to the base classes:
"focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas transition-colors"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ui/Button.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx
git commit -m "feat(design): explicit visible focus ring on Button variants"
```

---

## Task 7: Masthead, Sidebar & Topbar — hairline + active state

**Files:**
- Modify: `frontend/src/components/brand/ProofLensMasthead.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/Topbar.tsx`
- Test: `frontend/src/components/brand/ProofLensMasthead.test.tsx` (create)

**Interfaces:**
- Consumes: `--hairline-gold`, `text-accent`, `bg-surface-2`.
- Produces: masthead renders exactly one gold hairline; nav active row uses `bg-surface-2 text-accent` with a left accent marker.

- [ ] **Step 1: Read the masthead** to learn its markup.

Run: `sed -n '1,60p' frontend/src/components/brand/ProofLensMasthead.tsx`

- [ ] **Step 2: Write the failing test** at `frontend/src/components/brand/ProofLensMasthead.test.tsx`

```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProofLensMasthead } from "./ProofLensMasthead";

describe("ProofLensMasthead", () => {
  it("renders exactly one gold hairline element", () => {
    const { container } = render(<ProofLensMasthead />);
    const hairlines = container.querySelectorAll('[data-hairline="gold"]');
    expect(hairlines.length).toBe(1);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/brand/ProofLensMasthead.test.tsx`
Expected: FAIL (no `data-hairline` marker yet).

- [ ] **Step 4: Add the gold hairline** under the logo in `ProofLensMasthead.tsx` (represent the underline as an explicit element for testability and precise control):

```tsx
{/* The single sanctioned gold accent — 2px underline under the product mark. */}
<span data-hairline="gold" className="mt-1 block h-0.5 w-9 rounded-full" style={{ background: "var(--hairline-gold)" }} />
```

- [ ] **Step 5: Refine the nav active state** in `Sidebar.tsx` (`SidebarInner`) — add a left accent marker to the active row (replace the active branch of the `cn(...)` at lines ~36–41):

```tsx
                active
                  ? "relative bg-surface-2 text-accent before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-0.5 before:rounded-full before:bg-accent"
                  : "text-text-secondary hover:bg-surface-2 hover:text-text",
```

- [ ] **Step 6: Run gate**

Run: `cd frontend && npx vitest run src/components/brand/ProofLensMasthead.test.tsx && npx tsc --noEmit`
Expected: PASS + clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/brand/ProofLensMasthead.tsx frontend/src/components/layout/Sidebar.tsx frontend/src/components/layout/Topbar.tsx frontend/src/components/brand/ProofLensMasthead.test.tsx
git commit -m "feat(design): masthead gold hairline + accent-marked nav active state"
```

---

## Task 8: DecisionStream — density + cascade motion

**Files:**
- Modify: `frontend/src/components/mission/DecisionStream.tsx`
- Test: extend `frontend/src/components/mission/DecisionStream.test.tsx` (exists)

**Interfaces:**
- Consumes: `animate-cascade-in` (Task 1), `newIds` set already passed to the component, `useReducedMotion`.
- Produces: fresh rows (id ∈ `newIds`) get `animate-cascade-in` only when motion is allowed; timestamps render in `font-mono`.

- [ ] **Step 1: Read the current component + test** to learn props (`items`, `newIds`, `onSelect`).

Run: `sed -n '1,80p' frontend/src/components/mission/DecisionStream.tsx && sed -n '1,60p' frontend/src/components/mission/DecisionStream.test.tsx`

- [ ] **Step 2: Write the failing test** — extend `DecisionStream.test.tsx`:

```tsx
it("applies cascade-in to fresh rows only", () => {
  const items = [{ id: "a" /* ...minimal ResultItem shape from existing test */ } as any];
  const { container } = render(<DecisionStream items={items} newIds={new Set(["a"])} onSelect={() => {}} />);
  const row = container.querySelector('[data-decision-id="a"]')!;
  expect(row.className).toContain("animate-cascade-in");
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/mission/DecisionStream.test.tsx`
Expected: FAIL (no `data-decision-id` / no cascade class).

- [ ] **Step 4: Implement** — add `data-decision-id={item.id}` to each row and the fresh-row animation class:

```tsx
const reduceMotion = useReducedMotion();
// inside the row className:
cn(
  "...existing row classes...",
  newIds.has(item.id) && !reduceMotion && "animate-cascade-in",
)
// and on the timestamp span:
className="font-mono text-caption text-text-muted tabular-nums"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/mission/DecisionStream.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/mission/DecisionStream.tsx frontend/src/components/mission/DecisionStream.test.tsx
git commit -m "feat(design): DecisionStream cascade-in on fresh rows + mono timestamps"
```

---

## Task 9: ResultsTable — density, tabular columns, sticky header

**Files:**
- Modify: `frontend/src/components/history/ResultsTable.tsx`
- Test: `frontend/src/components/history/ResultsTable.test.tsx` (create if absent)

**Interfaces:**
- Consumes: `VerdictBadge` (Task 4), `font-mono`, `bg-surface`/`border`.
- Produces: header row is sticky (`sticky top-0`); numeric cells (score, time) use `font-mono tabular-nums`; row padding tightened to the Signal density (`py-2.5`).

- [ ] **Step 1: Read the table** to learn its columns/markup.

Run: `sed -n '1,120p' frontend/src/components/history/ResultsTable.tsx`

- [ ] **Step 2: Write the failing test** at `frontend/src/components/history/ResultsTable.test.tsx` — feed one row (reuse the row shape from `DecisionStream.test.tsx`) and assert a sticky header + a tabular numeric cell:

```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultsTable } from "./ResultsTable";

describe("ResultsTable", () => {
  it("has a sticky header and tabular numeric cells", () => {
    const { container } = render(<ResultsTable items={[/* one ResultItem */] as any} />);
    expect(container.querySelector("thead")?.className).toContain("sticky");
    expect(container.querySelector("[data-cell='score']")?.className).toContain("tabular-nums");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/history/ResultsTable.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Implement** — add `className="sticky top-0 z-10 bg-surface"` to `<thead>` (or the header `<tr>`), add `data-cell="score"` + `font-mono tabular-nums` to the score cell and `font-mono tabular-nums` to the time cell, and tighten row padding to `py-2.5`. Preserve all existing columns, sorting, and links.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/history/ResultsTable.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/history/ResultsTable.tsx frontend/src/components/history/ResultsTable.test.tsx
git commit -m "feat(design): ResultsTable Signal density — sticky header, tabular numeric columns"
```

---

## Task 10: Chart theme — shared Recharts styling

**Files:**
- Create: `frontend/src/lib/charts/theme.ts`
- Modify: `frontend/src/components/ui/ChartCard.tsx` and analytics chart consumers
- Test: `frontend/src/lib/charts/theme.test.ts` (create)

**Interfaces:**
- Produces: `CHART_THEME` — `{ grid: string; axis: string; areaFill: (color: string) => string; series: string[] }`, all reading CSS vars so it tracks light/dark automatically.

- [ ] **Step 1: Write the failing test** at `frontend/src/lib/charts/theme.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { CHART_THEME } from "./theme";

describe("CHART_THEME", () => {
  it("exposes token-driven grid, axis, and a series palette (no hard-coded verdict hues for generic series)", () => {
    expect(CHART_THEME.grid).toContain("var(--");
    expect(CHART_THEME.axis).toContain("var(--");
    expect(CHART_THEME.series.length).toBeGreaterThanOrEqual(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/charts/theme.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `frontend/src/lib/charts/theme.ts`

```ts
/** Shared Recharts styling — reads CSS vars so charts track light/dark (Noir) automatically.
 *  Generic data series use the Focus-Indigo accent family, NOT verdict hues (verdict color = meaning). */
export const CHART_THEME = {
  grid: "var(--border)",
  axis: "var(--text-muted)",
  series: ["var(--accent)", "var(--brand-gold)", "var(--text-secondary)"],
  areaFill: (color: string) => `color-mix(in srgb, ${color} 14%, transparent)`,
};
```

- [ ] **Step 4: Apply to charts** — in `ChartCard.tsx` and the analytics chart components, set `<CartesianGrid stroke={CHART_THEME.grid} />`, axis `tick={{ fill: CHART_THEME.axis }}`, area `fill={CHART_THEME.areaFill(CHART_THEME.series[0])}` with an emphasized endpoint dot. Keep verdict-distribution charts on their verdict colors (that IS meaning); generic trend series use `CHART_THEME.series`.

- [ ] **Step 5: Run gate**

Run: `cd frontend && npx vitest run src/lib/charts/theme.test.ts && npx tsc --noEmit && npm run build`
Expected: PASS + clean + build ok.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/charts/theme.ts frontend/src/lib/charts/theme.test.ts frontend/src/components/ui/ChartCard.tsx frontend/src/components/analytics
git commit -m "feat(design): shared Recharts theme (token-driven, light/dark aware)"
```

---

## Task 11: Mission Control — flagship surface polish

**Files:**
- Modify: `frontend/src/app/(app)/mission-control/page.tsx`
- Modify (as needed): `frontend/src/components/mission/{AlertsPanel,DecisionMixBar,ProvenanceGauge}.tsx`

**Interfaces:**
- Consumes: every primitive from Tasks 2–10.

- [ ] **Step 1: Apply the new system to the page** — use `Card glow` on the live-stream panel; `CardHeader serif` for panel titles; add a live-pulse status element in the page header:

```tsx
<span
  className="inline-block h-2 w-2 rounded-full bg-verdict-clear animate-pulse-dot"
  style={{ ["--pulse-color" as string]: "rgba(31,157,87,0.5)" }}
  aria-hidden
/>
```

- [ ] **Step 2: Tighten the KPI grid + panel rhythm** — confirm `MetricCard` deltas remain neutral; ensure spacing uses the section rhythm (`space-y-6`, `gap-3`/`gap-6` already present).

- [ ] **Step 3: Build + visual QA both modes**

Run: `cd frontend && npm run build`
Then deploy to the droplet preview (see Task 12 recipe) and eyeball `/mission-control` in BOTH light and dark:
- Light = Editorial (bone canvas, serif titles, gold hairline present once).
- Dark = Noir (glass panels, glow on the live-stream card, verdict signal pops).
- Live pulse animates; disables under OS "reduce motion".

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/(app)/mission-control/page.tsx frontend/src/components/mission
git commit -m "feat(design): Mission Control flagship polish — glow panel, serif headers, live pulse"
```

---

## Task 12: Surface sweep + final QA

**Files:**
- Modify: `frontend/src/app/(app)/{analytics,team,ledger,history,analyze,present,dse,settings,methodology}/page.tsx` and `page.tsx` (home)

**Interfaces:**
- Consumes: all prior tasks. No new components — this is application + QA.

- [ ] **Step 1: Apply per surface** — for each page, swap ad-hoc headings to `PageHeader`/`CardHeader serif`, ensure numbers use `MetricCard`/`font-mono tabular-nums`, tables use the Task 9 treatment, charts use Task 10 theme. NO structural/route/data change. Work one page per commit if preferred.

- [ ] **Step 2: Brand-guardrail audit** — grep for violations and fix any:

```bash
cd frontend
# verdict hues must never be used as generic chrome (spot-check matches by eye):
grep -rn "verdict-" src/app src/components | grep -viE "Badge|BAND_META|MixBar|Gauge|ring|dot|distribution"
# crimson must be masthead/primary only:
grep -rn "brand-crimson" src/components src/app
```

- [ ] **Step 3: Full gate**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint . && npm run build`
Expected: all green.

- [ ] **Step 4: Deploy to droplet preview + verify both modes**

```bash
ssh root@68.183.94.47 'cd /opt/prooflens && git fetch origin -q && git checkout -- frontend/package-lock.json && git checkout feature/premium-craft-overhaul && git pull origin feature/premium-craft-overhaul && (cd frontend && npm run build) && systemctl restart prooflens-web'
```
Then check every route 200 and eyeball light + dark:
```bash
for r in "" mission-control analytics team ledger history analyze present dse settings methodology; do
  printf "/%s -> " "$r"; curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 "https://prooflens.68-183-94-47.sslip.io/$r"
done
```
Manual QA checklist: AA contrast holds in both modes; focus rings visible on tab; reduced-motion kills pulse/cascade; gold hairline appears once (masthead only); crimson only on masthead/primary.

- [ ] **Step 5: Final commit + open PR**

```bash
git add -A && git commit -m "feat(design): apply premium craft system across all surfaces + QA"
git push origin feature/premium-craft-overhaul
gh pr create --base main --title "Premium craft overhaul — Editorial Trust + Cockpit Noir" --body "Craft-only visual overhaul per docs/superpowers/specs/2026-08-26-premium-craft-overhaul-design.md. No IA/route/data/backend changes."
```

---

## Self-Review (completed)

**Spec coverage:** §3 foundation → Task 1; §4 signature (ring/hairline/pulse) → Tasks 5, 7, 11; §5 components → Tasks 2,3,4,6,8,9,10; §6 Noir dark → Task 1 (+ verified Tasks 11–12); §7 application order → Tasks 11–12; §8 motion → Tasks 1,8,11; §9 rollout/testing/guardrails → Task 12. All covered.

**Placeholder scan:** No "TBD/handle edge cases" — Tasks 4/6/8/9 begin with an explicit read step because those components' exact prop names must be honored, and provide representative real code to adapt (not a placeholder).

**Type consistency:** `Card` `glow?`, `CardHeader` `serif?`, `VerdictBadge` `score?`, `CHART_THEME` shape, `data-decision-id`, `data-hairline="gold"`, `data-cell="score"`, `animate-cascade-in`, `animate-pulse-dot`, `--pulse-color`, `card-glow`, `u-label` are used consistently across tasks.

**Invariant guard:** Neutral-delta rule (Global Constraints + Task 2 test) and verdict-color-is-meaning (Task 10 + Task 12 audit) are explicitly enforced.
