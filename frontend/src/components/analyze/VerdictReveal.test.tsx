import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerdictReveal } from "./VerdictReveal";
import type { ScoreResponse } from "@/lib/api/types";

const base = {
  band: "Suspect", score: 18, reason: "Reused image", reason_code: "recycled",
  rubric_version: "v3", checks: [], result_id: "OPP-1", processing_ms: 1200,
  backend: "nvidia", backend_is_real: true,
} as unknown as ScoreResponse;

describe("VerdictReveal", () => {
  it("shows the band and the copilot summary when present", () => {
    render(<VerdictReveal result={{ ...base, copilot_summary: "Scored Suspect because reused." }} />);
    expect(screen.getByText("Suspect")).toBeInTheDocument();
    expect(screen.getByText(/reused\./i)).toBeInTheDocument();
  });
  it("falls back to reason when copilot_summary is null", () => {
    const result = { ...base, copilot_summary: null } as ScoreResponse;
    render(<VerdictReveal result={result} />);
    const summaryElements = screen.getAllByText("Reused image");
    const summaryEl = summaryElements.find(el => el.className.includes("text-body-sm"));
    expect(summaryEl).toBeInTheDocument();
  });
});
