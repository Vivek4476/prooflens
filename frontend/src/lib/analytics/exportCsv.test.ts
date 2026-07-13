import { describe, expect, it } from "vitest";

import type { AnalyticsBucket, AnalyticsSummary } from "@/lib/api/types";
import { analyticsToCsv, bucketsToCsv, csvFilename } from "./exportCsv";

function bucket(over: Partial<AnalyticsBucket>): AnalyticsBucket {
  return {
    bucket_label: "Week 1",
    start: "2026-06-10",
    end: "2026-06-16",
    clear: 90,
    doubtful: 6,
    suspect: 4,
    unassessed: 0,
    total: 100,
    avg_score: 79.2,
    incomplete: false,
    ...over,
  };
}

describe("bucketsToCsv", () => {
  it("emits a header row plus one row per bucket", () => {
    const csv = bucketsToCsv([bucket({}), bucket({ bucket_label: "Week 2" })]);
    const lines = csv.trimEnd().split("\n");
    expect(lines[0]).toBe("bucket,start,end,clear,doubtful,suspect,total,avg_score,suspect_rate_pct,incomplete");
    expect(lines).toHaveLength(3);
  });

  it("computes suspect_rate_pct rounded to one decimal", () => {
    expect(bucketsToCsv([bucket({ suspect: 4, total: 100 })])).toContain(",4,"); // exact integer stays "4"
    expect(bucketsToCsv([bucket({ suspect: 5, total: 300 })])).toContain(",1.7,"); // 1.666… → 1.7
  });

  it("guards divide-by-zero for empty buckets", () => {
    const csv = bucketsToCsv([bucket({ clear: 0, doubtful: 0, suspect: 0, total: 0 })]);
    // suspect_rate_pct column is 0, not NaN
    expect(csv).not.toContain("NaN");
    expect(csv.trimEnd().split("\n")[1].endsWith(",0,false")).toBe(true);
  });

  it("quotes cells containing commas or quotes (RFC 4180)", () => {
    const csv = bucketsToCsv([bucket({ bucket_label: 'Jun 10, "wk"' })]);
    expect(csv).toContain('"Jun 10, ""wk"""');
  });

  it("marks the incomplete current bucket honestly", () => {
    const csv = bucketsToCsv([bucket({ incomplete: true })]);
    expect(csv.trimEnd().split("\n")[1].endsWith(",true")).toBe(true);
  });

  it("ends with a trailing newline and handles an empty series", () => {
    expect(bucketsToCsv([])).toBe(
      "bucket,start,end,clear,doubtful,suspect,total,avg_score,suspect_rate_pct,incomplete\n",
    );
  });
});

function summary(): AnalyticsSummary {
  return {
    period: { from: "2026-06-10", to: "2026-07-09" },
    previous_period: { from: "2026-05-11", to: "2026-06-09" },
    total: 1322,
    suspect_pct: 4.5,
    avg_score: 78.9,
    duplicates_caught: 11,
    system_health: { scored_without_content_pct: 3.3, median_processing_ms: 0 },
    buckets: [bucket({ suspect: 4, total: 100 })],
    top_reasons: [
      { reason_code: "too_blurred", short_label: "Too blurred", count: 48 },
      { reason_code: "clear", short_label: "Clear", count: 900 },
    ],
  } as unknown as AnalyticsSummary;
}

describe("analyticsToCsv", () => {
  it("emits sectioned report: period, KPIs, time series, top reasons", () => {
    const csv = analyticsToCsv(summary());
    expect(csv).toContain("ProofLens — Analytics export");
    expect(csv).toContain("Period,2026-06-10,to,2026-07-09");
    expect(csv).toContain("Total scored,1322");
    expect(csv).toContain("Median time-to-score (ms),0"); // 0 kept, not blank
    expect(csv).toContain("Time series");
    expect(csv).toContain("Top flag reasons");
    expect(csv).toContain("Too blurred,48,100"); // 48/48 flagged = 100% (clear excluded)
  });

  it("excludes the non-flag 'clear' reason from the reasons section", () => {
    const csv = analyticsToCsv(summary());
    const reasonsSection = csv.slice(csv.indexOf("Top flag reasons"));
    expect(reasonsSection).not.toContain("Clear,900");
  });
});

describe("csvFilename", () => {
  it("embeds the period bounds", () => {
    expect(csvFilename({ from: "2026-06-10", to: "2026-07-09" })).toBe(
      "prooflens-analytics-2026-06-10_2026-07-09.csv",
    );
  });
});
