import { describe, it, expect } from "vitest";
import { bandRate } from "./bandRates";

describe("bandRate", () => {
  const dist = { Clear: 70, Doubtful: 20, Suspect: 8, Unassessed: 2 };
  it("returns the band's percentage of total", () => {
    expect(bandRate(dist, 100, "Doubtful")).toBe(20);
    expect(bandRate(dist, 100, "Unassessed")).toBe(2);
  });
  it("returns 0 when total is 0", () => {
    expect(bandRate({ Clear: 0, Doubtful: 0, Suspect: 0, Unassessed: 0 }, 0, "Suspect")).toBe(0);
  });
});
