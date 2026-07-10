import type { BulkResultItem } from "@/lib/api/types";

/** RFC-4180 cell quoting + spreadsheet formula-injection guard.
 *  (Same pattern as src/lib/analytics/exportCsv.ts — kept file-local by design.)
 *  image_url / rep_id / error here come from an uploaded CSV, so a cell like
 *  "=cmd|..." could execute if opened in Excel/Sheets; prefix a quote. Only
 *  string cells can carry a payload — numbers/booleans are left untouched so
 *  legitimate negative values aren't mangled. */
function csvCell(value: string | number | boolean | null): string {
  const s = value === null ? "" : String(value);
  const guarded = typeof value === "string" && /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return /[",\n\r]/.test(guarded) ? `"${guarded.replace(/"/g, '""')}"` : guarded;
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
