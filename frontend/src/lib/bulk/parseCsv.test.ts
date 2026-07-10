import { describe, expect, it } from "vitest";

import { buildBulkRows, parseCsv } from "./parseCsv";

describe("parseCsv", () => {
  it("parses a simple comma-delimited CSV with a header row", () => {
    const csv = "Agent ID,Image URL\nA1,https://example.com/a.jpg\nA2,https://example.com/b.jpg";
    const { headers, rows } = parseCsv(csv);
    expect(headers).toEqual(["Agent ID", "Image URL"]);
    expect(rows).toEqual([
      { "Agent ID": "A1", "Image URL": "https://example.com/a.jpg" },
      { "Agent ID": "A2", "Image URL": "https://example.com/b.jpg" },
    ]);
  });

  it("handles CRLF line endings", () => {
    const csv = "Agent ID,Image URL\r\nA1,https://example.com/a.jpg\r\nA2,https://example.com/b.jpg\r\n";
    const { headers, rows } = parseCsv(csv);
    expect(headers).toEqual(["Agent ID", "Image URL"]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({ "Agent ID": "A1", "Image URL": "https://example.com/a.jpg" });
  });

  it("handles quoted fields containing commas", () => {
    const csv = 'Name,Note\n"Doe, John","Says ""hello"" there"';
    const { headers, rows } = parseCsv(csv);
    expect(headers).toEqual(["Name", "Note"]);
    expect(rows).toEqual([{ Name: "Doe, John", Note: 'Says "hello" there' }]);
  });

  it("handles quoted fields containing newlines", () => {
    const csv = 'Name,Note\n"Jane","Line one\nLine two"\nBob,plain';
    const { headers, rows } = parseCsv(csv);
    expect(rows).toEqual([
      { Name: "Jane", Note: "Line one\nLine two" },
      { Name: "Bob", Note: "plain" },
    ]);
  });

  it("skips blank trailing lines", () => {
    const csv = "A,B\n1,2\n\n";
    const { rows } = parseCsv(csv);
    expect(rows).toEqual([{ A: "1", B: "2" }]);
  });

  it("pads missing trailing columns with empty string", () => {
    const csv = "A,B,C\n1,2";
    const { rows } = parseCsv(csv);
    expect(rows).toEqual([{ A: "1", B: "2", C: "" }]);
  });

  it("returns empty headers/rows for an empty string", () => {
    expect(parseCsv("")).toEqual({ headers: [], rows: [] });
  });

  it("returns headers with no rows when only a header line is present", () => {
    const { headers, rows } = parseCsv("A,B");
    expect(headers).toEqual(["A", "B"]);
    expect(rows).toEqual([]);
  });
});

describe("buildBulkRows", () => {
  const rows = [
    { "Image URL": "https://example.com/a.jpg", "Agent ID": "A1", "Opp ID": "O1" },
    { "Image URL": "", "Agent ID": "A2", "Opp ID": "O2" },
    { "Image URL": "  https://example.com/c.jpg  ", "Agent ID": "A3", "Opp ID": "" },
  ];

  it("maps rows to the POST shape using the given column mapping", () => {
    const { valid, skipped } = buildBulkRows(rows, {
      imageCol: "Image URL",
      repIdCol: "Agent ID",
      opportunityIdCol: "Opp ID",
    });
    expect(valid).toEqual([
      { image_url: "https://example.com/a.jpg", rep_id: "A1", opportunity_id: "O1" },
      { image_url: "https://example.com/c.jpg", rep_id: "A3", opportunity_id: null },
    ]);
    expect(skipped).toBe(1);
  });

  it("skips rows with no image URL (missing, blank, or whitespace-only)", () => {
    const { valid, skipped } = buildBulkRows(
      [
        { Image: "" },
        { Image: "   " },
        { Image: "https://example.com/x.jpg" },
      ],
      { imageCol: "Image" },
    );
    expect(valid).toEqual([{ image_url: "https://example.com/x.jpg", rep_id: null, opportunity_id: null }]);
    expect(skipped).toBe(2);
  });

  it("returns rep_id/opportunity_id as null when no mapping column is given", () => {
    const { valid } = buildBulkRows([{ Image: "https://example.com/x.jpg" }], { imageCol: "Image" });
    expect(valid).toEqual([{ image_url: "https://example.com/x.jpg", rep_id: null, opportunity_id: null }]);
  });

  it("treats a blank mapped rep/opportunity value as null", () => {
    const { valid } = buildBulkRows(
      [{ Image: "https://example.com/x.jpg", Rep: "", Opp: "  " }],
      { imageCol: "Image", repIdCol: "Rep", opportunityIdCol: "Opp" },
    );
    expect(valid).toEqual([{ image_url: "https://example.com/x.jpg", rep_id: null, opportunity_id: null }]);
  });

  it("handles an empty rows array", () => {
    expect(buildBulkRows([], { imageCol: "Image" })).toEqual({ valid: [], skipped: 0 });
  });
});
