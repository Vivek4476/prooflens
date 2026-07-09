import { describe, expect, it } from "vitest";

import { mergeState, parseState, serializeState } from "./useUrlState";

interface FilterState extends Record<string, string | undefined> {
  range: string;
  bucket: string;
  group_by: string;
}

const defaults: FilterState = {
  range: "30d",
  bucket: "daily",
  group_by: "none",
};

const allowedKeys: (keyof FilterState)[] = ["range", "bucket", "group_by"];

describe("serializeState", () => {
  it("round-trips a full non-default state object through serialize -> querystring -> parse", () => {
    const state: FilterState = { range: "7d", bucket: "weekly", group_by: "zone" };

    const serialized = serializeState(state, defaults);
    const qs = new URLSearchParams(serialized).toString();
    const parsed = parseState(new URLSearchParams(qs), defaults, allowedKeys);

    expect(parsed).toEqual(state);
  });

  it("omits keys whose value equals the default (keeps URLs clean)", () => {
    const state: FilterState = { range: "30d", bucket: "daily", group_by: "zone" };

    const serialized = serializeState(state, defaults);

    expect(serialized).toEqual({ group_by: "zone" });
    expect(serialized).not.toHaveProperty("range");
    expect(serialized).not.toHaveProperty("bucket");
  });

  it("treats empty-string values as absent", () => {
    const state: FilterState = { range: "", bucket: "weekly", group_by: "none" };

    const serialized = serializeState(state, defaults);

    expect(serialized).toEqual({ bucket: "weekly" });
    expect(serialized).not.toHaveProperty("range");
  });

  it("omits undefined values", () => {
    const state: Record<string, string | undefined> = {
      range: "7d",
      bucket: undefined,
      group_by: "none",
    };

    const serialized = serializeState(state, defaults);

    expect(serialized).toEqual({ range: "7d" });
  });
});

describe("parseState", () => {
  it("fills in defaults for missing keys", () => {
    const params = new URLSearchParams("range=7d");

    const parsed = parseState(params, defaults, allowedKeys);

    expect(parsed).toEqual({ range: "7d", bucket: "daily", group_by: "none" });
  });

  it("ignores unknown/unrelated query params", () => {
    const params = new URLSearchParams("range=7d&utm_source=newsletter&foo=bar");

    const parsed = parseState(params, defaults, allowedKeys);

    expect(parsed).toEqual({ range: "7d", bucket: "daily", group_by: "none" });
  });

  it("treats an empty-string query value as absent and falls back to default", () => {
    const params = new URLSearchParams("range=&bucket=monthly");

    const parsed = parseState(params, defaults, allowedKeys);

    expect(parsed).toEqual({ range: "30d", bucket: "monthly", group_by: "none" });
  });

  it("returns all defaults when given an empty querystring", () => {
    const parsed = parseState(new URLSearchParams(""), defaults, allowedKeys);

    expect(parsed).toEqual(defaults);
  });
});

describe("mergeState (multi-instance URL safety)", () => {
  it("preserves foreign params owned by other useUrlState instances", () => {
    // The page has range=90d (global filters) AND trend_agg=weekly (another instance).
    const current = new URLSearchParams("range=90d&trend_agg=weekly");
    // This instance only owns bandmix_agg; it sets bandmix_agg=monthly.
    const next = { bandmix_agg: "monthly" } as Record<string, string | undefined>;
    const merged = mergeState(current, next, { bandmix_agg: "page" }, ["bandmix_agg"]);

    // range and trend_agg (foreign) are untouched; bandmix_agg is added.
    expect(merged.get("range")).toBe("90d");
    expect(merged.get("trend_agg")).toBe("weekly");
    expect(merged.get("bandmix_agg")).toBe("monthly");
  });

  it("removes an owned key when it returns to its default, leaving foreign params", () => {
    const current = new URLSearchParams("range=90d&bandmix_agg=monthly");
    const next = { bandmix_agg: "page" } as Record<string, string | undefined>;
    const merged = mergeState(current, next, { bandmix_agg: "page" }, ["bandmix_agg"]);

    expect(merged.has("bandmix_agg")).toBe(false); // cleared (equals default)
    expect(merged.get("range")).toBe("90d"); // foreign param kept
  });

  it("only ever touches its own allowedKeys", () => {
    const current = new URLSearchParams("q=blur&reason=too_blurred");
    // A hook that owns only 'band' sets band=Suspect — q and reason must survive.
    const merged = mergeState(
      current,
      { band: "Suspect" } as Record<string, string | undefined>,
      {},
      ["band"],
    );
    expect(merged.get("q")).toBe("blur");
    expect(merged.get("reason")).toBe("too_blurred");
    expect(merged.get("band")).toBe("Suspect");
  });
});
