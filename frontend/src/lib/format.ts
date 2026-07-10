/** Thousands separators, no decimals: 2113 -> "2,113". */
export function formatCount(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/** Fixed 1 decimal for score-like values: 78.4 -> "78.4". Clamps -0 to 0. */
export function formatScore(n: number): string {
  const v = Math.round(n * 10) / 10;
  return (v === 0 ? 0 : v).toFixed(1);
}

/** Percentage with 1 decimal, no false precision: 3.0421 -> "3.0%". */
export function formatPct(n: number): string {
  const v = Math.round(n * 10) / 10;
  return `${(v === 0 ? 0 : v).toFixed(1)}%`;
}

/** Signed, worded delta for a count/percentage-point metric.
 *  formatSignedPct(3.2) -> "+3.2 pts", formatSignedPct(-1.1) -> "-1.1 pts" */
export function formatSignedPts(n: number): string {
  const v = Math.round(n * 10) / 10;
  const sign = v > 0 ? "+" : v < 0 ? "" : "±"; // toFixed keeps the "-" for negatives
  return `${v === 0 ? "±0.0" : `${sign}${v.toFixed(1)}`} pts`;
}

/** Signed relative percentage change: formatSignedRelPct(23.4) -> "+23.4%" */
export function formatSignedRelPct(n: number): string {
  const v = Math.round(n * 10) / 10;
  if (v === 0) return "±0.0%";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/** Short date for captions/axis ticks: "2026-07-08" -> "Jul 8". */
export function formatShortDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "Jun 8 – Jul 7" style range caption from two YYYY-MM-DD strings. */
export function formatDateRange(fromIso: string, toIso: string): string {
  return `${formatShortDate(fromIso)}–${formatShortDate(toIso)}`;
}
