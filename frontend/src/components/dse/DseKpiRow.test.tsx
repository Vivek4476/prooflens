import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DseKpiRow } from "./DseKpiRow";

describe("DseKpiRow", () => {
  it("shows Unassessed rate, not Avg score", () => {
    render(
      <DseKpiRow
        total={50}
        suspectRate={0.1}
        bandDistribution={{ Clear: 40, Doubtful: 5, Suspect: 5, Unassessed: 0 }}
      />,
    );
    expect(screen.getByText("Unassessed rate")).toBeInTheDocument();
    expect(screen.queryByText("Avg score")).toBeNull();
  });
});
