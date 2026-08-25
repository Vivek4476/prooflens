# Live Score Theater — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate the existing `/analyze` staged reveal into a cinematic "watch it think → land on a verdict" experience, and expose it in a fullscreen `/present` mode — both driven by one shared reveal engine.

**Architecture:** Extract the reveal state machine out of `analyze/page.tsx` into a pure schedule fn + a `useScoreReveal` hook (paced by real per-check `latency_ms`, reduced-motion safe). Compose it into `VerdictReveal` + `ScoreStage`, rendered by both `/analyze` (inline) and `/present` (fullscreen). Backend returns the already-computed `copilot_summary` from `/v1/score`.

**Tech Stack:** Backend — FastAPI, pytest. Frontend — Next.js 15, React 18, TS, framer-motion (already wired via `MotionConfig reducedMotion="user"`), Vitest.

## Global Constraints

- **Reuse, don't rebuild:** `ImageUploader`, `ScoreRing`, `VerdictBadge`, `ChecksList`, `StateIcon`, `PipelineStepper` are reused; the reveal is re-paced, not faked (checks + latencies are real).
- **Motion is additive + reduced-motion safe:** every animation uses `useReducedMotion()`/`motion-safe`; `MotionConfig reducedMotion="user"` is already the provider. Reduced motion → verdict shows immediately, no staggering.
- **Verdict colors band-only, paired with the band word** (via `ScoreRing`/`VerdictBadge`). Unassessed reveals as its own band, never Clear.
- **Copilot summary is additive:** `VerdictReveal` falls back to `result.reason` when `copilot_summary` is null.
- **`/present` is a mode, not in NAV** (like `/dse`, `/team`).
- **Tests:** backend `.venv/bin/python -m pytest`; frontend `npm test` from `frontend/` (Vitest globals OFF — import from `"vitest"`). `git add <specific files>`, never `-A`.

---

## File Structure

**Backend:**
- `src/prooflens/api/scoring.py` *(modify)* — add `payload["copilot_summary"]` in `score_bytes` (~line 157).

**Frontend:**
- `src/lib/api/types.ts` *(modify)* — `ScoreResponse.copilot_summary?: string | null`.
- `src/lib/analyze/revealSchedule.ts` *(create)* — pure pacing.
- `src/lib/analyze/useScoreReveal.ts` *(create)* — the reveal hook.
- `src/components/analyze/VerdictReveal.tsx` *(create)* — the payoff beat.
- `src/components/analyze/ScoreStage.tsx` *(create)* — the shared stage.
- `src/components/analyze/PipelineStepper.tsx` *(modify)* — motion elevation (keeps `states` contract).
- `src/app/(app)/analyze/page.tsx` *(modify)* — recompose to `ScoreStage`.
- `src/app/(app)/present/page.tsx` *(create)* — fullscreen mode.

---

## Task 1: Backend — return `copilot_summary` from `/v1/score`

**Files:**
- Modify: `src/prooflens/api/scoring.py` (`score_bytes`, the `payload` dict ~lines 152-158)
- Test: `tests/integration/test_scoring_api.py`

**Interfaces:**
- Consumes: `copilot_summary` (already computed at ~line 145 via `summarize_decision(verdict)`).
- Produces: `/v1/score` response dict includes `"copilot_summary": str | None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_scoring_api.py  (add near the other /v1/score tests)
def test_score_response_includes_copilot_summary(client):
    r = _upload(client, "meeting.jpg")   # reuse the file's existing _upload helper
    assert r.status_code == 200
    body = r.json()
    assert "copilot_summary" in body
    assert body["copilot_summary"] is None or isinstance(body["copilot_summary"], str)
```

- [ ] **Step 2: Run → fail** (KeyError/assert: `copilot_summary` not in body)

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py::test_score_response_includes_copilot_summary -q`

- [ ] **Step 3: Add the field**

In `src/prooflens/api/scoring.py` `score_bytes`, immediately before `return payload`, add:

```python
    payload["copilot_summary"] = copilot_summary
