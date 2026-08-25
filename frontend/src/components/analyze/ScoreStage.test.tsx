import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScoreStage } from "./ScoreStage";

describe("ScoreStage", () => {
  it("renders nothing when idle (no result, not pending)", () => {
    const { container } = render(<ScoreStage result={null} pending={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
