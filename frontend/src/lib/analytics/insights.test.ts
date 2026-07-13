import { describe, expect, it } from "vitest";

import type { AnalyticsSummary, TopReason } from "@/lib/api/types";
import { computeInsights, NO_SHIFTS_FALLBACK } from "./insights";

/** Builds a minimal valid AnalyticsSummary, overridable per-test. */
function makeSummary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    total: 100,
    images_today: 10,
    band_distribution: { Clear: 80, Doubtful: 10, Suspect: 10, Unassessed: 0 },
    suspect_pct: 10,
    avg_score: 75,
    avg_processing_ms: 500,
    duplicates_caught: 0,
    top_reasons: [],
    series: [],
    buckets: [],
    incomplete: false,
    previous: { clear: 80, doubtful: 10, suspect: 10, unassessed: 0, total: 100, avg_score: 75 },
    period: { from: "2026-06-09", to: "2026-07-08" },
    previous_period: { from: "2026-05-10", to: "2026-06-08" },
    groups: [],
    ...overrides,
  };
}

function reason(overrides: Partial<TopReason>): TopReason {
  return {
    reason_code: "blur",
    reason: "Image appears blurry",
    short_label: "Blurry",
    count: 0,
    ...overrides,
  };
}

describe("computeInsights — suspectRateShift rule", () => {
  it("does not fire when current suspect count is below the absolute gate (cur=9), even with huge relative change", () => {
    const a = makeSummary({
      band_distribution: { Clear: 80, Doubtful: 11, Suspect: 9, Unassessed: 0 },
      previous: { clear: 80, doubtful: 15, suspect: 5, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "suspect-rate-shift")).toBeUndefined();
  });

  it("fires when cur=10, prev=8 (relative change 25% >= 20%)", () => {
    const a = makeSummary({
      band_distribution: { Clear: 80, Doubtful: 10, Suspect: 10, Unassessed: 0 },
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "suspect-rate-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("high");
    expect(hit?.text).toContain("rose");
  });

  it("does not fire when cur=10, prev=9 (relative change ~11% < 20%)", () => {
    const a = makeSummary({
      band_distribution: { Clear: 80, Doubtful: 10, Suspect: 10, Unassessed: 0 },
      previous: { clear: 80, doubtful: 11, suspect: 9, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "suspect-rate-shift")).toBeUndefined();
  });

  it("does NOT fire a percentage/Infinity insight when previous.total is a large sample but prior suspect count is 0 (honest-states guard)", () => {
    // previous.total (100) is well above MIN_PREV_N, so this isn't a small-sample
    // case — it's a genuine "no prior Suspect captures" case. Percent-of-zero is
    // still undefined, so no relative-% bullet may be emitted for it.
    const a = makeSummary({
      band_distribution: { Clear: 90, Doubtful: 0, Suspect: 10, Unassessed: 0 },
      previous: { clear: 100, doubtful: 0, suspect: 0, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "suspect-rate-shift");
    if (hit) {
      expect(hit.text).not.toMatch(/Infinity/i);
      expect(hit.text).not.toMatch(/NaN/i);
      expect(hit.text).not.toMatch(/%/);
    }
  });

  it("never emits Infinity/NaN/% text when previous.total is below MIN_PREV_N, even with a huge current suspect count", () => {
    const a = makeSummary({
      band_distribution: { Clear: 0, Doubtful: 0, Suspect: 133, Unassessed: 0 },
      previous: { clear: 0, doubtful: 0, suspect: 0, unassessed: 0, total: 0, avg_score: 0 },
    });
    const insights = computeInsights(a, null);
    for (const i of insights) {
      expect(i.text).not.toMatch(/Infinity/i);
      expect(i.text).not.toMatch(/NaN/i);
    }
    const hit = insights.find((i) => i.id === "suspect-rate-shift");
    if (hit) {
      expect(hit.text).not.toMatch(/%/);
    }
  });

  it("fires with info severity and 'fell' wording when suspect volume falls", () => {
    const a = makeSummary({
      band_distribution: { Clear: 90, Doubtful: 0, Suspect: 10, Unassessed: 0 },
      previous: { clear: 70, doubtful: 15, suspect: 15, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "suspect-rate-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("info");
    expect(hit?.text).toContain("fell");
  });
});

describe("computeInsights — dominantReason rule", () => {
  it("fires when the top reason share is exactly 30% (boundary inclusive)", () => {
    const a = makeSummary({
      top_reasons: [reason({ reason_code: "blur", short_label: "Blurry", count: 30 }), reason({ reason_code: "dup", short_label: "Duplicate", count: 70 })],
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "dominant-reason");
    expect(hit).toBeDefined();
    expect(hit?.text).toContain("30%");
  });

  it("does not fire when the top reason share is 29.9%", () => {
    const a = makeSummary({
      top_reasons: [
        reason({ reason_code: "blur", short_label: "Blurry", count: 299 }),
        reason({ reason_code: "dup", short_label: "Duplicate", count: 701 }),
      ],
    });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "dominant-reason")).toBeUndefined();
  });

  it("does not fire with an empty top_reasons list (no divide-by-zero)", () => {
    const a = makeSummary({ top_reasons: [] });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "dominant-reason")).toBeUndefined();
  });

  it("excludes 'clear' reason_code entries from the flagged total", () => {
    const a = makeSummary({
      top_reasons: [
        reason({ reason_code: "clear", short_label: "Clear", count: 1000 }),
        reason({ reason_code: "blur", short_label: "Blurry", count: 30 }),
        reason({ reason_code: "dup", short_label: "Duplicate", count: 70 }),
      ],
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "dominant-reason");
    expect(hit).toBeDefined();
    expect(hit?.text).toContain("Blurry");
    expect(hit?.text).toContain("30%");
  });
});

describe("computeInsights — avgScoreShift rule", () => {
  it("does not fire when previous.total=29 regardless of diff (small-sample guard)", () => {
    const a = makeSummary({
      avg_score: 90,
      previous: { clear: 20, doubtful: 5, suspect: 4, unassessed: 0, total: 29, avg_score: 50 },
    });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "avg-score-shift")).toBeUndefined();
  });

  it("fires when previous.total=30 and diff=5.0 (boundary inclusive)", () => {
    const a = makeSummary({
      avg_score: 80,
      previous: { clear: 20, doubtful: 5, suspect: 5, unassessed: 0, total: 30, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "avg-score-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("info");
    expect(hit?.text).toContain("improved");
  });

  it("does not fire when previous.total=30 and diff=4.9", () => {
    const a = makeSummary({
      avg_score: 79.9,
      previous: { clear: 20, doubtful: 5, suspect: 5, unassessed: 0, total: 30, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "avg-score-shift")).toBeUndefined();
  });

  it("fires with warn severity and 'dropped' wording when avg score falls by >= 5 pts", () => {
    const a = makeSummary({
      avg_score: 65,
      previous: { clear: 20, doubtful: 5, suspect: 5, unassessed: 0, total: 30, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    const hit = insights.find((i) => i.id === "avg-score-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("warn");
    expect(hit?.text).toContain("dropped");
  });
});

describe("computeInsights — duplicatesShift rule", () => {
  it("does not fire when both current and previous are under 5, even with 100% relative change", () => {
    const a = makeSummary({ duplicates_caught: 4 });
    const insights = computeInsights(a, 2);
    expect(insights.find((i) => i.id === "duplicates-shift")).toBeUndefined();
  });

  it("fires when current=5, previous=4 (25% relative change >= 20%)", () => {
    const a = makeSummary({ duplicates_caught: 5 });
    const insights = computeInsights(a, 4);
    const hit = insights.find((i) => i.id === "duplicates-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("warn");
    expect(hit?.text).toContain("rose");
  });

  it("fires when current=6, previous=5 (20% relative change, boundary inclusive)", () => {
    const a = makeSummary({ duplicates_caught: 6 });
    const insights = computeInsights(a, 5);
    const hit = insights.find((i) => i.id === "duplicates-shift");
    expect(hit).toBeDefined();
  });

  it("is skipped (not fabricated) when prevDuplicatesCaught is null", () => {
    const a = makeSummary({ duplicates_caught: 100 });
    const insights = computeInsights(a, null);
    expect(insights.find((i) => i.id === "duplicates-shift")).toBeUndefined();
  });

  it("does not emit Infinity/NaN/% text when previous.total is below MIN_PREV_N, even though prevDuplicatesCaught=0 and current=34 (honest-states guard, reproduces reported bug)", () => {
    const a = makeSummary({
      duplicates_caught: 34,
      previous: { clear: 0, doubtful: 0, suspect: 0, unassessed: 0, total: 0, avg_score: 0 },
    });
    const insights = computeInsights(a, 0);
    const hit = insights.find((i) => i.id === "duplicates-shift");
    if (hit) {
      expect(hit.text).not.toMatch(/Infinity/i);
      expect(hit.text).not.toMatch(/NaN/i);
      expect(hit.text).not.toMatch(/%/);
    }
  });

  it("still fires a normal relative-% duplicates insight when previous.total is sufficient (regression guard)", () => {
    const a = makeSummary({
      duplicates_caught: 5,
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, 4);
    const hit = insights.find((i) => i.id === "duplicates-shift");
    expect(hit).toBeDefined();
    expect(hit?.text).toContain("25%");
  });

  it("fires with info severity and 'fell' wording when duplicates fall", () => {
    const a = makeSummary({ duplicates_caught: 4 });
    // previous=8: rel change (4-8)/8 = -50%
    const insights = computeInsights(a, 8);
    const hit = insights.find((i) => i.id === "duplicates-shift");
    expect(hit).toBeDefined();
    expect(hit?.severity).toBe("info");
    expect(hit?.text).toContain("fell");
  });
});

describe("computeInsights — fallback, ordering, and cap", () => {
  it("returns an empty array when no rules fire", () => {
    const a = makeSummary();
    const insights = computeInsights(a, null);
    expect(insights).toEqual([]);
  });

  it("never labels insights as AI/model output", () => {
    const a = makeSummary({
      band_distribution: { Clear: 80, Doubtful: 10, Suspect: 10, Unassessed: 0 },
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 },
    });
    const insights = computeInsights(a, null);
    for (const insight of insights) {
      expect(insight.text.toLowerCase()).not.toMatch(/\b(ai|model|llm|generated by)\b/);
    }
  });

  it("sorts so that high severity precedes warn precedes info when all rules fire, and caps at MAX_INSIGHTS", () => {
    const a = makeSummary({
      // suspect-rate-shift: rising -> high
      band_distribution: { Clear: 60, Doubtful: 20, Suspect: 20, Unassessed: 0 },
      avg_score: 60,
      duplicates_caught: 5,
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 }, // avg-score-shift: falling -> warn
      top_reasons: [
        // dominant-reason -> warn
        reason({ reason_code: "blur", short_label: "Blurry", count: 30 }),
        reason({ reason_code: "dup", short_label: "Duplicate", count: 70 }),
      ],
    });
    // duplicates-shift: current=5, previous=4 -> rising -> warn
    const insights = computeInsights(a, 4);

    expect(insights.length).toBeLessThanOrEqual(5);
    expect(insights.length).toBeGreaterThanOrEqual(1);

    const severityIndex: Record<string, number> = { high: 0, warn: 1, info: 2 };
    for (let i = 1; i < insights.length; i++) {
      expect(severityIndex[insights[i - 1].severity]).toBeLessThanOrEqual(
        severityIndex[insights[i].severity],
      );
    }

    // Confirm the high-severity suspect-rate-shift bullet is first.
    expect(insights[0].id).toBe("suspect-rate-shift");
    expect(insights[0].severity).toBe("high");
  });

  it("respects the MAX_INSIGHTS cap of 5 even if more candidate rules existed", () => {
    // With today's 4 rules we can't exceed 5, but assert the cap contract directly:
    // every returned list length must never exceed 5 regardless of how many fire.
    const a = makeSummary({
      band_distribution: { Clear: 60, Doubtful: 20, Suspect: 20, Unassessed: 0 },
      avg_score: 60,
      duplicates_caught: 5,
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 },
      top_reasons: [
        reason({ reason_code: "blur", short_label: "Blurry", count: 30 }),
        reason({ reason_code: "dup", short_label: "Duplicate", count: 70 }),
      ],
    });
    const insights = computeInsights(a, 4);
    expect(insights.length).toBeLessThanOrEqual(5);
  });
});

describe("computeInsights — drill-down href", () => {
  it("suspect-rate-shift links to /history?band=Suspect with the current period", () => {
    const a = makeSummary({
      band_distribution: { Clear: 80, Doubtful: 10, Suspect: 10, Unassessed: 0 },
      previous: { clear: 80, doubtful: 12, suspect: 8, unassessed: 0, total: 100, avg_score: 75 },
      period: { from: "2026-06-09", to: "2026-07-08" },
    });
    const hit = computeInsights(a, null).find((i) => i.id === "suspect-rate-shift");
    expect(hit?.href).toBe("/history?band=Suspect&from=2026-06-09&to=2026-07-08");
  });

  it("dominant-reason links to /history?reason=<code> with the current period", () => {
    const a = makeSummary({
      top_reasons: [
        reason({ reason_code: "screen_recapture", short_label: "Photo of a screen", count: 30 }),
        reason({ reason_code: "blur", short_label: "Blurry", count: 70 }),
      ],
      period: { from: "2026-06-09", to: "2026-07-08" },
    });
    const hit = computeInsights(a, null).find((i) => i.id === "dominant-reason");
    expect(hit?.href).toBe("/history?reason=screen_recapture&from=2026-06-09&to=2026-07-08");
  });

  it("duplicates-shift links to /history?reason=recycled (the real reason_code) with the current period", () => {
    const a = makeSummary({
      duplicates_caught: 5,
      period: { from: "2026-06-09", to: "2026-07-08" },
    });
    const hit = computeInsights(a, 4).find((i) => i.id === "duplicates-shift");
    expect(hit?.href).toBe("/history?reason=recycled&from=2026-06-09&to=2026-07-08");
  });

  it("avg-score-shift has no href — /v1/results has no avg-score filter to honour", () => {
    const a = makeSummary({
      avg_score: 65,
      previous: { clear: 20, doubtful: 5, suspect: 5, unassessed: 0, total: 30, avg_score: 75 },
    });
    const hit = computeInsights(a, null).find((i) => i.id === "avg-score-shift");
    expect(hit).toBeDefined();
    expect(hit?.href).toBeUndefined();
  });
});

describe("NO_SHIFTS_FALLBACK", () => {
  it("is a non-empty fallback string for when computeInsights returns []", () => {
    expect(typeof NO_SHIFTS_FALLBACK).toBe("string");
    expect(NO_SHIFTS_FALLBACK.length).toBeGreaterThan(0);
  });
});