```

(`copilot_summary` is already in scope from the earlier `copilot_summary = summarize_decision(verdict)`.)

- [ ] **Step 4: Run → pass + full suite**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -q` → PASS
Run: `.venv/bin/python -m pytest -q` → green; `.venv/bin/ruff check src/prooflens/api/scoring.py && .venv/bin/mypy src/prooflens` → clean

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(score): return copilot_summary from /v1/score"
```

---

## Task 2: Reveal engine — `revealSchedule` (pure) + `useScoreReveal` hook

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (`ScoreResponse`)
- Create: `frontend/src/lib/analyze/revealSchedule.ts`, `frontend/src/lib/analyze/useScoreReveal.ts`
- Test: `frontend/src/lib/analyze/revealSchedule.test.ts`

**Interfaces:**
- Consumes: `CheckOutcome` (`latency_ms`), `PIPELINE_STAGES`, `checkState`, `bandState`, `StageState` (`components/analyze/PipelineStepper`), `ScoreResponse`.
- Produces: `revealSchedule(checks) -> { key: string; dwellMs: number }[]` (6 entries, pipeline order, total ≈ TARGET clamped, each in [MIN,MAX]); `useScoreReveal(result, pending) -> { phase: "idle"|"scoring"|"revealing"|"verdict"; stepperStates: StageState[]; verdictShown: boolean }`.

- [ ] **Step 1: Add the type field**

In `frontend/src/lib/api/types.ts`, add to `interface ScoreResponse`:

```typescript
  copilot_summary?: string | null;
```

- [ ] **Step 2: Write the failing pure test**

```typescript
// frontend/src/lib/analyze/revealSchedule.test.ts
import { describe, it, expect } from "vitest";
import { revealSchedule, REVEAL_TARGET_MS, REVEAL_MIN_MS, REVEAL_MAX_MS } from "./revealSchedule";
import type { CheckOutcome } from "@/lib/api/types";

const chk = (name: string, latency: number | null): CheckOutcome =>
  ({ name, available: true, score: 50, summary: "", metric: null, data: {}, latency_ms: latency } as CheckOutcome);

describe("revealSchedule", () => {
  const checks = [
    chk("exif", 20), chk("sharpness", 30), chk("uniqueness", 40),
    chk("recapture", 25), chk("content", 3200),
  ];
  it("returns one entry per pipeline stage, in order, incl. fusion", () => {
    const s = revealSchedule(checks);
    expect(s.map((x) => x.key)).toEqual(["exif", "sharpness", "uniqueness", "recapture", "content", "fusion"]);
  });
  it("gives the slowest check (content) the longest dwell", () => {
    const s = revealSchedule(checks);
    const content = s.find((x) => x.key === "content")!.dwellMs;
    const exif = s.find((x) => x.key === "exif")!.dwellMs;
    expect(content).toBeGreaterThan(exif);
  });
  it("clamps every dwell to [MIN, MAX] and total near target", () => {
    const s = revealSchedule(checks);
    for (const x of s) { expect(x.dwellMs).toBeGreaterThanOrEqual(REVEAL_MIN_MS); expect(x.dwellMs).toBeLessThanOrEqual(REVEAL_MAX_MS); }
    const total = s.reduce((a, x) => a + x.dwellMs, 0);
    expect(total).toBeLessThanOrEqual(REVEAL_TARGET_MS + 6 * REVEAL_MAX_MS);
  });
  it("handles missing/negative latencies without NaN", () => {
    const s = revealSchedule([chk("exif", null), chk("content", -5)]);
    for (const x of s) expect(Number.isFinite(x.dwellMs)).toBe(true);
  });
});
```

- [ ] **Step 3: Run → fail** (cannot find module `./revealSchedule`)

Run (frontend/): `npm test -- revealSchedule`

- [ ] **Step 4: Implement the pure schedule**

```typescript
// frontend/src/lib/analyze/revealSchedule.ts
import type { CheckOutcome } from "@/lib/api/types";
import { PIPELINE_STAGES } from "@/lib/verdict";

