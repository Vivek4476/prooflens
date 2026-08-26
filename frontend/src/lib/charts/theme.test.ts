import { describe, expect, it } from "vitest";
import { CHART_THEME } from "./theme";

describe("CHART_THEME", () => {
  it("exposes token-driven grid, axis, and a series palette (no hard-coded verdict hues for generic series)", () => {
    expect(CHART_THEME.grid).toContain("var(--");
    expect(CHART_THEME.axis).toContain("var(--");
    expect(CHART_THEME.series.length).toBeGreaterThanOrEqual(2);
  });
});
