import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResultsTable } from "./ResultsTable";
import type { ResultItem } from "@/lib/api/types";

// Mock next/navigation used inside ResultsTable
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const items = [
  {
    id: "r1",
    band: "Clear",
    score: 86,
    reason: "All checks passed",
    rep_id: "Amit",
    opportunity_id: "OPP-1",
    source: "camera",
    processing_ms: 1234,
    created_at: "2026-08-25T10:00:00Z",
    checks: [],
  },
] as unknown as ResultItem[];

describe("ResultsTable", () => {
  it("has a sticky header and tabular numeric cells", () => {
    const { container } = render(<ResultsTable items={items} />);
    expect(container.querySelector("thead")?.className).toContain("sticky");
    expect(container.querySelector("[data-cell='score']")?.className).toContain("tabular-nums");
  });
});
