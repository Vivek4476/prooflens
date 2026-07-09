import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

export type MetricSubDirection = "up" | "down" | "flat";

/** A KPI card — headline number gets the space; label never competes with value. */
export function MetricCard({
  label,
  value,
  suffix,
  sub,
  subDirection,
  accent,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  sub?: string;
  /**
   * Direction of the sub-line delta. Rendered as a neutral ↗/↘ glyph — never a verdict
   * colour. Verdict green/red is reserved for genuine integrity semantics (Clear/Suspect);
   * a volume or score movement is not a verdict, so it stays neutral (BRAND "colour is
   * meaning"). Omit for non-delta sub-lines (e.g. "Insufficient history for comparison").
   */
  subDirection?: MetricSubDirection;
  accent?: boolean; // subtle emphasis for the single most important KPI
}) {
  return (
    <div className={cn("card flex flex-col gap-2 p-4", accent && "ring-1 ring-border-strong")}>
      <span className="text-caption font-medium text-text-muted">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className="text-display leading-none tabular-nums text-text">{value}</span>
        {suffix && <span className="text-body-sm text-text-muted">{suffix}</span>}
      </div>
      {sub && (
        <span className="flex items-center gap-1 text-caption text-text-secondary">
          {subDirection === "up" && <ArrowUpRight aria-hidden className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
          {subDirection === "down" && <ArrowDownRight aria-hidden className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
          {sub}
        </span>
      )}
    </div>
  );
}
