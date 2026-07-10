import { describe, expect, it } from "vitest";
import {
  bucketsWithData,
  MIN_BAND_MIX_BUCKETS,
  previousPeriodRate,
  toBandMixData,
  toTrendData,
} from "./chartData";
import type { AnalyticsBucket, PeriodAggregate } from "@/lib/api/types";

function bucket(overrides: Partial<AnalyticsBucket>): AnalyticsBucket {
  return {
    bucket_label: "Jul 1",
    start: "2026-07-01",
    end: "2026-07-01",
    clear: 0,
    doubtful: 0,
    suspect: 0,
    total: 0,
    avg_score: 0,
    incomplete: false,
    ...overrides,
  };
}

describe("toTrendData", () => {
  it("computes suspect rate as a percentage per bucket", () => {
    const buckets = [bucket({ bucket_label: "Jul 1", clear: 6, doubtful: 2, suspect: 2, total: 10 })];
    expect(toTrendData(buckets)).toEqual([
      { label: "Jul 1", rate: 20, incomplete: false, total: 10 },
    ]);
  });

  it("charts a zero-total bucket at 0% instead of dividing by zero", () => {
    const buckets = [bucket({ total: 0, suspect: 0 })];
    const [point] = toTrendData(buckets);
    expect(point.rate).toBe(0);
    expect(Number.isFinite(point.rate)).toBe(true);
  });

  it("carries the incomplete flag through untouched", () => {
    const buckets = [
      bucket({ bucket_label: "complete", incomplete: false, total: 5, suspect: 1 }),
      bucket({ bucket_label: "in-progress", incomplete: true, total: 5, suspect: 1 }),
    ];
    const points = toTrendData(buckets);
    expect(points[0].incomplete).toBe(false);
    expect(points[1].incomplete).toBe(true);
  });

  it("preserves bucket order and count", () => {
    const buckets = [
      bucket({ bucket_label: "a" }),
      bucket({ bucket_label: "b" }),
      bucket({ bucket_label: "c" }),
    ];
    expect(toTrendData(buckets).map((p) => p.label)).toEqual(["a", "b", "c"]);
  });
});

describe("previousPeriodRate", () => {
  it("computes the previous period's overall suspect rate as a percentage", () => {
    const previous: PeriodAggregate = { clear: 70, doubtful: 20, suspect: 10, total: 100, avg_score: 80 };
    expect(previousPeriodRate(previous)).toBe(10);
  });

  it("returns 0 (not NaN) when the previous period had no scored volume", () => {
    const previous: PeriodAggregate = { clear: 0, doubtful: 0, suspect: 0, total: 0, avg_score: 0 };
    expect(previousPeriodRate(previous)).toBe(0);
  });
});

describe("bucketsWithData", () => {
  it("keeps only buckets with total > 0", () => {
    const buckets = [
      bucket({ bucket_label: "empty", total: 0 }),
      bucket({ bucket_label: "has-data", total: 5 }),
    ];
    expect(bucketsWithData(buckets).map((b) => b.bucket_label)).toEqual(["has-data"]);
  });

  it("drops all buckets when none have data", () => {
    const buckets = [bucket({ total: 0 }), bucket({ total: 0 })];
    expect(bucketsWithData(buckets)).toEqual([]);
  });
});

describe("toBandMixData", () => {
  it("converts raw band counts to 100%-stacked percentages", () => {
    const buckets = [bucket({ clear: 5, doubtful: 3, suspect: 2, total: 10 })];
    const [point] = toBandMixData(buckets);
    expect(point.Clear).toBe(50);
    expect(point.Doubtful).toBe(30);
    expect(point.Suspect).toBe(20);
    expect(point.Clear + point.Doubtful + point.Suspect).toBe(100);
  });

  it("carries raw counts through for tooltip use", () => {
    const buckets = [bucket({ clear: 5, doubtful: 3, suspect: 2, total: 10 })];
    const [point] = toBandMixData(buckets);
    expect(point.rawClear).toBe(5);
    expect(point.rawDoubtful).toBe(3);
    expect(point.rawSuspect).toBe(2);
    expect(point.total).toBe(10);
  });

  it("excludes empty (total===0) buckets from the output entirely — the X-domain rule", () => {
    const buckets = [
      bucket({ bucket_label: "empty", total: 0 }),
      bucket({ bucket_label: "has-data", clear: 1, total: 1 }),
    ];
    expect(toBandMixData(buckets).map((p) => p.label)).toEqual(["has-data"]);
  });

  it("marks incomplete buckets so the chart can render them distinctly", () => {
    const buckets = [bucket({ total: 5, clear: 5, incomplete: true })];
    expect(toBandMixData(buckets)[0].incomplete).toBe(true);
  });
});

describe("MIN_BAND_MIX_BUCKETS gate (the <3-buckets caption branch)", () => {
  it("is 3, matching the brief's 'fewer than 3 -> caption' rule", () => {
    expect(MIN_BAND_MIX_BUCKETS).toBe(3);
  });

  it("2 data-bearing buckets is below the gate", () => {
    const buckets = [bucket({ total: 5 }), bucket({ total: 5 })];
    expect(bucketsWithData(buckets).length < MIN_BAND_MIX_BUCKETS).toBe(true);
  });

  it("3 data-bearing buckets clears the gate", () => {
    const buckets = [bucket({ total: 5 }), bucket({ total: 5 }), bucket({ total: 5 })];
    expect(bucketsWithData(buckets).length < MIN_BAND_MIX_BUCKETS).toBe(false);
  });

  it("empty buckets don't count toward the gate even if total bucket count is >=3", () => {
    const buckets = [
      bucket({ total: 5 }),
      bucket({ total: 0 }),
      bucket({ total: 0 }),
    ];
    expect(bucketsWithData(buckets).length < MIN_BAND_MIX_BUCKETS).toBe(true);
  });
});
