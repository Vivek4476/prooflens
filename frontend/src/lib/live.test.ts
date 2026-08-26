import { describe, it, expect } from "vitest";
import { pickNewIds } from "./live";
import type { ResultItem } from "./api/types";

const r = (id: string): ResultItem => ({ id } as ResultItem);

describe("pickNewIds", () => {
  it("returns ids present in next but not in prev", () => {
    const out = pickNewIds(["a", "b"], [r("c"), r("b"), r("a")]);
    expect(out).toEqual(new Set(["c"]));
  });
  it("is empty when nothing is new", () => {
    expect(pickNewIds(["a", "b"], [r("a"), r("b")])).toEqual(new Set());
  });
  it("treats the first load as no-animation (empty prev -> empty new)", () => {
    expect(pickNewIds([], [r("a"), r("b")])).toEqual(new Set());
  });
});
