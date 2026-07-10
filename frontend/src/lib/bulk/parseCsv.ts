// Pure CSV parsing + column-mapping for the Bulk upload module. No dependencies,
// no DOM — handles the LSQ export shape (quoted fields, commas-in-quotes, CRLF).

export interface ParsedCsv {
  headers: string[];
  rows: Record<string, string>[];
}

/**
 * Split one CSV text into rows of raw string cells, honoring RFC-4180 quoting:
 * a quoted field may contain commas, newlines, and CRLF; "" inside a quoted
 * field is an escaped literal quote. Handles trailing-newline / CRLF input.
 */
function tokenize(csv: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;
  let i = 0;
  const n = csv.length;

  function endCell() {
    row.push(cell);
    cell = "";
  }
  function endRow() {
    endCell();
    rows.push(row);
    row = [];
  }

  while (i < n) {
    const ch = csv[i];

    if (inQuotes) {
      if (ch === '"') {
        if (csv[i + 1] === '"') {
          cell += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      cell += ch;
      i += 1;
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (ch === ",") {
      endCell();
      i += 1;
      continue;
    }
    if (ch === "\r") {
      // Treat CRLF and bare CR as a single row break.
      if (csv[i + 1] === "\n") i += 1;
      endRow();
      i += 1;
      continue;
    }
    if (ch === "\n") {
      endRow();
      i += 1;
      continue;
    }
    cell += ch;
    i += 1;
  }

  // Flush a trailing cell/row (input doesn't end with a line break).
  if (cell.length > 0 || row.length > 0) {
    endRow();
  }

  // Drop wholly-blank trailing rows (a single empty cell from a trailing newline).
  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}

/**
 * Parse a CSV string into a header list + array of header-keyed row objects.
 * Rows shorter than the header are padded with "" for missing trailing columns.
 */
export function parseCsv(csv: string): ParsedCsv {
  const raw = tokenize(csv);
  if (raw.length === 0) return { headers: [], rows: [] };

  const headers = raw[0].map((h) => h.trim());
  const rows: Record<string, string>[] = [];
  for (let r = 1; r < raw.length; r++) {
    const cells = raw[r];
    const record: Record<string, string> = {};
    headers.forEach((h, idx) => {
      record[h] = cells[idx] ?? "";
    });
    rows.push(record);
  }
  return { headers, rows };
}

export interface ColumnMapping {
  imageCol: string;
  repIdCol?: string;
  opportunityIdCol?: string;
}

export interface BulkRow {
  image_url: string;
  rep_id: string | null;
  opportunity_id: string | null;
}

export interface BuildBulkRowsResult {
  valid: BulkRow[];
  skipped: number;
}

/** Blank/whitespace-only reads as absent — never send an empty-string identifier. */
function normalizeCell(v: string | undefined): string | null {
  const trimmed = (v ?? "").trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Map parsed CSV rows to the POST /v1/bulk-score `rows` shape using the
 * operator's column mapping. Rows with no image URL are skipped (counted,
 * never silently vanish) rather than sent to the backend.
 */
export function buildBulkRows(
  rows: Record<string, string>[],
  mapping: ColumnMapping,
): BuildBulkRowsResult {
  const valid: BulkRow[] = [];
  let skipped = 0;

  for (const row of rows) {
    const imageUrl = normalizeCell(row[mapping.imageCol]);
    if (!imageUrl) {
      skipped += 1;
      continue;
    }
    valid.push({
      image_url: imageUrl,
      rep_id: mapping.repIdCol ? normalizeCell(row[mapping.repIdCol]) : null,
      opportunity_id: mapping.opportunityIdCol ? normalizeCell(row[mapping.opportunityIdCol]) : null,
    });
  }

  return { valid, skipped };
}