export const REVEAL_TARGET_MS = 2800; // watchable total, regardless of real latency
export const REVEAL_MIN_MS = 180;
export const REVEAL_MAX_MS = 900;
const FUSION_WEIGHT = 400; // synthetic weight for the fusion beat (no check → no latency)

/** Per-stage dwell, paced by each check's real latency_ms, compressed to a watchable window. */
export function revealSchedule(checks: CheckOutcome[]): { key: string; dwellMs: number }[] {
  const byName = new Map(checks.map((c) => [c.name, c]));
  const weights = PIPELINE_STAGES.map((s) => {
    if (s.key === "fusion") return FUSION_WEIGHT;
    const l = byName.get(s.key)?.latency_ms;
    return Number.isFinite(l) && (l as number) > 0 ? (l as number) : 50; // floor for tiny/absent
  });
  const sum = weights.reduce((a, w) => a + w, 0) || 1;
  return PIPELINE_STAGES.map((s, i) => {
    const raw = (weights[i] / sum) * REVEAL_TARGET_MS;
    const dwellMs = Math.round(Math.max(REVEAL_MIN_MS, Math.min(REVEAL_MAX_MS, raw)));
    return { key: s.key, dwellMs };
  });
}
```

- [ ] **Step 5: Run → pass**

Run (frontend/): `npm test -- revealSchedule` → PASS

- [ ] **Step 6: Implement the hook** (extracts the page's state machine; replaces fixed 260ms with schedule dwells)

```typescript
// frontend/src/lib/analyze/useScoreReveal.ts
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import type { ScoreResponse } from "@/lib/api/types";
import type { StageState } from "@/components/analyze/PipelineStepper";
import { PIPELINE_STAGES, bandState, checkState } from "@/lib/verdict";
import { revealSchedule } from "./revealSchedule";

export type RevealPhase = "idle" | "scoring" | "revealing" | "verdict";

export function useScoreReveal(
  result: ScoreResponse | null,
  pending: boolean,
): { phase: RevealPhase; stepperStates: StageState[]; verdictShown: boolean } {
  const reduce = useReducedMotion();
  const [revealed, setRevealed] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const realStates = useMemo<StageState[]>(() => {
    if (!result) return [];
    return PIPELINE_STAGES.map((stage) => {
      if (stage.key === "fusion") return bandState(result.band);
      const c = result.checks.find((x) => x.name === stage.key);
      return c ? checkState(c) : "skip";
    });
  }, [result]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!result) { setRevealed(-1); return; }
    if (reduce) { setRevealed(PIPELINE_STAGES.length - 1); return; } // instant
    const sched = revealSchedule(result.checks);
    setRevealed(-1);
    let i = 0;
    const tick = () => {
      setRevealed(i);
      if (i >= PIPELINE_STAGES.length - 1) return;
      const dwell = sched[i]?.dwellMs ?? 300;
      i += 1;
      timer.current = setTimeout(tick, dwell);
    };
    timer.current = setTimeout(tick, 120); // small lead-in
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [result, reduce]);

  const revealing = !!result && revealed < PIPELINE_STAGES.length - 1;
  const stepperStates = useMemo<StageState[]>(() => {
    if (pending) return PIPELINE_STAGES.map((s) => (s.key === "content" ? "active" : "pending"));
    if (result) return PIPELINE_STAGES.map((_, i) =>
      i <= revealed ? realStates[i] : i === revealed + 1 ? "active" : "pending");
    return PIPELINE_STAGES.map(() => "pending");
  }, [pending, result, revealed, realStates]);

  const phase: RevealPhase = pending ? "scoring" : !result ? "idle" : revealing ? "revealing" : "verdict";
  return { phase, stepperStates, verdictShown: phase === "verdict" };
}
```

- [ ] **Step 7: tsc + commit**

Run (frontend/): `npx tsc --noEmit` → 0 errors; `npx eslint src/lib/analyze src/lib/api/types.ts` → clean
```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/analyze/revealSchedule.ts frontend/src/lib/analyze/revealSchedule.test.ts frontend/src/lib/analyze/useScoreReveal.ts
git commit -m "feat(fe): latency-paced reveal schedule + useScoreReveal hook"
```

---

## Task 3: `VerdictReveal` component (the payoff beat)

**Files:**
- Create: `frontend/src/components/analyze/VerdictReveal.tsx`
- Test: `frontend/src/components/analyze/VerdictReveal.test.tsx`

**Interfaces:**
- Consumes: `ScoreRing`, `VerdictBadge`, `ScoreResponse`, `formatMs`.
- Produces: `VerdictReveal({ result }: { result: ScoreResponse })` — verdict header, score ring, reason, **copilot summary (fallback to reason)**, backend note, saved-report link.

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/analyze/VerdictReveal.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerdictReveal } from "./VerdictReveal";
import type { ScoreResponse } from "@/lib/api/types";

const base = {
  band: "Suspect", score: 18, reason: "Reused image", reason_code: "recycled",
  rubric_version: "v3", checks: [], result_id: "OPP-1", processing_ms: 1200,
  backend: "nvidia", backend_is_real: true,
} as unknown as ScoreResponse;

describe("VerdictReveal", () => {
  it("shows the band and the copilot summary when present", () => {
    render(<VerdictReveal result={{ ...base, copilot_summary: "Scored Suspect because reused." }} />);
    expect(screen.getByText("Suspect")).toBeInTheDocument();
    expect(screen.getByText(/reused\./i)).toBeInTheDocument();
  });
  it("falls back to reason when copilot_summary is null", () => {
    render(<VerdictReveal result={{ ...base, copilot_summary: null }} />);
    expect(screen.getByText("Reused image")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run → fail**  (frontend/): `npm test -- VerdictReveal`

- [ ] **Step 3: Implement** (elevates the existing `ResultPanel`, adding the copilot summary beat)

```tsx
// frontend/src/components/analyze/VerdictReveal.tsx
"use client";

