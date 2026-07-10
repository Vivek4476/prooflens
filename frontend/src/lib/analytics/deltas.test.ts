import { describe, expect, it } from "vitest";

import { computeDelta, MIN_PREV_N, relativeChangePct } from "./deltas";

describe("computeDelta", () => {
  it("returns insufficientHistory when prevN < MIN_PREV_N, regardless of diff", () => {
    const result = computeDelta(100, 10, MIN_PREV_N - 1, { higherIsBad: true, unit: "pct" });
    expect(result).toEqual({
      direction: "flat",
      sentiment: "neutral",
      words: null,
      insufficientHistory: true,
    });
  });

  it("treats prevN exactly at MIN_PREV_N as sufficient (boundary inclusive)", () => {
    const result = computeDelta(50, 40, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(result.insufficientHistory).toBe(false);
  });

  it("respects a custom minPrevN override", () => {
    const result = computeDelta(50, 40, 5, { higherIsBad: true, unit: "pct", minPrevN: 10 });
    expect(result.insufficientHistory).toBe(true);
    expect(result.words).toBeNull();
  });

  it("suspect-rate rising (higherIsBad: true) is sentiment bad", () => {
    const result = computeDelta(30, 20, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(result.direction).toBe("up");
    expect(result.sentiment).toBe("bad");
  });

  it("suspect-rate falling (higherIsBad: true) is sentiment good", () => {
    const result = computeDelta(10, 20, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(result.direction).toBe("down");
    expect(result.sentiment).toBe("good");
  });

  it("avg-score rising (higherIsBad: false) is sentiment good", () => {
    const result = computeDelta(80, 70, MIN_PREV_N, { higherIsBad: false, unit: "pts" });
    expect(result.direction).toBe("up");
    expect(result.sentiment).toBe("good");
  });

  it("avg-score falling (higherIsBad: false) is sentiment bad", () => {
    const result = computeDelta(60, 70, MIN_PREV_N, { higherIsBad: false, unit: "pts" });
    expect(result.direction).toBe("down");
    expect(result.sentiment).toBe("bad");
  });

  it("zero diff is neutral/flat regardless of higherIsBad", () => {
    const bad = computeDelta(50, 50, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(bad.direction).toBe("flat");
    expect(bad.sentiment).toBe("neutral");

    const good = computeDelta(50, 50, MIN_PREV_N, { higherIsBad: false, unit: "pts" });
    expect(good.direction).toBe("flat");
    expect(good.sentiment).toBe("neutral");
  });

  it("words uses formatSignedPts for unit 'pts'", () => {
    const result = computeDelta(75, 70, MIN_PREV_N, { higherIsBad: false, unit: "pts" });
    expect(result.words).toBe("+5.0 pts vs previous period");
  });

  it("words uses formatSignedRelPct on the raw diff for unit 'pct'", () => {
    // Note: computeDelta's "pct" branch words the raw (current - previous) diff,
    // not a relative percentage — relativeChangePct is a separate helper.
    const result = computeDelta(65, 50, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(result.words).toBe("+15.0% vs previous period");
  });

  it("words uses a rounded signed integer for unit 'count'", () => {
    const rising = computeDelta(45, 40, MIN_PREV_N, { higherIsBad: true, unit: "count" });
    expect(rising.words).toBe("+5 vs previous period");

    const falling = computeDelta(35, 40, MIN_PREV_N, { higherIsBad: true, unit: "count" });
    expect(falling.words).toBe("-5 vs previous period");
  });

  it("insufficientHistory is false once prevN passes the guard, even with zero diff", () => {
    const result = computeDelta(50, 50, MIN_PREV_N, { higherIsBad: true, unit: "pct" });
    expect(result.insufficientHistory).toBe(false);
    expect(result.words).not.toBeNull();
  });
});

describe("relativeChangePct", () => {
  it("returns Infinity when previous is 0 and current > 0", () => {
    expect(relativeChangePct(10, 0)).toBe(Infinity);
  });

  it("returns 0 when both previous and current are 0", () => {
    expect(relativeChangePct(0, 0)).toBe(0);
  });

  it("computes a normal relative change (50 -> 65 is 30%)", () => {
    expect(relativeChangePct(65, 50)).toBe(30);
  });

  it("computes a normal negative relative change (50 -> 40 is -20%)", () => {
    expect(relativeChangePct(40, 50)).toBe(-20);
  });
});
