"use client";

import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/api/hooks";
import type { HealthState } from "@/lib/api/types";

const LABEL: Record<HealthState, string> = {
  ok: "Backend healthy",
  degraded: "Backend degraded (DB unreachable)",
  down: "Backend unreachable",
  loading: "Checking backend…",
};

// Verdict colors are reserved for verdicts; health uses its own neutral+state
// palette and ALWAYS pairs the dot with a label/tooltip (never colour alone).
const DOT: Record<HealthState, string> = {
  ok: "bg-ok",
  degraded: "bg-warn",
  down: "bg-danger",
  loading: "bg-text-muted",
};

export function HealthDot() {
  const { state } = useHealth();
  return (
    <div
      className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5"
      title={LABEL[state]}
      role="status"
      aria-label={LABEL[state]}
    >
      <span className="relative flex h-2 w-2">
        {state === "ok" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
        )}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", DOT[state])} />
      </span>
      <span className="hidden text-caption font-medium text-text-secondary sm:inline">
        {state === "ok" ? "Healthy" : state === "degraded" ? "Degraded" : state === "down" ? "Offline" : "…"}
      </span>
    </div>
  );
}
