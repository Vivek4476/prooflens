import type { CheckOutcome } from "./api/types";

/** Phase-1 proxy for capture provenance, derived from existing checks.
 *  Full signed-capture (C2PA / Play Integrity) is a separate engine sub-project. */
export function provenanceSignal(
  checks: CheckOutcome[],
): { state: "signed" | "unsigned" | "na"; label: string } {
  const by = (n: string) => checks.find((c) => c.name === n);
  const exif = by("exif");
  const recap = by("recapture");

  if (recap && recap.available && (recap.score ?? 100) < 30) {
    return { state: "unsigned", label: "Screen recapture — unverifiable" };
  }
  if (exif) {
    if (!exif.available) return { state: "unsigned", label: "No capture metadata" };
    return (exif.score ?? 0) >= 50
      ? { state: "signed", label: "Capture metadata present" }
      : { state: "unsigned", label: "Capture metadata weak/stripped" };
  }
  return { state: "na", label: "Provenance not assessed" };
}
