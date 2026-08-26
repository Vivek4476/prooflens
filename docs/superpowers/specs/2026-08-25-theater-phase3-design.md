# Phase 3 — Live Score Theater

**Date:** 2026-08-25
**Status:** Design approved; ready for implementation plan
**Branch:** `feature/theater-phase3` (stacked on `feature/analytics-phase2` / PR #30)
**Precedes:** builds on Phase 1 (copilot summary, verdict components) and the Glass Cockpit spec §3.

---

## 1. Context

The `/analyze` flow is **~95% built**: `ImageUploader` (drop/preview/validate), a staged-reveal state
machine (idle → scoring → reveal @ 260ms/step → verdict), `PipelineStepper` (6 real checks: exif →
sharpness → uniqueness → recapture → content → fusion), an animated `ScoreRing`, `ChecksList` evidence,
framer-motion wired (`MotionConfig` provider), and the sync `POST /v1/score` response carrying every
check with a real **`latency_ms`**. Phase 3 is an **elevation**, not a rebuild.

Goal: turn the reveal into a genuinely dramatic "watch it think, land on a verdict" moment, and expose it
in two surfaces — the everyday `/analyze` tool **and** a fullscreen **Present** mode for stakeholder demos —
both driven by one shared reveal engine.

---

## 2. The units

### A. `useScoreReveal(result)` hook *(the shared reveal engine)*
Lifts the staged-reveal state machine out of `analyze/page.tsx` into a reusable hook. Given a
`ScoreResponse` (with `checks[]` + per-check `latency_ms`), it computes a **reveal schedule** and exposes
`{ phase: "idle"|"scoring"|"revealing"|"verdict", activeStage: number, stageStates: StageState[],
verdictShown: boolean }`. Pacing:
- Reveal order = `PIPELINE_STAGES` (exif→…→content→fusion).
- Each stage dwells **proportional to its check's `latency_ms`** (the vision `content` check dwells
  longest), but the TOTAL reveal is compressed to a watchable window (target ~2.8s, clamp each stage to
  [180ms, 900ms]) so a 12s real score still reads as a tight ~3s reveal.
- `prefers-reduced-motion` → no staggering: jump straight to `verdict`.
- The **pure schedule function** `revealSchedule(checks) -> {stageKey, delayMs}[]` is unit-testable in
  isolation (no timers/React).

### B. Elevated `PipelineStepper`
Add framer-motion to the existing stepper: each stage row does a slide+fade entrance as it activates, the
active check gets a subtle pulse/glow, and the tick "lands" when it completes. Same `states` prop contract
(backward-compatible) so `/analyze`'s current call keeps working; motion is additive and reduced-motion-safe.

### C. `VerdictReveal` *(the payoff beat)*
The dramatic landing: `ScoreRing` draws (0→score), `VerdictBadge` + reason snap in, and the **copilot
summary** fades/types in beneath. Props: `{ result: ScoreResponse }`. Reused by both surfaces.

### D. `ScoreStage`
Composes `useScoreReveal` → elevated `PipelineStepper` → `VerdictReveal` (+ a staggered `ChecksList`
reveal after the verdict). Props: `{ result: ScoreResponse | null, pending: boolean, size?: "inline"|"stage" }`.
This is the single thing both surfaces render; `size="stage"` scales type/spacing up for fullscreen.

### E. `/analyze` — elevated in place
Recompose the page's right pane to render `<ScoreStage size="inline" .../>` instead of the inline
stepper+result blocks. Uploader/button/error states unchanged. The page keeps owning the `useMutation`
call to `api.score`; it passes `result`/`pending` down to `ScoreStage`.

