import type { AnalyticsSummary } from "@/lib/api/types";
import { MIN_PREV_N, relativeChangePct } from "./deltas";
import { formatCount } from "@/lib/format";

export type InsightSeverity = "info" | "warn" | "high";

export interface Insight {
  id: string;
  text: string; // full sentence, ready to render — plain language, no jargon
  severity: InsightSeverity;
}

const MAX_INSIGHTS = 5;

/**
 * Rule 1: suspect-rate delta >= 20% relative AND >= 10 absolute suspects in current period.
 * Same small-sample basis as the KPI cards: if `previous.total` is below MIN_PREV_N, the
 * prior period can't be trusted as a comparison basis, so no relative-% claim is made
 * (matches computeDelta's insufficientHistory guard — never contradicts the KPI cards).
 */
function suspectRateShift(a: AnalyticsSummary): Insight | null {
  if (a.previous.total < MIN_PREV_N) return null;
  const cur = a.band_distribution.Suspect;
  const prev = a.previous.suspect;
  if (cur < 10) return null;
  const rel = relativeChangePct(cur, prev);
  if (!Number.isFinite(rel)) return null;
  if (Math.abs(rel) < 20) return null;
  const rising = rel > 0;
  return {
    id: "suspect-rate-shift",
    severity: rising ? "high" : "info",
    text: rising
      ? `Suspect volume rose ${Math.round(rel)}% vs the previous period (${formatCount(cur)} vs ${formatCount(prev)}).`
      : `Suspect volume fell ${Math.round(Math.abs(rel))}% vs the previous period (${formatCount(cur)} vs ${formatCount(prev)}).`,
  };
}

/** Rule 2: a single top reason accounts for >= 30% of all flagged (non-clear) verdicts. */
function dominantReason(a: AnalyticsSummary): Insight | null {
  const flagged = a.top_reasons.filter((r) => r.reason_code !== "clear");
  const totalFlagged = flagged.reduce((s, r) => s + r.count, 0);
  if (totalFlagged === 0) return null;
  const top = flagged[0];
  const share = (top.count / totalFlagged) * 100;
  if (share < 30) return null;
  return {
    id: "dominant-reason",
    severity: "warn",
    text: `"${top.short_label}" accounts for ${Math.round(share)}% of flagged verdicts (${formatCount(top.count)} of ${formatCount(totalFlagged)}).`,
  };
}

/** Rule 3: avg-score delta >= 5 pts AND previous-period n >= 30. */
function avgScoreShift(a: AnalyticsSummary): Insight | null {
  if (a.previous.total < 30) return null;
  const diff = a.avg_score - a.previous.avg_score;
  if (Math.abs(diff) < 5) return null;
  const rising = diff > 0;
  return {
    id: "avg-score-shift",
    severity: rising ? "info" : "warn",
    text: rising
      ? `Average score improved ${diff.toFixed(1)} pts vs the previous period.`
      : `Average score dropped ${Math.abs(diff).toFixed(1)} pts vs the previous period.`,
  };
}

/**
 * Rule 4: duplicates_caught relative delta >= 20% (needs previous.duplicates_caught —
 * passed in explicitly since it isn't on `previous`). `prevN` is the same
 * `previous.total` basis the KPI cards use for their insufficient-history guard —
 * duplicates_caught has no sample size of its own, so we borrow the period's overall
 * prior-sample size to decide whether the prior period is trustworthy at all.
 */
function duplicatesShift(current: number, previous: number, prevN: number): Insight | null {
  if (prevN < MIN_PREV_N) return null;
  if (current < 5 && previous < 5) return null; // both negligible, not worth a bullet
  const rel = relativeChangePct(current, previous);
  if (!Number.isFinite(rel)) return null;
  if (Math.abs(rel) < 20) return null;
  const rising = rel > 0;
  return {
    id: "duplicates-shift",
    severity: rising ? "warn" : "info",
    text: rising
      ? `Duplicate captures rose ${Math.round(rel)}% vs the previous period (${formatCount(current)} vs ${formatCount(previous)}).`
      : `Duplicate captures fell ${Math.round(Math.abs(rel))}% vs the previous period (${formatCount(current)} vs ${formatCount(previous)}).`,
  };
}

export function computeInsights(
  a: AnalyticsSummary,
  prevDuplicatesCaught: number | null,
): Insight[] {
  const candidates = [
    suspectRateShift(a),
    dominantReason(a),
    avgScoreShift(a),
    prevDuplicatesCaught == null
      ? null
      : duplicatesShift(a.duplicates_caught, prevDuplicatesCaught, a.previous.total),
  ].filter((x): x is Insight => x !== null);

  // Stable order: high severity first, then warn, then info; cap at 5.
  const order: Record<InsightSeverity, number> = { high: 0, warn: 1, info: 2 };
  candidates.sort((x, y) => order[x.severity] - order[y.severity]);
  return candidates.slice(0, MAX_INSIGHTS);
}

export const NO_SHIFTS_FALLBACK = "No significant shifts this period.";
