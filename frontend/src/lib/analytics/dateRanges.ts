export type RangePreset = "7d" | "30d" | "90d" | "month" | "custom";

export interface ResolvedRange {
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
}

/** Resolve a preset (or explicit custom bounds) to concrete YYYY-MM-DD bounds,
 *  inclusive, ending "today" (UTC) unless custom bounds are given. */
export function resolvePreset(
  preset: RangePreset,
  today: Date,
  custom?: { start_date?: string; end_date?: string },
): ResolvedRange {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const t = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  if (preset === "custom") {
    return {
      start_date: custom?.start_date ?? iso(t),
      end_date: custom?.end_date ?? iso(t),
    };
  }
  if (preset === "month") {
    const start = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), 1));
    return { start_date: iso(start), end_date: iso(t) };
  }
  const days = preset === "7d" ? 6 : preset === "30d" ? 29 : 89; // inclusive span
  const start = new Date(t);
  start.setUTCDate(start.getUTCDate() - days);
  return { start_date: iso(start), end_date: iso(t) };
}

export const RANGE_PRESET_LABELS: Record<RangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  month: "This month",
  custom: "Custom range",
};

export const DEFAULT_PRESET: RangePreset = "30d";
export const DEFAULT_BUCKET = "daily" as const;
