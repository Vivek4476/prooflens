// Pure bucket -> chart-data shaping for the two time-series charts (CaptureRiskTrend,
// BandMixChart). Kept separate from the components so the shaping/gating logic is
// unit-testable without rendering recharts/SVG.
import type { AnalyticsBucket, PeriodAggregate } from "@/lib/api/types";

export interface TrendPoint {
  label: string;
  rate: number;
  incomplete: boolean;
  total: number;
}

/** Suspect-rate-per-bucket points for `CaptureRiskTrend`. Buckets with total===0 chart at 0%. */
export function toTrendData(buckets: AnalyticsBucket[]): TrendPoint[] {
  return buckets.map((b) => ({
    label: b.bucket_label,
    rate: b.total ? (b.suspect / b.total) * 100 : 0,
    incomplete: b.incomplete,
    total: b.total,
  }));
}

/** The previous period's overall suspect rate, shown as a static reference line. */
export function previousPeriodRate(previous: PeriodAggregate): number {
  return previous.total ? (previous.suspect / previous.total) * 100 : 0;
}

export interface BandMixPoint {
  label: string;
  Clear: number;
  Doubtful: number;
  Suspect: number;
  Unassessed: number;
  rawClear: number;
  rawDoubtful: number;
  rawSuspect: number;
  rawUnassessed: number;
  total: number;
  incomplete: boolean;
}

/** Minimum number of data-bearing buckets before the band-mix trend is trustworthy. */
export const MIN_BAND_MIX_BUCKETS = 3;

/** Buckets with any scored volume — the only ones the band-mix chart's X-domain shows. */
export function bucketsWithData(buckets: AnalyticsBucket[]): AnalyticsBucket[] {
  return buckets.filter((b) => b.total > 0);
}

/** 100%-stacked Clear/Doubtful/Suspect/Unassessed shares (percent) for buckets with data. */
export function toBandMixData(buckets: AnalyticsBucket[]): BandMixPoint[] {
  return bucketsWithData(buckets).map((b) => {
    const sum = b.total || 1;
    return {
      label: b.bucket_label,
      Clear: (b.clear / sum) * 100,
      Doubtful: (b.doubtful / sum) * 100,
      Suspect: (b.suspect / sum) * 100,
      Unassessed: (b.unassessed / sum) * 100,
      rawClear: b.clear,
      rawDoubtful: b.doubtful,
      rawSuspect: b.suspect,
      rawUnassessed: b.unassessed,
      total: b.total,
      incomplete: b.incomplete,
    };
  });
}
