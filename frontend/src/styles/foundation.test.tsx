import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("foundation utilities", () => {
  it("applies new type + shadow + font utilities without error", () => {
    const { container } = render(
      <div className="font-serif text-display-lg shadow-3 animate-cascade-in card-glow">ProofLens</div>,
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("font-serif");
    expect(el.className).toContain("text-display-lg");
    expect(el.className).toContain("card-glow");
  });
});
