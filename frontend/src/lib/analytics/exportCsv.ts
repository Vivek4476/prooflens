import type { AnalyticsBucket, AnalyticsSummary, PeriodBounds } from "@/lib/api/types";

/** RFC-4180 cell quoting + spreadsheet formula-injection guard: a string cell
 *  with a leading =/+/-/@ (or control char) can execute in Excel/Sheets, so
 *  prefix a quote. Numbers/booleans are left untouched (no payload possible,
 *  and legitimate negatives stay intact). */
function csvCell(value: string | number | boolean): string {
  const s = String(value);
  const guarded = typeof value === "string" && /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return /[",\n\r]/.test(guarded) ? `"${guarded.replace(/"/g, '""')}"` : guarded;
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

function blank(): string {
  return "";
}

/**
 * A full analytics report as one sectioned CSV: the period + headline KPIs, the per-bucket
 * time series, and the top flag reasons — everything on the page's summary, so the export is
 * a usable report rather than a bare series. Pure; opens cleanly in Excel/Sheets.
 */
export function analyticsToCsv(a: AnalyticsSummary): string {
  const lines: string[] = [];

  lines.push(csvRow(["ProofLens — Analytics export"]));
  lines.push(csvRow(["Period", a.period.from, "to", a.period.to]));
  lines.push(csvRow(["Compared with", a.previous_period.from, "to", a.previous_period.to]));
  lines.push(blank());

  // Headline KPIs
  lines.push(csvRow(["Summary metric", "value"]));
  lines.push(csvRow(["Total scored", a.total]));
  lines.push(csvRow(["Suspect rate (%)", a.suspect_pct]));
  lines.push(csvRow(["Avg score", a.avg_score]));
  lines.push(csvRow(["Duplicates caught", a.duplicates_caught]));
  if (a.system_health) {
    lines.push(csvRow(["Scored without content check (%)", a.system_health.scored_without_content_pct ?? ""]));
    lines.push(csvRow(["Median time-to-score (ms)", a.system_health.median_processing_ms ?? ""]));
  }
  lines.push(blank());

  // Time series (same data the trend / band-mix charts plot)
  lines.push(csvRow(["Time series"]));
  lines.push(csvRow([...HEADERS]));
  for (const b of a.buckets) {
    lines.push(
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
  }
  lines.push(blank());

  // Top flag reasons (aggregate; % of flagged verdicts, clear excluded)
  const flagged = a.top_reasons.filter((r) => r.reason_code !== "clear");
  const totalFlagged = flagged.reduce((s, r) => s + r.count, 0) || 1;
  lines.push(csvRow(["Top flag reasons"]));
  lines.push(csvRow(["reason", "count", "pct_of_flags"]));
  for (const r of flagged) {
    lines.push(csvRow([r.short_label, r.count, Math.round((r.count / totalFlagged) * 1000) / 10]));
  }

  return lines.join("\n") + "\n";
}
