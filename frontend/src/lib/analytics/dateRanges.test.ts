import { describe, expect, it } from "vitest";

import { resolvePreset } from "./dateRanges";

const TODAY = new Date("2026-07-08T00:00:00Z");

describe("resolvePreset", () => {
  it("7d resolves to a 7-day span ending today", () => {
    expect(resolvePreset("7d", TODAY)).toEqual({
      start_date: "2026-07-02",
      end_date: "2026-07-08",
    });
  });

  it("30d resolves to a 30-day span ending today", () => {
    expect(resolvePreset("30d", TODAY)).toEqual({
      start_date: "2026-06-09",
      end_date: "2026-07-08",
    });
  });

  it("90d resolves to a 90-day span ending today", () => {
    expect(resolvePreset("90d", TODAY)).toEqual({
      start_date: "2026-04-10",
      end_date: "2026-07-08",
    });
  });

  it("month resolves from the 1st of the current month through today", () => {
    expect(resolvePreset("month", TODAY)).toEqual({
      start_date: "2026-07-01",
      end_date: "2026-07-08",
    });
  });

  it("month collapses to a 1-day span when today is the 1st", () => {
    const firstOfMonth = new Date("2026-07-01T00:00:00Z");
    expect(resolvePreset("month", firstOfMonth)).toEqual({
      start_date: "2026-07-01",
      end_date: "2026-07-01",
    });
  });

  it("custom passes through given bounds unchanged", () => {
    expect(
      resolvePreset("custom", TODAY, { start_date: "2026-01-01", end_date: "2026-01-15" }),
    ).toEqual({
      start_date: "2026-01-01",
      end_date: "2026-01-15",
    });
  });

  it("custom falls back to today when bounds are omitted", () => {
    expect(resolvePreset("custom", TODAY)).toEqual({
      start_date: "2026-07-08",
      end_date: "2026-07-08",
    });
  });

  it("custom falls back to today for whichever bound is missing", () => {
    expect(resolvePreset("custom", TODAY, { start_date: "2026-01-01" })).toEqual({
      start_date: "2026-01-01",
      end_date: "2026-07-08",
    });
  });
});
