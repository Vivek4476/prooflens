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
