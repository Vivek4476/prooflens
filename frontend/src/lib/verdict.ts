// Presentation helpers that READ the real Verdict — they never invent data.
import type { Band, CheckOutcome } from "./api/types";

export type CheckState = "pass" | "warn" | "fail" | "skip" | "info";

export const BAND_META: Record<
  Band,
  { label: Band; fg: string; bg: string; ring: string; dot: string }
> = {
  Clear: {
    label: "Clear",
    fg: "text-verdict-clear-fg",
    bg: "bg-verdict-clear-bg",
    ring: "var(--verdict-clear)",
    dot: "bg-verdict-clear",
  },
  Doubtful: {
    label: "Doubtful",
    fg: "text-verdict-doubtful-fg",
    bg: "bg-verdict-doubtful-bg",
    ring: "var(--verdict-doubtful)",
    dot: "bg-verdict-doubtful",
  },
  Suspect: {
    label: "Suspect",
    fg: "text-verdict-suspect-fg",
    bg: "bg-verdict-suspect-bg",
    ring: "var(--verdict-suspect)",
    dot: "bg-verdict-suspect",
  },
};

// Friendly labels for each check the backend can return. Only checks present in
// checks[] are ever shown — we never add checks the backend doesn't run.
export const CHECK_LABEL: Record<string, string> = {
  exif: "Capture metadata",
  sharpness: "Image sharpness",
  uniqueness: "Duplicate check",
  recapture: "Screen-photo check",
  content: "Scene & people",
};

// The pipeline stages, in gating order. `fusion` is the final decision, derived
// from the verdict band (there is no separate check for it).
export const PIPELINE_STAGES = [
  { key: "exif", label: "EXIF" },
  { key: "sharpness", label: "Sharpness" },
  { key: "uniqueness", label: "Uniqueness" },
  { key: "recapture", label: "Recapture" },
  { key: "content", label: "Content" },
  { key: "fusion", label: "Fusion" },
] as const;

/** Derive a pass/warn/fail/skip/info state from a real check's data. */
export function checkState(c: CheckOutcome): CheckState {
  if (!c.available) return "skip";
  const d = c.data || {};
  switch (c.name) {
    case "exif":
      return "info";
    case "sharpness":
      return d.too_blurred ? "warn" : "pass";
    case "uniqueness":
      if (d.exact_duplicate) return "fail";
      if (d.near_duplicate) return "warn";
      return "pass";
    case "recapture":
      return d.screen_detected ? "fail" : "pass";
    case "content": {
      if (d.looks_like_photo_of_a_screen || d.is_designed_graphic || d.is_meme_or_screenshot)
        return "fail";
      if (Number(d.people_count) === 0) return "warn";
      if (Number(d.plausibility) < 30) return "warn";
      return "pass";
    }
    default:
      return "info";
  }
}

/** Confidence 0-100 only where the backend genuinely provides it (content plausibility). */
export function checkConfidence(c: CheckOutcome): number | null {
  if (c.name === "content" && c.available && typeof c.data?.plausibility === "number") {
    return c.data.plausibility as number;
  }
  return null;
}

export function bandState(band: Band): CheckState {
  return band === "Clear" ? "pass" : band === "Doubtful" ? "warn" : "fail";
}

export const STATE_WORD: Record<CheckState, string> = {
  pass: "Pass",
  warn: "Review",
  fail: "Flag",
  skip: "Skipped",
  info: "Noted",
};
