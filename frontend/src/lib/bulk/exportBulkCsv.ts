import type { BulkResultItem } from "@/lib/api/types";

/** RFC-4180 cell quoting: wrap in quotes and double internal quotes when needed.
 *  (Same pattern as src/lib/analytics/exportCsv.ts — kept file-local by design.) */
function csvCell(value: string | number | boolean | null): string {
  const s = value === null ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvRow(cells: Array<string | number | boolean | null>): string {
  return cells.map(csvCell).join(",");
}

const HEADERS = [
  "image_url",
  "rep_id",
  "opportunity_id",
  "band",
  "score",
  "reason_code",
  "result_id",
  "error",
] as const;

/**
 * Serialize bulk-job results to CSV — exactly what the results table shows,
 * including per-row errors (never hidden). Pure and deterministic.
 */
export function bulkResultsToCsv(results: BulkResultItem[]): string {
  const rows = results.map((r) =>
    csvRow([
      r.image_url,
      r.rep_id,
      r.opportunity_id,
      r.band,
      r.score,
      r.reason_code,
      r.result_id,
      r.error,
    ]),
  );
  return [csvRow([...HEADERS]), ...rows].join("\n") + "\n";
}

/** A stable, human-readable file name for the export, e.g. prooflens-bulk-results-2026-07-10.csv */
export function bulkResultsFilename(date: Date = new Date()): string {
  const iso = date.toISOString().slice(0, 10);
  return `prooflens-bulk-results-${iso}.csv`;
}