### F. Present mode — `/present`
A fullscreen, minimal-chrome route: centered `<ScoreStage size="stage">`, a compact uploader, and a
**sample-photo quick-start** — a small strip of bundled example images (genuine + fraud) so a demo needs no
file fumbling. Picking a sample or uploading runs the same `api.score` path. Reached from a "Present"
affordance on `/analyze` (and by URL). Not in the main NAV (it's a mode, like `/dse`/`/team`).
**Sample images are a content dependency:** ship the wiring; the real JPEGs go in `frontend/public/samples/`
(genuine photos must be real — a good VLM correctly flags synthetic stand-ins). If none are present, the
quick-start strip hides and Present still works via upload.

### G. Backend — return `copilot_summary` from `/v1/score`
`score_bytes` (Phase 1) already generates `copilot_summary` and persists it, but the sync response dict
omits it. Add `"copilot_summary": copilot_summary` to that returned dict, and `copilot_summary?: string | null`
to the `ScoreResponse` type. One-line each; no new generation.

---

## 3. Architecture & data flow

```
/analyze  ─┐                         ┌─ ImageUploader (reuse)
           ├─ api.score(file) ──► ScoreResponse ──► useScoreReveal(result)
/present  ─┘   (POST /v1/score, now incl. copilot_summary)        │
                                                                   ▼
                                            ScoreStage → PipelineStepper (elevated)
                                                       → VerdictReveal (ScoreRing+band+copilot)
                                                       → ChecksList (staggered)
```

- **New units:** `lib/analyze/revealSchedule.ts` (pure) + `lib/analyze/useScoreReveal.ts` (hook);
  `components/analyze/VerdictReveal.tsx`, `components/analyze/ScoreStage.tsx`; motion added to
  `components/analyze/PipelineStepper.tsx`; `app/(app)/present/page.tsx`.
- **Changed:** `app/(app)/analyze/page.tsx` (recompose to `ScoreStage`); `lib/api/types.ts`
  (`ScoreResponse.copilot_summary?`); `src/prooflens/api/scoring.py` (add field to response dict).
- **Reused unchanged:** `ImageUploader`, `ScoreRing`, `VerdictBadge`, `ChecksList`, `StateIcon`, framer-motion.

## 4. Error handling & edge cases
- **Reduced motion:** `useScoreReveal` skips staging → verdict immediately; `PipelineStepper`/`VerdictReveal`
  motion is `motion-safe` only.
- **Backend fallback / unavailable vision:** `backend_note` still surfaces; an Unassessed result reveals as
  its own band (never Clear) — reuse the band-only treatment.
- **Error (network/validation):** the uploader/page error card is unchanged; `ScoreStage` renders nothing
  when `result` is null and `pending` is false.
- **No samples present:** Present's quick-start strip is hidden; upload path still works.
- **copilot_summary null:** `VerdictReveal` falls back to `result.reason` (additive, per Phase 1).

## 5. Testing
- Pure `revealSchedule(checks)` unit tests: order = pipeline stages; vision check gets the longest dwell;
  total clamped to the target window; empty/negative latencies handled.
- `useScoreReveal` tested against a mock timer (or its pure schedule extracted and tested directly).
- Component render tests: `VerdictReveal` shows band + copilot summary (fallback to reason when null);
  `ScoreStage` renders nothing when idle. `PipelineStepper` still satisfies its existing test.
- Backend: extend a `/v1/score` test to assert `copilot_summary` is present in the response.
- `tsc` + eslint + `next build` with `/present` emitted.

## 6. Out of scope / deferred
- Real streaming of per-check progress (the sync response already carries everything; the reveal is a
  faithful client-side re-pacing, not a fake — checks and latencies are real).
- Camera capture on web (upload only, unchanged).
- Real sample JPEGs are a content task (wiring ships; images dropped in later).
- Auto-play/kiosk loop for Present (could be a follow-up; Phase 3 ships manual pick + upload).

## 7. Decisions log
- ✅ Elevate `/analyze` AND add `/present`, both over one shared `ScoreStage`/`useScoreReveal` engine.
- ✅ Pace the reveal by real `latency_ms`, clamped to a watchable ~2.8s window; reduced-motion → instant.
- ✅ Return `copilot_summary` from `/v1/score` (already generated) so the verdict beat can show it.
- ✅ Present is a mode (not in NAV); sample photos optional, gated on real images in `public/samples/`.
- ✅ Stacked on Phase 2; PR stacks on #30.
