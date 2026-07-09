import { describe, expect, it } from "vitest";

import {
  availableBuckets,
  effectiveBucket,
  isOverridden,
  MIN_DAYS_FOR_MONTHLY,
  MIN_DAYS_FOR_WEEKLY,
  spanDays,
} from "./cardOverride";

describe("spanDays", () => {
  it("counts inclusively", () => {
    expect(spanDays("2026-07-01", "2026-07-01")).toBe(1);
    expect(spanDays("2026-07-01", "2026-07-07")).toBe(7);
  });

  it("returns 0 for missing or unparseable dates", () => {
    expect(spanDays(undefined, "2026-07-07")).toBe(0);
    expect(spanDays("2026-07-01", undefined)).toBe(0);
    expect(spanDays("not-a-date", "2026-07-07")).toBe(0);
  });
});

describe("availableBuckets", () => {
  it("daily is always available", () => {
    expect(availableBuckets("2026-07-01", "2026-07-01").daily).toBe(true);
    expect(availableBuckets(undefined, undefined).daily).toBe(true);
  });

  it("weekly is enabled iff span >= 14 days", () => {
    const justUnder = availableBuckets("2026-07-01", "2026-07-13"); // 13 days
    const exact = availableBuckets("2026-07-01", "2026-07-14"); // 14 days
    expect(spanDays("2026-07-01", "2026-07-13")).toBe(MIN_DAYS_FOR_WEEKLY - 1);
    expect(justUnder.weekly).toBe(false);
    expect(exact.weekly).toBe(true);
  });

  it("monthly is enabled iff span >= 60 days", () => {
    const justUnder = availableBuckets("2026-01-01", "2026-02-28"); // 59 days
    const exact = availableBuckets("2026-01-01", "2026-03-01"); // 60 days
    expect(spanDays("2026-01-01", "2026-02-28")).toBe(MIN_DAYS_FOR_MONTHLY - 1);
    expect(justUnder.monthly).toBe(false);
    expect(exact.monthly).toBe(true);
  });
});

describe("isOverridden", () => {
  it("is false for 'page'", () => {
    expect(isOverridden("page", "daily")).toBe(false);
  });

  it("is false when the choice equals the global bucket", () => {
    expect(isOverridden("daily", "daily")).toBe(false);
    expect(isOverridden("weekly", "weekly")).toBe(false);
  });

  it("is true when the choice differs from the global bucket", () => {
    expect(isOverridden("weekly", "daily")).toBe(true);
    expect(isOverridden("monthly", "weekly")).toBe(true);
  });
});

describe("effectiveBucket", () => {
  it("resolves 'page' to the global bucket", () => {
    expect(effectiveBucket("page", "monthly")).toBe("monthly");
  });

  it("resolves an explicit choice to itself", () => {
    expect(effectiveBucket("weekly", "daily")).toBe("weekly");
  });
});
