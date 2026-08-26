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
