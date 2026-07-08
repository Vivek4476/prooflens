import { formatSignedPts, formatSignedRelPct } from "@/lib/format";

export type DeltaDirection = "up" | "down" | "flat";
export type DeltaSentiment = "good" | "bad" | "neutral"; // for-integrity, not for-vanity

export interface Delta {
  direction: DeltaDirection;
  sentiment: DeltaSentiment;
  /** null when the previous-period sample is too small to trust (see MIN_PREV_N). */
  words: string | null;
  insufficientHistory: boolean;
}

export const MIN_PREV_N = 20;

/**
 * higherIsBad: true for suspect-rate-like metrics (a rise is bad for integrity);
 * false for avg-score-like metrics (a rise is good). Falling suspect rate = green;
 * rising suspect rate = red — the metric's OWN semantics decide color, not the sign.
 */
export function computeDelta(
  current: number,
  previous: number,
  prevN: number,
  opts: { higherIsBad: boolean; unit: "pts" | "pct" | "count"; minPrevN?: number },
): Delta {
  const minN = opts.minPrevN ?? MIN_PREV_N;
  if (prevN < minN) {
    return { direction: "flat", sentiment: "neutral", words: null, insufficientHistory: true };
  }
  const diff = current - previous;
  const direction: DeltaDirection = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  const rising = diff > 0;
  const sentiment: DeltaSentiment =
    direction === "flat" ? "neutral" : rising === opts.higherIsBad ? "bad" : "good";
  const worded =
    opts.unit === "count"
      ? `${diff > 0 ? "+" : ""}${Math.round(diff)} vs previous period`
      : opts.unit === "pts"
        ? `${formatSignedPts(diff)} vs previous period`
        : `${formatSignedRelPct(diff)} vs previous period`;
  return { direction, sentiment, words: worded, insufficientHistory: false };
}

/** Relative change for the ≥20% relative threshold rule used by insights.ts. */
export function relativeChangePct(current: number, previous: number): number {
  if (previous === 0) return current === 0 ? 0 : Infinity;
  return ((current - previous) / previous) * 100;
}
