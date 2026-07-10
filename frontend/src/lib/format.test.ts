import { describe, expect, it } from "vitest";
import {
  formatCount,
  formatDateRange,
  formatPct,
  formatScore,
  formatShortDate,
  formatSignedPts,
  formatSignedRelPct,
} from "./format";

describe("formatCount", () => {
  it("formats 0", () => {
    expect(formatCount(0)).toBe("0");
  });

  it("formats 1000 with a thousands separator", () => {
    expect(formatCount(1000)).toBe("1,000");
  });

  it("formats 2113 with a thousands separator", () => {
    expect(formatCount(2113)).toBe("2,113");
  });

  it("formats 1000000 with multiple thousands separators", () => {
    expect(formatCount(1000000)).toBe("1,000,000");
  });
});

describe("formatScore", () => {
  it("formats 0 as 0.0, not -0.0", () => {
    expect(formatScore(0)).toBe("0.0");
    expect(formatScore(-0)).toBe("0.0");
  });

  it("rounds 78.44 down to 78.4", () => {
    expect(formatScore(78.44)).toBe("78.4");
  });

  it("rounds 78.45 to 78.5 (actual toFixed/float behavior, not banker's rounding)", () => {
    // 78.45 * 10 === 784.5 exactly in floating point, and Math.round(784.5) === 785,
    // so this rounds up to 78.5 rather than exhibiting banker's rounding to 78.4.
    expect(formatScore(78.45)).toBe("78.5");
  });
});

describe("formatPct", () => {
  it("formats 0 as 0.0%", () => {
    expect(formatPct(0)).toBe("0.0%");
  });

  it("formats 100 as 100.0%", () => {
    expect(formatPct(100)).toBe("100.0%");
  });

  it("formats 3.0421 as 3.0% without false precision", () => {
    expect(formatPct(3.0421)).toBe("3.0%");
  });
});

describe("formatSignedPts", () => {
  it("formats 0 as ±0.0 pts", () => {
    expect(formatSignedPts(0)).toBe("±0.0 pts");
  });

  it("formats a positive delta with a leading +", () => {
    expect(formatSignedPts(3.2)).toBe("+3.2 pts");
  });

  it("formats a negative delta with a leading -", () => {
    expect(formatSignedPts(-1.1)).toBe("-1.1 pts");
  });
});

describe("formatSignedRelPct", () => {
  it("formats 0 as ±0.0%", () => {
    expect(formatSignedRelPct(0)).toBe("±0.0%");
  });

  it("formats a positive change with a leading +", () => {
    expect(formatSignedRelPct(23.4)).toBe("+23.4%");
  });

  it("formats a negative change with a leading -", () => {
    expect(formatSignedRelPct(-5.5)).toBe("-5.5%");
  });
});

describe("formatShortDate", () => {
  it("formats a leap-year Feb 29", () => {
    expect(formatShortDate("2024-02-29")).toBe("Feb 29");
  });

  it("formats Dec 31", () => {
    expect(formatShortDate("2025-12-31")).toBe("Dec 31");
  });

  it("formats the Jan 1 boundary from the following year", () => {
    expect(formatShortDate("2026-01-01")).toBe("Jan 1");
  });

  it("returns the original string for unparseable input", () => {
    expect(formatShortDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatDateRange", () => {
  it("formats a cross-month range", () => {
    expect(formatDateRange("2026-06-08", "2026-07-07")).toBe("Jun 8–Jul 7");
  });
});