import { motion, useReducedMotion } from "framer-motion";
import { AlertCircle, ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { formatMs } from "@/lib/utils";
import type { ScoreResponse } from "@/lib/api/types";

export function VerdictReveal({ result }: { result: ScoreResponse }) {
  const reduce = useReducedMotion();
  const entrance = reduce
    ? {}
    : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.22 } };
  return (
    <motion.div className="outline-none" {...entrance}>
      <Card className="p-6">
        <div className="mb-5 flex items-center justify-between">
          <VerdictBadge band={result.band} size="lg" />
          <div className="flex items-center gap-1.5 text-caption text-text-muted">
            <Clock size={13} />{formatMs(result.processing_ms)}
          </div>
        </div>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
          <ScoreRing score={result.score} band={result.band} />
          <div className="flex-1">
            <p className="text-h2 leading-snug text-text">{result.reason}</p>
            <motion.p
              className="mt-2 text-body-sm leading-relaxed text-text-secondary"
              {...(reduce ? {} : { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { delay: 0.5 } })}
            >
              {result.copilot_summary ?? result.reason}
            </motion.p>
            <p className="mt-3 text-caption text-text-muted">
              Scored by <span className="font-medium text-text-secondary">{result.backend}</span>
              {result.backend_is_real ? "" : " (deterministic demo model)"}
            </p>
            {result.backend_note && (
              <p className="mt-2 flex items-start gap-1.5 text-caption text-warn">
                <AlertCircle size={13} className="mt-0.5 shrink-0" />{result.backend_note}
              </p>
            )}
            <Link href={`/verdict/${result.result_id}`}
              className="mt-3 inline-flex items-center gap-1 text-caption font-medium text-text-secondary hover:text-text">
              View saved report <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
```

- [ ] **Step 4: Run → pass + tsc/eslint**

Run (frontend/): `npm test -- VerdictReveal` → PASS; `npx tsc --noEmit`; `npx eslint src/components/analyze/VerdictReveal.tsx src/components/analyze/VerdictReveal.test.tsx` → clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/analyze/VerdictReveal.tsx frontend/src/components/analyze/VerdictReveal.test.tsx
git commit -m "feat(fe): VerdictReveal — score ring + band + copilot summary beat"
```

---

## Task 4: `ScoreStage` — the shared stage

**Files:**
- Create: `frontend/src/components/analyze/ScoreStage.tsx`
- Test: `frontend/src/components/analyze/ScoreStage.test.tsx`

**Interfaces:**
- Consumes: `useScoreReveal` (Task 2), `PipelineStepper`, `VerdictReveal` (Task 3), `ChecksList`, `Card`/`CardHeader`, `ScoreResponse`.
- Produces: `ScoreStage({ result, pending, size }: { result: ScoreResponse | null; pending: boolean; size?: "inline" | "stage" })` — renders the stepper during scoring/reveal, `VerdictReveal` + a `ChecksList` card on verdict, and nothing when idle & not pending.

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/components/analyze/ScoreStage.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScoreStage } from "./ScoreStage";

