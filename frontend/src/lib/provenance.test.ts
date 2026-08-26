import { describe, it, expect } from "vitest";
import { provenanceSignal } from "./provenance";
import type { CheckOutcome } from "./api/types";

const c = (name: string, available: boolean, score: number | null): CheckOutcome =>
  ({ name, available, score, summary: "", data: {}, metric: null, latency_ms: null } as CheckOutcome);

describe("provenanceSignal", () => {
  it("signed when exif is available and strong", () => {
    expect(provenanceSignal([c("exif", true, 90)]).state).toBe("signed");
  });
  it("unsigned when a screen recapture is detected", () => {
    expect(provenanceSignal([c("exif", true, 90), c("recapture", true, 5)]).state).toBe("unsigned");
  });
  it("unsigned when exif is unavailable", () => {
    expect(provenanceSignal([c("exif", false, null)]).state).toBe("unsigned");
  });
  it("na when there are no relevant checks", () => {
    expect(provenanceSignal([c("content", true, 80)]).state).toBe("na");
  });
});
