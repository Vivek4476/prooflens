// frontend/src/components/decision/DecisionDrawer.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionDrawer } from "./DecisionDrawer";
import type { ResultItem } from "@/lib/api/types";

const result = {
  id: "OPP-1", created_at: "2026-08-25T10:00:00Z", band: "Suspect", score: 18,
  reason: "Reused image", reason_code: "recycled", rubric_version: "v3",
  processing_ms: 1200, source: "webhook", opportunity_id: "OPP-1", rep_id: "R1",
  checks: [{ name: "uniqueness", available: true, score: 5, summary: "near-dupe", data: {} }],
  copilot_summary: "Scored Suspect because reused imagery.",
} as unknown as ResultItem;

describe("DecisionDrawer", () => {
  it("renders nothing when result is null", () => {
    const { container } = render(<DecisionDrawer result={null} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("shows the band word, the copilot summary, and NO adjudication control", () => {
    render(<DecisionDrawer result={result} onClose={() => {}} />);
    expect(screen.getByText("Suspect")).toBeInTheDocument();
    expect(screen.getByText(/reused imagery/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /mark genuine|confirm fraud/i })).toBeNull();
    expect(screen.getByText(/written back to lsq/i)).toBeInTheDocument();
  });
});
