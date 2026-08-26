import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardHeader } from "./Card";

describe("Card", () => {
  it("adds card-glow when glow is set", () => {
    const { container } = render(<Card glow>x</Card>);
    expect((container.firstChild as HTMLElement).className).toContain("card-glow");
  });
  it("CardHeader renders a serif title when serif is set", () => {
    render(<CardHeader title="Live decision stream" serif />);
    expect(screen.getByText("Live decision stream").className).toContain("font-serif");
  });
});
