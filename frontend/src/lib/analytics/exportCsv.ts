import type { AnalyticsBucket, PeriodBounds } from "@/lib/api/types";

/** RFC-4180 cell quoting: wrap in quotes and double internal quotes when needed. */
function csvCell(value: string | number | boolean): string {
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvRow(cells: Array<string | number | boolean>): string {
  return cells.map(csvCell).join(",");
}

const HEADERS = [
  "bucket",
  "start",
  "end",
  "clear",
  "doubtful",
  "suspect",
  "total",
  "avg_score",
  "suspect_rate_pct",
  "incomplete",
] as const;

/** Per-bucket suspect rate as a 0–100 percentage with one decimal (0 total → 0). */
function suspectRatePct(b: AnalyticsBucket): number {
  return b.total ? Math.round((b.suspect / b.total) * 1000) / 10 : 0;
}

/**
 * Serialize the analytics time series (the trend/band-mix data) to CSV — exactly what's
 * on screen for the selected range and cadence, so an export never disagrees with the page.
 * Pure and deterministic; the DOM download is a separate thin helper.
 */
export function bucketsToCsv(buckets: AnalyticsBucket[]): string {
  const rows = buckets.map((b) =>
    csvRow([
      b.bucket_label,
      b.start,
      b.end,
      b.clear,
      b.doubtful,
      b.suspect,
      b.total,
      b.avg_score,
      suspectRatePct(b),
      b.incomplete,
    ]),
  );
  return [csvRow([...HEADERS]), ...rows].join("\n") + "\n";
}

/** A stable, human-readable file name for the export, e.g. prooflens-analytics-2026-06-10_2026-07-09.csv */
export function csvFilename(period: PeriodBounds): string {
  return `prooflens-analytics-${period.from}_${period.to}.csv`;
}
