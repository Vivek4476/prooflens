import { cn } from "@/lib/utils";
import { BAND_META } from "@/lib/verdict";
import type { Band } from "@/lib/api/types";

/**
 * Verdict band — ALWAYS the word paired with its colour (never colour alone).
 */
export function VerdictBadge({ band, size = "md" }: { band: Band; size?: "sm" | "md" | "lg" }) {
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
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} aria-hidden />
      {band}
    </span>
  );
}
