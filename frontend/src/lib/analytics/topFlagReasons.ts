import type { TopReason } from "@/lib/api/types";

/**
 * Mirrors the backend's REASON_SHORT_LABEL (src/prooflens/engine/verdicts.py) for
 * surfaces that only have a bare reason_code (e.g. /history reading it from the
 * querystring) and no accompanying TopReason with a real short_label from the API.
 * Falls back to the raw code for any reason_code not in this list — never fabricates
 * a label, just doesn't shorten it.
 */
export const REASON_SHORT_LABEL: Record<string, string> = {
  clear: "Clear",
  recycled: "Recycled image",
  screen_recapture: "Photo of a screen",
  designed_graphic: "Designed graphic",
  no_people_or_irrelevant: "No people in scene",
  not_a_visit: "Not a visit",
  single_person: "Only one person",
  no_visit_context: "No visit in progress",
  too_blurred: "Too blurred",
  no_content_analysis: "Scored without content check",
};

export function reasonShortLabel(reasonCode: string): string {
  return REASON_SHORT_LABEL[reasonCode] ?? reasonCode;
}

/** Row-count options for the "Top flag reasons" widget dropdown. */
export type TopReasonsLimit = 5 | 10 | 20 | "all";

export const TOP_REASONS_LIMIT_OPTIONS: TopReasonsLimit[] = [5, 10, 20, "all"];

export const TOP_REASONS_LIMIT_LABELS: Record<TopReasonsLimit, string> = {
  5: "Top 5",
  10: "Top 10",
  20: "Top 20",
  all: "All",
};

/** Limits at/above which the row list scrolls internally instead of growing the card. */
const SCROLLING_LIMITS: TopReasonsLimit[] = [20, "all"];

export interface RankedReason {
  reason_code: string;
  reason: string; // verbatim verdict sentence — tooltip only, never rewritten
  short_label: string;
  count: number;
  rank: number; // 1-based
  pctOfFlags: number; // 0-100, rounded to 1 decimal, % of total flagged (clear excluded)
  barPct: number; // 0-100, width relative to the top row's count (for the neutral bar)
}

/** `clear` is a non-flag verdict — it never belongs in a "flag reasons" ranking. */
export function excludeClear(topReasons: TopReason[]): TopReason[] {
  return topReasons.filter((r) => r.reason_code !== "clear");
}

/**
 * Rank flagged reasons by count desc, compute %-of-flags (denominator excludes `clear`)
 * and a neutral bar width relative to the largest count, then slice to `limit`.
 * Order is stable for equal counts (Array.sort is stable per spec).
 */
export function rankTopReasons(topReasons: TopReason[], limit: TopReasonsLimit): RankedReason[] {
  const flagged = excludeClear(topReasons);
  const totalFlagged = flagged.reduce((sum, r) => sum + r.count, 0) || 1;
  const maxCount = Math.max(1, ...flagged.map((r) => r.count));

  const sorted = [...flagged].sort((a, b) => b.count - a.count);
  const sliced = limit === "all" ? sorted : sorted.slice(0, limit);

  return sliced.map((r, i) => ({
    reason_code: r.reason_code,
    reason: r.reason,
    short_label: r.short_label,
    count: r.count,
    rank: i + 1,
    pctOfFlags: Math.round((r.count / totalFlagged) * 1000) / 10,
    barPct: Math.round((r.count / maxCount) * 1000) / 10,
  }));
}

/** Whether the row list should scroll internally rather than grow the card's height. */
export function shouldScroll(limit: TopReasonsLimit): boolean {
  return SCROLLING_LIMITS.includes(limit);
}