describe("ScoreStage", () => {
  it("renders nothing when idle (no result, not pending)", () => {
    const { container } = render(<ScoreStage result={null} pending={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run → fail**  (frontend/): `npm test -- ScoreStage`

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/analyze/ScoreStage.tsx
"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Card, CardHeader } from "@/components/ui/Card";
import { PipelineStepper } from "@/components/analyze/PipelineStepper";
import { VerdictReveal } from "@/components/analyze/VerdictReveal";
import { ChecksList } from "@/components/verdict/ChecksList";
import { useScoreReveal } from "@/lib/analyze/useScoreReveal";
import type { ScoreResponse } from "@/lib/api/types";

export function ScoreStage({
  result, pending, size = "inline",
}: {
  result: ScoreResponse | null; pending: boolean; size?: "inline" | "stage";
}) {
  const reduce = useReducedMotion();
  const { phase, stepperStates, verdictShown } = useScoreReveal(result, pending);
  if (phase === "idle") return null;

  const showStepper = phase === "scoring" || phase === "revealing";
  return (
    <div className={size === "stage" ? "mx-auto w-full max-w-2xl space-y-6" : "space-y-6"}>
      {showStepper && (
        <Card className="p-4">
          <PipelineStepper states={stepperStates} />
        </Card>
      )}
      {verdictShown && result && (
        <>
          <VerdictReveal result={result} />
          <motion.div
            {...(reduce ? {} : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2, delay: 0.1 } })}
          >
            <Card>
              <CardHeader title="Why this verdict" subtitle="Every check the pipeline ran, in plain terms" />
              <ChecksList checks={result.checks} rubricVersion={result.rubric_version} />
            </Card>
          </motion.div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run → pass + tsc/eslint**

Run (frontend/): `npm test -- ScoreStage` → PASS; `npx tsc --noEmit`; `npx eslint src/components/analyze/ScoreStage.tsx` → clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/analyze/ScoreStage.tsx frontend/src/components/analyze/ScoreStage.test.tsx
git commit -m "feat(fe): ScoreStage — shared reveal stage (stepper -> verdict -> checks)"
```

---

## Task 5: Elevate `/analyze` in place

**Files:**
- Modify: `frontend/src/app/(app)/analyze/page.tsx`

**Interfaces:**
- Consumes: `ScoreStage` (Task 4), `ImageUploader`, `api.score`, `useMutation`.
- Produces: the page keeps the uploader + `useMutation`, delegates all reveal/result rendering to `<ScoreStage result={mutation.data ?? null} pending={mutation.isPending} />`.

- [ ] **Step 1: Recompose the page**

Remove from `analyze/page.tsx`: the `revealed` state, `revealTimer` ref, `REVEAL_MS`, the reveal `useEffect`, the `realStates`/`stepperStates` memos, the `revealing`/`showResult`/`showStepper` derivations, the inline `ResultPanel` component, and the direct `PipelineStepper`/`ChecksList`/`ScoreRing`/`VerdictBadge` imports that are now only used by `ScoreStage`. Keep: `ImageUploader`, the `useMutation` (with its retry/`isTransient` cold-start logic — do NOT remove that), the error card, `PageHeader`, buttons. Replace the entire right-pane render (stepper card + result panel + empty state) and the full-width checks card with:

```tsx
        {mutation.isError ? (
          <ApiError onRetry={() => file && mutation.mutate(file)} />   /* keep the existing error card */
        ) : (
          <ScoreStage result={mutation.data ?? null} pending={mutation.isPending} />
        )}
```

Add `import { ScoreStage } from "@/components/analyze/ScoreStage";`. If `ScoreStage` renders `null` when idle, keep the existing `EmptyState` as a sibling shown only when `!mutation.data && !mutation.isPending && !mutation.isError`.

> The `onSuccess: () => setRevealed(-1)` in the mutation is no longer needed (the hook owns reveal state) — remove it. Verify no other code referenced the removed state.

- [ ] **Step 2: Verify**

Run (frontend/): `npx tsc --noEmit` → 0 errors; `npx eslint src/app/\(app\)/analyze` → clean (remove any now-unused imports); `npm test` → existing suite green; `npm run build` → succeeds, `/analyze` still emitted.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(app\)/analyze/page.tsx
git commit -m "refactor(fe): /analyze renders shared ScoreStage (reveal engine extracted)"
```

---

## Task 6: `/present` fullscreen mode + Present affordance

**Files:**
- Create: `frontend/src/app/(app)/present/page.tsx`
- Modify: `frontend/src/app/(app)/analyze/page.tsx` (add a "Present" link)

**Interfaces:**
- Consumes: `ScoreStage` (size="stage"), `ImageUploader`, `api.score`, `useMutation`.
- Produces: `PresentPage` at `/present` — fullscreen, centered `ScoreStage`, compact uploader, optional sample-photo strip; a "Present" link from `/analyze`.

- [ ] **Step 1: Implement the page**

```tsx
// frontend/src/app/(app)/present/page.tsx
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ImageUploader } from "@/components/analyze/ImageUploader";
import { Button } from "@/components/ui/Button";
import { ScoreStage } from "@/components/analyze/ScoreStage";
import { api } from "@/lib/api/client";

const SAMPLES: { label: string; src: string }[] = [
  // Real JPEGs go in frontend/public/samples/. If none exist, this strip renders
  // nothing meaningful — the uploader path still works. See spec §2.F.
];

export default function PresentPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: (f: File) => api.score(f) });

  function pick(f: File) {
    setFile(f); setPreview(URL.createObjectURL(f));
  }
  async function scoreSample(src: string) {
    const blob = await (await fetch(src)).blob();
    const f = new File([blob], src.split("/").pop() || "sample.jpg", { type: blob.type });
    pick(f); mutation.mutate(f);
  }

  return (
    <div className="mx-auto flex min-h-[80dvh] w-full max-w-3xl flex-col items-center justify-center gap-8 py-10 text-center">
      <div>
        <h1 className="text-display text-text">ProofLens</h1>
        <p className="mt-1 text-body text-text-muted">Drop a photo — watch it get scored, live.</p>
      </div>

      {!mutation.data && !mutation.isPending && (
        <div className="w-full max-w-md space-y-4">
          <ImageUploader preview={preview} fileName={file?.name ?? null} onSelect={pick}
            onClear={() => { setFile(null); setPreview(null); }} disabled={mutation.isPending} />
          <Button variant="primary" className="w-full" disabled={!file}
            onClick={() => file && mutation.mutate(file)}>Score it</Button>
          {SAMPLES.length > 0 && (
            <div className="flex justify-center gap-3">
              {SAMPLES.map((s) => (
                <button key={s.src} onClick={() => scoreSample(s.src)}
                  className="overflow-hidden rounded-lg border border-border hover:border-border-strong">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.src} alt={s.label} className="h-16 w-16 object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <ScoreStage result={mutation.data ?? null} pending={mutation.isPending} size="stage" />

      {(mutation.data || mutation.isError) && (
        <Button variant="secondary" onClick={() => { mutation.reset(); setFile(null); setPreview(null); }}>
          Score another
        </Button>
      )}
    </div>
  );
}
```

> Confirm `ImageUploader`'s prop names (`preview`, `fileName`, `onSelect`, `onClear`, `disabled`) against the component. `/present` is NOT added to `NAV`.

- [ ] **Step 2: Add a "Present" link on `/analyze`**

In `analyze/page.tsx`'s `PageHeader` actions, add a link to `/present` (e.g. a secondary Button/Link labeled "Present mode"). Keep it minimal.

- [ ] **Step 3: Verify**

Run (frontend/): `npx tsc --noEmit`; `npx eslint src/app/\(app\)/present src/app/\(app\)/analyze`; `npm run build` → succeeds with `/present` emitted.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(app\)/present frontend/src/app/\(app\)/analyze/page.tsx
git commit -m "feat(fe): /present fullscreen Live Score Theater + Present link"
```

---

## Task 7: Motion polish — PipelineStepper stagger/glow + ChecksList reveal

**Files:**
- Modify: `frontend/src/components/analyze/PipelineStepper.tsx`

**Interfaces:**
- Consumes: framer-motion, `useReducedMotion`; keeps the existing `{ states }` prop contract.
- Produces: staged entrance + active-glow motion on `PipelineStepper` (additive, reduced-motion safe). Existing `PipelineStepper` test still passes.

- [ ] **Step 1: Elevate the stepper**

In `PipelineStepper.tsx`, wrap each `<li>` in a `motion.li` that animates on becoming non-pending, and give the `active` row a subtle pulse. Gate ALL motion behind `useReducedMotion()` (return the current static markup when reduced). Keep the `states` prop and the pending/active/done rendering identical; only add motion. Example for the active glow:

```tsx
  const reduce = useReducedMotion();
  // for the active row's icon container:
  className={cn("grid h-6 w-6 shrink-0 place-items-center",
    !reduce && state === "active" && "motion-safe:animate-pulse")}
```

and a slide+fade entrance on each row keyed by its state transition (use `motion.li` with `initial/animate` only when `!reduce`). Do not change the stage order, labels, or the `STATE_WORD`/`StateIcon` usage.

- [ ] **Step 2: Verify**

Run (frontend/): `npm test -- PipelineStepper` (if a test exists) → still green; `npx tsc --noEmit`; `npx eslint src/components/analyze/PipelineStepper.tsx`; `npm run build` → succeeds. Manual: reduced-motion OFF → staged glow; reduced-motion ON → static, verdict immediate.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/analyze/PipelineStepper.tsx
git commit -m "feat(fe): cinematic PipelineStepper motion (stagger + active glow), reduced-motion safe"
```

---

## Self-Review

**Spec coverage:** A (useScoreReveal) → Task 2; B (elevated PipelineStepper) → Task 7; C (VerdictReveal) → Task 3; D (ScoreStage) → Task 4; E (elevate /analyze) → Task 5; F (/present + samples) → Task 6; G (backend copilot_summary) → Task 1. ✅

**Placeholder scan:** no TBD/TODO. `SAMPLES = []` is an explicit, documented content-gated empty (spec §2.F: real JPEGs added later; strip hides when empty) with working upload fallback — not a placeholder for logic.

**Type consistency:** `ScoreResponse.copilot_summary?` (Task 2) consumed by `VerdictReveal` (Task 3). `useScoreReveal(result, pending) -> { phase, stepperStates, verdictShown }` (Task 2) consumed by `ScoreStage` (Task 4). `StageState` from `PipelineStepper` used by the hook + schedule. `revealSchedule` constants exported and asserted in tests. `ScoreStage({ result, pending, size })` consumed by `/analyze` (Task 5) + `/present` (Task 6).

**Deferred (documented):** real sample JPEGs (content); auto-play/kiosk loop; camera capture; streaming (the reveal is a faithful client-side re-pace of the real sync response).
