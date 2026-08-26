import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreRing } from "./ScoreRing";

describe("ScoreRing", () => {
  it("renders the rounded score and applies a band-colored progress stroke", () => {
    const { container } = render(<ScoreRing score={90.6} band="Clear" />);
    expect(screen.getByText("91")).toBeInTheDocument();
    const progress = container.querySelectorAll("circle")[1];
    expect(progress.getAttribute("stroke")).toBe("var(--verdict-clear)");
  });
});
