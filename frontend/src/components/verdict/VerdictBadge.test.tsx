import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerdictBadge } from "./VerdictBadge";

describe("VerdictBadge", () => {
  it("always shows the band word and renders score in mono tabular", () => {
    render(<VerdictBadge band="Suspect" score={18} />);
    expect(screen.getByText(/Suspect/)).toBeInTheDocument();
    const score = screen.getByText("18");
    expect(score.className).toContain("font-mono");
    expect(score.className).toContain("tabular-nums");
  });

  it("does not show score for Unassessed band", () => {
    render(<VerdictBadge band="Unassessed" score={5} />);
    expect(screen.getByText(/Unassessed/)).toBeInTheDocument();
    expect(screen.queryByText("5")).not.toBeInTheDocument();
  });

  it("does not show score when score is not provided", () => {
    const { getByText } = render(<VerdictBadge band="Clear" />);
    expect(getByText(/Clear/)).toBeInTheDocument();
  });

  it("accepts size prop without breaking (backward compat)", () => {
    render(<VerdictBadge band="Doubtful" size="lg" />);
    expect(screen.getByText(/Doubtful/)).toBeInTheDocument();
  });

  it("accepts className prop without breaking (backward compat)", () => {
    const { container } = render(<VerdictBadge band="Clear" className="custom-class" />);
    expect(container.querySelector(".custom-class")).toBeInTheDocument();
  });
});
