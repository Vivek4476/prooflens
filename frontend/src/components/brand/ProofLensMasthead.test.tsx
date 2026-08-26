import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProofLensMasthead } from "./ProofLensMasthead";

describe("ProofLensMasthead", () => {
  it("renders exactly one gold hairline element", () => {
    const { container } = render(<ProofLensMasthead />);
    const hairlines = container.querySelectorAll('[data-hairline="gold"]');
    expect(hairlines.length).toBe(1);
  });
});
