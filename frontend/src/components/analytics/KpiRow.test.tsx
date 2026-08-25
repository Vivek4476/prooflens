import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiRow } from "./KpiRow";
import type { AnalyticsSummary } from "@/lib/api/types";

const a = {
  total: 100,
  suspect_pct: 8,
  avg_score: 73,
  band_distribution: { Clear: 70, Doubtful: 20, Suspect: 8, Unassessed: 2 },
  previous: { total: 90, suspect: 6, avg_score: 71, clear: 80, doubtful: 10, unassessed: 4 },
} as unknown as AnalyticsSummary;

describe("KpiRow", () => {
  it("shows band-rate KPIs and NO avg score", () => {
    render(<KpiRow analytics={a} />);
    expect(screen.getByText("Doubtful rate")).toBeInTheDocument();
    expect(screen.getByText("Unassessed rate")).toBeInTheDocument();
    expect(screen.queryByText("Avg score")).toBeNull();
  });
});
