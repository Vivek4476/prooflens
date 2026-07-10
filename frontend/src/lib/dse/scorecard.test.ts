import { describe, expect, it } from "vitest";

import type { DseScorecard, DseSearchResult, DseTrendPoint } from "@/lib/api/types";
import {
  chainBreadcrumb,
  isSparseDse,
  MIN_TOTAL_FOR_CONFIDENT_RATE,
  shapeSearchResults,
  toDseTrendData,
} from "./scorecard";

function trendPoint(overrides: Partial<DseTrendPoint>): DseTrendPoint {
  return {
    bucket_label: "Jul 1",
    start: "2026-07-01",
    end: "2026-07-01",
    suspect: 0,
    total: 0,
    suspect_rate: 0,
    incomplete: false,
    ...overrides,
  };
}

function chain(overrides: Partial<DseScorecard["chain"]> = {}): DseScorecard["chain"] {
  return { sm: null, rsm: null, srsm: null, zone: null, branch: null, city: null, ...overrides };
}

function searchResult(overrides: Partial<DseSearchResult>): DseSearchResult {
  return { agent_id: "A1", name: "Agent One", branch: null, sm: null, ...overrides };
}

describe("isSparseDse", () => {
  it("flags totals below the confidence threshold as sparse", () => {
    expect(isSparseDse(0)).toBe(true);
    expect(isSparseDse(19)).toBe(true);
  });

  it("does not flag totals at or above the threshold", () => {
    expect(isSparseDse(20)).toBe(false);
    expect(isSparseDse(500)).toBe(false);
  });

  it("threshold constant is 20, matching ByTeamPanel's MIN_TOTAL_FOR_RATE", () => {
    expect(MIN_TOTAL_FOR_CONFIDENT_RATE).toBe(20);
  });
});

describe("toDseTrendData", () => {
  it("computes suspect rate as a percentage per bucket", () => {
    const trend = [trendPoint({ bucket_label: "Jul 1", suspect: 2, total: 10 })];
    expect(toDseTrendData(trend)).toEqual([{ label: "Jul 1", rate: 20, incomplete: false, total: 10 }]);
  });

  it("charts a zero-total bucket at 0% instead of dividing by zero", () => {
    const [point] = toDseTrendData([trendPoint({ total: 0, suspect: 0 })]);
    expect(point.rate).toBe(0);
    expect(Number.isFinite(point.rate)).toBe(true);
  });

  it("carries the incomplete flag through untouched", () => {
    const points = toDseTrendData([
      trendPoint({ bucket_label: "complete", incomplete: false, total: 5, suspect: 1 }),
      trendPoint({ bucket_label: "in-progress", incomplete: true, total: 5, suspect: 1 }),
    ]);
    expect(points[0].incomplete).toBe(false);
    expect(points[1].incomplete).toBe(true);
  });

  it("preserves bucket order", () => {
    const points = toDseTrendData([
      trendPoint({ bucket_label: "a" }),
      trendPoint({ bucket_label: "b" }),
      trendPoint({ bucket_label: "c" }),
    ]);
    expect(points.map((p) => p.label)).toEqual(["a", "b", "c"]);
  });
});

describe("chainBreadcrumb", () => {
  it("orders SM -> RSM -> SRSM -> Zone -> Branch", () => {
    const c = chain({ sm: "SM1", rsm: "RSM1", srsm: "SRSM1", zone: "Z1", branch: "B1", city: "C1" });
    expect(chainBreadcrumb(c)).toEqual(["SM1", "RSM1", "SRSM1", "Z1", "B1"]);
  });

  it("drops missing levels rather than showing a placeholder", () => {
    const c = chain({ sm: "SM1", branch: "B1" });
    expect(chainBreadcrumb(c)).toEqual(["SM1", "B1"]);
  });

  it("drops blank/whitespace-only levels", () => {
    const c = chain({ sm: "SM1", rsm: "  ", branch: "B1" });
    expect(chainBreadcrumb(c)).toEqual(["SM1", "B1"]);
  });

  it("returns an empty array when the DSE has no resolvable chain at all", () => {
    expect(chainBreadcrumb(chain())).toEqual([]);
  });
});

describe("shapeSearchResults", () => {
  it("de-duplicates by agent_id, keeping first occurrence", () => {
    const results = [
      searchResult({ agent_id: "A1", name: "First" }),
      searchResult({ agent_id: "A1", name: "Duplicate" }),
      searchResult({ agent_id: "A2", name: "Second" }),
    ];
    const out = shapeSearchResults(results);
    expect(out).toHaveLength(2);
    expect(out[0].name).toBe("First");
  });

  it("caps to maxRows", () => {
    const results = Array.from({ length: 30 }, (_, i) => searchResult({ agent_id: `A${i}`, name: `Agent ${i}` }));
    expect(shapeSearchResults(results, 5)).toHaveLength(5);
  });

  it("preserves order otherwise", () => {
    const results = [searchResult({ agent_id: "A2" }), searchResult({ agent_id: "A1" })];
    expect(shapeSearchResults(results).map((r) => r.agent_id)).toEqual(["A2", "A1"]);
  });

  it("returns an empty array for empty input", () => {
    expect(shapeSearchResults([])).toEqual([]);
  });
});
