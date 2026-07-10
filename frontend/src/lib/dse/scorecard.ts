// Pure shaping helpers for the DSE scorecard page — kept separate from components so
// the mapping/honesty logic is unit-testable without rendering recharts/SVG.
import type { DseScorecard, DseSearchResult, DseTrendPoint } from "@/lib/api/types";
import type { TrendPoint } from "@/lib/analytics/chartData";

/** Below this scored total, KPIs are real but not statistically meaningful — the
 *  scorecard shows the true small numbers with a "limited data" note rather than
 *  suppressing or fabricating a rate (mirrors ByTeamPanel's MIN_TOTAL_FOR_RATE guard,
 *  applied per-DSE instead of per-team). */
export const MIN_TOTAL_FOR_CONFIDENT_RATE = 20;

/** True when a scorecard's headline numbers should carry a small-sample caveat. */
export function isSparseDse(total: number): boolean {
  return total < MIN_TOTAL_FOR_CONFIDENT_RATE;
}

/** DSE per-bucket suspect-rate points for the reused CaptureRiskTrend-style chart.
 *  Same shape as `toTrendData` in chartData.ts (label/rate/incomplete/total) so the
 *  chart itself needs no DSE-specific branching. */
export function toDseTrendData(trend: DseTrendPoint[]): TrendPoint[] {
  return trend.map((b) => ({
    label: b.bucket_label,
    rate: b.total ? (b.suspect / b.total) * 100 : 0,
    incomplete: b.incomplete,
    total: b.total,
  }));
}

/** Manager-chain breadcrumb parts (SM -> RSM -> SRSM -> Zone -> Branch), dropping any
 *  level the hierarchy doesn't have rather than showing a fabricated placeholder.
 *  City is intentionally excluded from the breadcrumb — it's shown in KPIs context
 *  separately if needed; the breadcrumb mirrors the spec's "SM -> ... -> Branch" order. */
export function chainBreadcrumb(chain: DseScorecard["chain"]): string[] {
  return [chain.sm, chain.rsm, chain.srsm, chain.zone, chain.branch].filter(
    (v): v is string => Boolean(v && v.trim()),
  );
}

/** Search results, de-duplicated by agent_id and capped — defensive shaping in case
 *  the backend ever returns a duplicate row for the same agent (e.g. multi-branch). */
export function shapeSearchResults(results: DseSearchResult[], maxRows = 20): DseSearchResult[] {
  const seen = new Set<string>();
  const out: DseSearchResult[] = [];
  for (const r of results) {
    if (seen.has(r.agent_id)) continue;
    seen.add(r.agent_id);
    out.push(r);
    if (out.length >= maxRows) break;
  }
  return out;
}
