import { describe, expect, it } from "vitest";

import type { AnalyticsGroup } from "@/lib/api/types";
import { rankHotspots } from "./hotspots";

function group(node: string, total: number, suspect_rate: number): AnalyticsGroup {
  return {
    node,
    total,
    clear: Math.round(total * (1 - suspect_rate)),
    doubtful: 0,
    suspect: Math.round(total * suspect_rate),
    avg_score: 75,
    suspect_rate,
    share: 0,
  };
}

const OPTS = { minTotal: 20, maxRows: 8 };

describe("rankHotspots", () => {
  it("excludes the Unmapped node from the ranking and reports its total separately", () => {
    const r = rankHotspots(
      [group("Unmapped", 28, 0.5), group("Branch A", 100, 0.04), group("Branch B", 100, 0.06)],
      OPTS,
    );
    expect(r.ranked.map((g) => g.node)).toEqual(["Branch B", "Branch A"]);
    expect(r.ranked.some((g) => g.node === "Unmapped")).toBe(false);
    expect(r.unmappedTotal).toBe(28);
  });

  it("excludes nodes below the volume threshold and counts them in belowCount", () => {
    const r = rankHotspots(
      [group("Big", 50, 0.9), group("Tiny", 2, 1.0), group("Small", 19, 0.8)],
      OPTS,
    );
    expect(r.ranked.map((g) => g.node)).toEqual(["Big"]); // Tiny(2) and Small(19) are below 20
    expect(r.belowCount).toBe(2);
  });

  it("ranks eligible nodes by suspect rate descending", () => {
    const r = rankHotspots(
      [group("Low", 100, 0.01), group("High", 100, 0.09), group("Mid", 100, 0.05)],
      OPTS,
    );
    expect(r.ranked.map((g) => g.node)).toEqual(["High", "Mid", "Low"]);
  });

  it("caps the ranking at maxRows", () => {
    const many = Array.from({ length: 12 }, (_, i) => group(`B${i}`, 100, i / 100));
    const r = rankHotspots(many, { minTotal: 20, maxRows: 5 });
    expect(r.ranked).toHaveLength(5);
    expect(r.ranked[0].node).toBe("B11"); // highest rate first
  });

  it("returns a safe non-zero maxRate even when nothing ranks", () => {
    const r = rankHotspots([group("Tiny", 3, 1.0), group("Unmapped", 40, 0.5)], OPTS);
    expect(r.ranked).toHaveLength(0);
    expect(r.belowCount).toBe(1);
    expect(r.unmappedTotal).toBe(40);
    expect(r.maxRate).toBeGreaterThan(0); // never divide bar widths by zero
  });

  it("reports zero unmapped when there is no Unmapped node", () => {
    const r = rankHotspots([group("Branch A", 100, 0.04)], OPTS);
    expect(r.unmappedTotal).toBe(0);
    expect(r.ranked.map((g) => g.node)).toEqual(["Branch A"]);
  });
});
