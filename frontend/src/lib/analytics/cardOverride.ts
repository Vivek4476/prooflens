// Pure helpers for Pain 8 (global-first per-card aggregation override) — kept
// separate from the chart components so the span-gating rule is unit-testable
// without rendering recharts/SVG. Two time-bucketed charts (CaptureRiskTrend,
// BandMixChart) use this to gate which per-card Daily/Weekly/Monthly options are
// selectable for the current page date range.
import type { Bucket } from "@/lib/api/types";

/** "Follow page" is the default — the card renders the page's global bucket
 *  data with zero extra fetches. Any other value is a genuine per-card override. */
export type CardAggChoice = "page" | Bucket;

/** Minimum inclusive day-span (from/to both YYYY-MM-DD) before Weekly/Monthly
 *  are offered as a per-card override — a 5-day range bucketed "weekly" would
 *  render one thin bar, so the option is disabled rather than producing a
 *  degenerate chart. Mirrors the small-sample discipline used elsewhere on
 *  this page (KPI deltas, hotspot ranking). */
export const MIN_DAYS_FOR_WEEKLY = 14;
export const MIN_DAYS_FOR_MONTHLY = 60;

/** Inclusive day count between two YYYY-MM-DD dates. Returns 0 if either is
 *  missing/unparseable so callers fail closed (gate disabled, not crash). */
export function spanDays(from?: string, to?: string): number {
  if (!from || !to) return 0;
  const start = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
  const msPerDay = 24 * 60 * 60 * 1000;
  const days = Math.round((end.getTime() - start.getTime()) / msPerDay) + 1;
  return Math.max(days, 0);
}

export interface BucketAvailability {
  daily: boolean;
  weekly: boolean;
  monthly: boolean;
}

/** Daily is always available; Weekly/Monthly gate to the data span. */
export function availableBuckets(from?: string, to?: string): BucketAvailability {
  const days = spanDays(from, to);
  return {
    daily: true,
    weekly: days >= MIN_DAYS_FOR_WEEKLY,
    monthly: days >= MIN_DAYS_FOR_MONTHLY,
  };
}

/** A card is "overridden" only when its choice resolves to a bucket that
 *  differs from the page's global bucket — selecting "page" is never an
 *  override, and selecting the SAME value as the global bucket is a no-op
 *  (chart still reads the page's props, no extra fetch, no chip). */
export function isOverridden(choice: CardAggChoice, globalBucket: Bucket): boolean {
  return choice !== "page" && choice !== globalBucket;
}

/** The effective bucket a card renders with: its own choice when overridden,
 *  otherwise the page's global bucket. */
export function effectiveBucket(choice: CardAggChoice, globalBucket: Bucket): Bucket {
  return choice === "page" ? globalBucket : choice;
}

export const BUCKET_LABEL: Record<Bucket, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};
