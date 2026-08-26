import { cn } from "@/lib/utils";
import { BAND_META } from "@/lib/verdict";
import type { Band } from "@/lib/api/types";

/**
 * Verdict band — ALWAYS the word paired with its colour (never colour alone).
 * Optional `score` is rendered in mono/tabular after the band word (suppressed for Unassessed).
 */
export function VerdictBadge({
  band,
  score,
  size = "md",
  className,
}: {
  band: Band;
  score?: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const m = BAND_META[band];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold",
        m.bg,
        m.fg,
        size === "lg" && "px-3.5 py-1.5 text-body",
        size === "md" && "px-2.5 py-1 text-body-sm",
        size === "sm" && "px-2 py-0.5 text-caption",
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} aria-hidden />
      {band}
      {score != null && band !== "Unassessed" && (
        <span className="font-mono tabular-nums opacity-90">{Math.round(score)}</span>
      )}
    </span>
  );
}
