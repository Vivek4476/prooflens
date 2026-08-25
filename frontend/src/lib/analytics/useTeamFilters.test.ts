import { describe, it, expect } from "vitest";
import { teamParams } from "./useTeamFilters";

describe("teamParams", () => {
  it("includes dim, node, and group_by=agent", () => {
    const p = teamParams({ start_date: "2026-08-01", end_date: "2026-08-30", bucket: "daily" }, "branch", "North");
    expect(p).toEqual({
      start_date: "2026-08-01", end_date: "2026-08-30", bucket: "daily",
      group_by: "agent", dim: "branch", node: "North",
    });
  });
});
