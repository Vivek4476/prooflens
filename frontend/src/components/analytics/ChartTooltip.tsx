"use client";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { cn } from "@/lib/utils";

export interface ChartTooltipRow {
  /** Row label. For band rows this MUST include the verdict word — the swatch color
   *  is never the only signal (color-blind / grayscale safety). */
  label: string;
  /** Pre-formatted value string — callers format with formatPct/formatCount/formatScore
   *  from "@/lib/format" so every chart's tooltip shows numbers the same way. */
  value: string;
  /** Verdict token color (e.g. "var(--verdict-clear)") for a small swatch next to the label. */
  swatchColor?: string;
}

export interface ChartTooltipProps {
  /** Bucket label / date shown as the tooltip's title. */
  title: string;
  /** A short qualifier appended next to the title, e.g. "(in progress)". */
  titleNote?: string;
  rows: ChartTooltipRow[];
  /** Optional footer line rendered below a divider (e.g. bucket total). */
  footer?: string;
}

/**
 * Shared recharts tooltip content for every analytics chart (Pain 2: one tooltip look
 * for the whole product). Pass as `<Tooltip content={...} />`; recharts supplies
 * `active`/`payload`, so charts should wrap this to shape their own rows and pass
 * `active` through — see CaptureRiskTrend/BandMixChart for the wiring pattern.
 */
export function ChartTooltip({ title, titleNote, rows, footer }: ChartTooltipProps) {
  const reducedMotion = usePrefersReducedMotion();
  return (
    <div
      className={cn(
        "min-w-[180px] space-y-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface)] p-3 shadow-[var(--shadow-2)]",
        !reducedMotion && "animate-tooltip-in",
      )}
    >
      <p className="text-body-sm font-semibold text-text">
        {title}
        {titleNote && <span className="ml-1.5 font-normal text-text-muted">{titleNote}</span>}
      </p>
      <div className="space-y-1">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-4 text-caption text-text-secondary"
          >
            <span className="flex items-center gap-1.5">
              {row.swatchColor && (
                <span
                  className="h-2 w-2 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: row.swatchColor }}
                />
              )}
              {row.label}
            </span>
            <span className="tabular-nums font-medium text-text">{row.value}</span>
          </div>
        ))}
      </div>
      {footer && (
        <div className="border-t border-[var(--border)] pt-1.5 text-caption text-text-muted">
          <span className="tabular-nums">{footer}</span>
        </div>
      )}
    </div>
  );
}
