"use client";

import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { PIPELINE_STAGES, STATE_WORD, type CheckState } from "@/lib/verdict";
import { StateIcon } from "@/components/verdict/StateIcon";

export type StageState = CheckState | "pending" | "active";

const HINT: Record<string, string> = {
  exif: "Reading capture metadata",
  sharpness: "Measuring focus",
  uniqueness: "Comparing against prior uploads",
  recapture: "Checking for screen re-photography",
  content: "Assessing the scene & people",
  fusion: "Fusing signals into a verdict",
};

/**
 * The real pipeline stages, resolving against the response's checks[]. The
 * animation is derived from real results — not a theatrical fake.
 */
export function PipelineStepper({ states }: { states: StageState[] }) {
  return (
    <ol className="space-y-1">
      {PIPELINE_STAGES.map((stage, i) => {
        const state = states[i] ?? "pending";
        const done = state !== "pending" && state !== "active";
        return (
          <li
            key={stage.key}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors",
              state === "active" && "bg-surface-2",
            )}
          >
            <div className="grid h-6 w-6 shrink-0 place-items-center">
              {state === "pending" && (
                <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
              )}
              {state === "active" && (
                <Loader2 size={18} className="animate-spin text-text-secondary" />
              )}
              {done && <StateIcon state={state as CheckState} size={18} />}
            </div>
            <div className="flex flex-1 items-center justify-between gap-3">
              <span
                className={cn(
                  "text-body-sm font-medium",
                  state === "pending" ? "text-text-muted" : "text-text",
                )}
              >
                {stage.label}
              </span>
              <span className="text-caption text-text-muted">
                {done ? STATE_WORD[state as CheckState] : state === "active" ? HINT[stage.key] : ""}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
