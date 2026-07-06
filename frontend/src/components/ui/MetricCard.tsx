import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/** A KPI card — headline number gets the space; label never competes with value. */
export function MetricCard({
  label,
  value,
  suffix,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  sub?: string;
  icon?: LucideIcon;
  accent?: boolean; // subtle emphasis for the single most important KPI
}) {
  return (
    <div className={cn("card flex flex-col gap-2 p-4", accent && "ring-1 ring-border-strong")}>
      <div className="flex items-center justify-between">
        <span className="text-caption font-medium uppercase tracking-wide text-text-muted">
          {label}
        </span>
        {Icon && <Icon size={15} className="text-text-muted" />}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-display leading-none tabular-nums text-text">{value}</span>
        {suffix && <span className="text-body-sm text-text-muted">{suffix}</span>}
      </div>
      {sub && <span className="text-caption text-text-muted">{sub}</span>}
    </div>
  );
}
