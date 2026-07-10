import { describe, expect, it } from "vitest";

import type { BulkResultItem } from "@/lib/api/types";

import { bulkResultsToCsv } from "./exportBulkCsv";

function row(overrides: Partial<BulkResultItem>): BulkResultItem {
  return {
    image_url: "https://lsq.example/p.jpg",
    rep_id: null,
    opportunity_id: null,
    band: null,
    score: null,
    reason_code: null,
    result_id: null,
    error: null,
    ...overrides,
  };
}

describe("bulkResultsToCsv", () => {
  it("emits a header row and one line per result", () => {
    const csv = bulkResultsToCsv([row({ band: "Clear", score: 91 })]);
    const lines = csv.trimEnd().split("\n");
    expect(lines[0]).toBe(
      "image_url,rep_id,opportunity_id,band,score,reason_code,result_id,error",
    );
    expect(lines).toHaveLength(2);
    expect(lines[1]).toContain("Clear");
    expect(lines[1]).toContain("91");
  });

  it("neutralizes spreadsheet formula-injection on string cells", () => {
    // An attacker-influenced field (from the uploaded CSV) starting with =/+/-/@
    // must be prefixed with a quote so Excel/Sheets won't execute it.
    const csv = bulkResultsToCsv([
      row({ rep_id: "=cmd|'/bin/sh'!A1", error: "@SUM(1+1)" }),
    ]);
    const line = csv.trimEnd().split("\n")[1];
    // The dangerous cells are quote-prefixed so no cell starts with =/@.
    expect(line).toContain(`'=cmd|'/bin/sh'!A1`);
    expect(line).toContain(`'@SUM(1+1)`);
    expect(line).not.toMatch(/(^|,)[=@]/); // no cell starts with a bare = or @
  });

  it("leaves a legitimate negative score untouched (no quote prefix)", () => {
    // score is a number, not a string, so the guard must not mangle it.
    const csv = bulkResultsToCsv([row({ score: -3 as unknown as number })]);
    const line = csv.trimEnd().split("\n")[1];
    expect(line).toContain(",-3,");
    expect(line).not.toContain(`'-3`);
  });
});
