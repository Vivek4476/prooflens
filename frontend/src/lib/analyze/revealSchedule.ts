import type { CheckOutcome } from "@/lib/api/types";
import { PIPELINE_STAGES } from "@/lib/verdict";

export const REVEAL_TARGET_MS = 2800; // watchable total, regardless of real latency
export const REVEAL_MIN_MS = 180;
export const REVEAL_MAX_MS = 900;
const FUSION_WEIGHT = 400; // synthetic weight for the fusion beat (no check → no latency)

/** Per-stage dwell, paced by each check's real latency_ms, compressed to a watchable window. */
export function revealSchedule(checks: CheckOutcome[]): { key: string; dwellMs: number }[] {
  const byName = new Map(checks.map((c) => [c.name, c]));
  const weights = PIPELINE_STAGES.map((s) => {
    if (s.key === "fusion") return FUSION_WEIGHT;
    const l = byName.get(s.key)?.latency_ms;
    return Number.isFinite(l) && (l as number) > 0 ? (l as number) : 50; // floor for tiny/absent
  });
  const sum = weights.reduce((a, w) => a + w, 0) || 1;
  return PIPELINE_STAGES.map((s, i) => {
    const raw = (weights[i] / sum) * REVEAL_TARGET_MS;
    const dwellMs = Math.round(Math.max(REVEAL_MIN_MS, Math.min(REVEAL_MAX_MS, raw)));
    return { key: s.key, dwellMs };
  });
}
