import { describe, expect, it } from "vitest";
import { excludeClear, rankTopReasons, reasonShortLabel, shouldScroll } from "./topFlagReasons";
import type { TopReason } from "@/lib/api/types";

function reason(overrides: Partial<TopReason>): TopReason {
  return {
    reason_code: "blur",
    reason: "Image failed the sharpness check.",
    short_label: "Blurry",
    count: 1,
    ...overrides,
  };
}

describe("excludeClear", () => {
  it("drops the clear reason code", () => {
    const reasons = [reason({ reason_code: "clear", count: 50 }), reason({ reason_code: "blur", count: 10 })];
    expect(excludeClear(reasons).map((r) => r.reason_code)).toEqual(["blur"]);
  });

  it("keeps everything when clear is absent", () => {
    const reasons = [reason({ reason_code: "blur" }), reason({ reason_code: "dup" })];
    expect(excludeClear(reasons)).toHaveLength(2);
  });

  it("returns an empty array when all verdicts are clear", () => {
    expect(excludeClear([reason({ reason_code: "clear" })])).toEqual([]);
  });
});

describe("rankTopReasons", () => {
  it("orders rows by count descending and assigns 1-based ranks", () => {
    const reasons = [
      reason({ reason_code: "a", count: 5 }),
      reason({ reason_code: "b", count: 20 }),
      reason({ reason_code: "c", count: 10 }),
    ];
    const ranked = rankTopReasons(reasons, "all");
    expect(ranked.map((r) => r.reason_code)).toEqual(["b", "c", "a"]);
    expect(ranked.map((r) => r.rank)).toEqual([1, 2, 3]);
  });

  it("excludes clear from both the list and the %-of-flags denominator", () => {
    const reasons = [
      reason({ reason_code: "clear", count: 1000 }),
      reason({ reason_code: "blur", count: 30 }),
      reason({ reason_code: "dup", count: 70 }),
    ];
    const ranked = rankTopReasons(reasons, "all");
    expect(ranked.map((r) => r.reason_code)).not.toContain("clear");
    // denominator is 30 + 70 = 100, not 1100
    expect(ranked.find((r) => r.reason_code === "dup")?.pctOfFlags).toBe(70);
    expect(ranked.find((r) => r.reason_code === "blur")?.pctOfFlags).toBe(30);
  });

  it("rounds %-of-flags to 1 decimal without false precision", () => {
    const reasons = [reason({ reason_code: "a", count: 1 }), reason({ reason_code: "b", count: 2 })];
    const ranked = rankTopReasons(reasons, "all");
    // 1/3 = 33.333...% -> 33.3, 2/3 = 66.666...% -> 66.7
    expect(ranked.find((r) => r.reason_code === "a")?.pctOfFlags).toBe(33.3);
    expect(ranked.find((r) => r.reason_code === "b")?.pctOfFlags).toBe(66.7);
  });

  it("slices to top 5 by default limit", () => {
    const reasons = Array.from({ length: 8 }, (_, i) => reason({ reason_code: `r${i}`, count: 8 - i }));
    const ranked = rankTopReasons(reasons, 5);
    expect(ranked).toHaveLength(5);
    expect(ranked[0].reason_code).toBe("r0");
    expect(ranked[4].reason_code).toBe("r4");
  });

  it("slices to top 10 and top 20 limits", () => {
    const reasons = Array.from({ length: 25 }, (_, i) => reason({ reason_code: `r${i}`, count: 25 - i }));
    expect(rankTopReasons(reasons, 10)).toHaveLength(10);
    expect(rankTopReasons(reasons, 20)).toHaveLength(20);
  });

  it("'all' returns every flagged row, uncapped", () => {
    const reasons = Array.from({ length: 25 }, (_, i) => reason({ reason_code: `r${i}`, count: 1 }));
    expect(rankTopReasons(reasons, "all")).toHaveLength(25);
  });

  it("does not slice away fewer rows than exist", () => {
    const reasons = [reason({ reason_code: "a", count: 1 }), reason({ reason_code: "b", count: 2 })];
    expect(rankTopReasons(reasons, 5)).toHaveLength(2);
  });

  it("computes barPct relative to the largest count among flagged reasons", () => {
    const reasons = [reason({ reason_code: "a", count: 10 }), reason({ reason_code: "b", count: 5 })];
    const ranked = rankTopReasons(reasons, "all");
    expect(ranked.find((r) => r.reason_code === "a")?.barPct).toBe(100);
    expect(ranked.find((r) => r.reason_code === "b")?.barPct).toBe(50);
  });

  it("handles an empty list without dividing by zero", () => {
    const ranked = rankTopReasons([], "all");
    expect(ranked).toEqual([]);
  });

  it("handles an all-clear list as empty (not NaN rows)", () => {
    const ranked = rankTopReasons([reason({ reason_code: "clear", count: 100 })], "all");
    expect(ranked).toEqual([]);
  });

  it("carries the verbatim reason sentence and short_label through untouched", () => {
    const reasons = [reason({ reason_code: "blur", reason: "The exact verdict sentence.", short_label: "Blurry" })];
    const [row] = rankTopReasons(reasons, "all");
    expect(row.reason).toBe("The exact verdict sentence.");
    expect(row.short_label).toBe("Blurry");
  });

  it("is stable for ties (equal counts keep source order)", () => {
    const reasons = [
      reason({ reason_code: "first", count: 5 }),
      reason({ reason_code: "second", count: 5 }),
    ];
    const ranked = rankTopReasons(reasons, "all");
    expect(ranked.map((r) => r.reason_code)).toEqual(["first", "second"]);
  });
});

describe("shouldScroll", () => {
  it("does not scroll for top 5 or top 10", () => {
    expect(shouldScroll(5)).toBe(false);
    expect(shouldScroll(10)).toBe(false);
  });

  it("scrolls for top 20 and all", () => {
    expect(shouldScroll(20)).toBe(true);
    expect(shouldScroll("all")).toBe(true);
  });
});

describe("reasonShortLabel", () => {
  it("maps known backend reason codes to their short label (mirrors REASON_SHORT_LABEL)", () => {
    expect(reasonShortLabel("recycled")).toBe("Recycled image");
    expect(reasonShortLabel("screen_recapture")).toBe("Photo of a screen");
    expect(reasonShortLabel("too_blurred")).toBe("Too blurred");
  });

  it("falls back to the raw code for an unrecognized reason_code (never fabricates a label)", () => {
    expect(reasonShortLabel("some_future_code")).toBe("some_future_code");
  });
});
