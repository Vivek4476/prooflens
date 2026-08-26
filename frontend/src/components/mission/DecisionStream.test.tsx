import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DecisionStream } from "./DecisionStream";
import type { ResultItem } from "@/lib/api/types";

const items = [
  { id: "1", band: "Clear", score: 86, rep_id: "Amit", opportunity_id: "OPP-1",
    created_at: "2026-08-25T10:00:00Z", checks: [] },
  { id: "2", band: "Suspect", score: 18, rep_id: "Raj", opportunity_id: "OPP-2",
    created_at: "2026-08-25T09:59:00Z", checks: [] },
] as unknown as ResultItem[];

describe("DecisionStream", () => {
  it("renders a row per decision and calls onSelect when a row is clicked", () => {
    const onSelect = vi.fn();
    render(<DecisionStream items={items} newIds={new Set(["1"])} onSelect={onSelect} />);
    expect(screen.getByText("Amit")).toBeInTheDocument();
    expect(screen.getByText("Raj")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Amit").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith(items[0]);
  });

  it("applies cascade-in to fresh rows only", () => {
    const freshItems = [
      { id: "a", band: "Clear", score: 86, rep_id: "Fresh", opportunity_id: "OPP-A",
        created_at: "2026-08-25T10:00:00Z", checks: [] },
    ] as unknown as ResultItem[];
    const { container } = render(
      <DecisionStream items={freshItems} newIds={new Set(["a"])} onSelect={() => {}} />
    );
    const row = container.querySelector('[data-decision-id="a"]')!;
    expect(row).toBeTruthy();
    expect(row.className).toContain("animate-cascade-in");
  });

  it("does not apply cascade-in to stale rows", () => {
    const staleItems = [
      { id: "b", band: "Suspect", score: 18, rep_id: "Stale", opportunity_id: "OPP-B",
        created_at: "2026-08-25T09:59:00Z", checks: [] },
    ] as unknown as ResultItem[];
    const { container } = render(
      <DecisionStream items={staleItems} newIds={new Set()} onSelect={() => {}} />
    );
    const row = container.querySelector('[data-decision-id="b"]')!;
    expect(row).toBeTruthy();
    expect(row.className).not.toContain("animate-cascade-in");
  });
});
