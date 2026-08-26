import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("carries a visible focus-visible ring", () => {
    render(<Button>Re-run</Button>);
    expect(screen.getByRole("button").className).toContain("focus-visible:ring");
  });
});
