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
    <div
      className={cn(
        "card group flex flex-col gap-2 p-5 hover:shadow-2 hover:-translate-y-0.5 transition-all duration-300 cursor-default select-none",
        accent && "ring-1 ring-border-strong"
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-caption font-medium uppercase tracking-wide text-text-muted group-hover:text-text-secondary transition-colors duration-200">
          {label}
        </span>
        {Icon && (
          <div
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg bg-surface-2 text-text-muted transition-all duration-200 group-hover:bg-brand-crimson/10 group-hover:text-brand-crimson",
              accent && "bg-brand-crimson/10 text-brand-crimson"
            )}
          >
            <Icon size={14} />
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-display leading-none tabular-nums text-text transition-colors duration-300">
          {value}
        </span>
        {suffix && <span className="text-body-sm text-text-muted">{suffix}</span>}
      </div>
      {sub && <span className="text-caption text-text-muted">{sub}</span>}
    </div>
  );
}
