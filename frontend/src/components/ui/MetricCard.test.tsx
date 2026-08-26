import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("renders value in tabular mono and keeps the delta NEUTRAL (no verdict color)", () => {
    render(<MetricCard label="Suspect / fraud" value="6.2%" sub="+2.1 pts vs 7-day" subDirection="up" />);
    const value = screen.getByText("6.2%");
    expect(value.className).toContain("tabular-nums");
    expect(value.className).toContain("font-mono");
    const delta = screen.getByText(/2.1 pts/).closest("span")!;
    // BRAND: a rate movement is not a verdict — never verdict-suspect red/green.
    expect(delta.className).not.toMatch(/verdict/);
    expect(delta.className).toContain("text-text-secondary");
  });
});
