import { describe, it, expect } from "vitest";
import { revealSchedule, REVEAL_TARGET_MS, REVEAL_MIN_MS, REVEAL_MAX_MS } from "./revealSchedule";
import type { CheckOutcome } from "@/lib/api/types";

const chk = (name: string, latency: number | null): CheckOutcome =>
  ({ name, available: true, score: 50, summary: "", metric: null, data: {}, latency_ms: latency } as CheckOutcome);

describe("revealSchedule", () => {
  const checks = [
    chk("exif", 20), chk("sharpness", 30), chk("uniqueness", 40),
    chk("recapture", 25), chk("content", 3200),
  ];
  it("returns one entry per pipeline stage, in order, incl. fusion", () => {
    const s = revealSchedule(checks);
    expect(s.map((x) => x.key)).toEqual(["exif", "sharpness", "uniqueness", "recapture", "content", "fusion"]);
  });
  it("gives the slowest check (content) the longest dwell", () => {
    const s = revealSchedule(checks);
    const content = s.find((x) => x.key === "content")!.dwellMs;
    const exif = s.find((x) => x.key === "exif")!.dwellMs;
    expect(content).toBeGreaterThan(exif);
  });
  it("clamps every dwell to [MIN, MAX] and total near target", () => {
    const s = revealSchedule(checks);
    for (const x of s) { expect(x.dwellMs).toBeGreaterThanOrEqual(REVEAL_MIN_MS); expect(x.dwellMs).toBeLessThanOrEqual(REVEAL_MAX_MS); }
    const total = s.reduce((a, x) => a + x.dwellMs, 0);
    expect(total).toBeLessThanOrEqual(REVEAL_TARGET_MS + 6 * REVEAL_MAX_MS);
  });
  it("handles missing/negative latencies without NaN", () => {
    const s = revealSchedule([chk("exif", null), chk("content", -5)]);
    for (const x of s) expect(Number.isFinite(x.dwellMs)).toBe(true);
  });
});
