import { test, expect, type Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";

/**
 * Task 1 (v4 Gate 1, Pain 1): reproduce — or rule out — the "Top Flag Reasons
 * overflows its container" bug with adversarial data, BEFORE any fix lands.
 *
 * This spec mocks GET /v1/analytics/summary with a deliberately worst-case
 * `top_reasons` payload (20 distinct reasons, several with long short_labels
 * and long full sentences) so every card on /analytics renders with realistic
 * data, then screenshots + asserts no scroll overflow at three breakpoints in
 * both themes.
 */

const SCREENSHOT_DIR = path.join(__dirname, "__screenshots__");
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "768x1024", width: 768, height: 1024 },
];

const THEMES = ["light", "dark"] as const;

// 20 distinct reasons, mixing short and deliberately long short_labels/sentences,
// so both the default (limit=5/10) and "Show all" (limit=20) states get exercised.
const LONG_LABELS = [
  "Screenshot of another rep's already-submitted visibility photo, re-uploaded as if it were a fresh capture",
  "EXIF capture timestamp is more than 14 days older than the upload timestamp, suggesting a stale gallery photo",
  "Duplicate perceptual hash matches an image already scored for a different outlet in the same visit window",
  "Image sharpness score falls below the blur floor threshold — likely motion blur or an out-of-focus capture",
  "Recaptured-from-screen artifact detected (moire pattern / screen glare consistent with photographing a display)",
];

const SHORT_LABELS = [
  "Blur",
  "Duplicate",
  "Screenshot",
  "Stale EXIF",
  "Recapture",
  "Low content match",
  "Missing GPS",
  "Wrong outlet",
  "Low light",
  "Cropped",
  "Watermark",
  "Compression artifacts",
  "Aspect ratio mismatch",
  "Night flash",
  "Overexposed",
];

const REASON_CODES = [
  "screenshot_reupload",
  "stale_exif_gap",
  "duplicate_cross_outlet",
  "blur_floor",
  "recapture_moire",
  "low_content_match",
  "missing_gps",
  "wrong_outlet",
  "low_light",
  "cropped_frame",
  "watermark_detected",
  "compression_artifacts",
  "aspect_ratio_mismatch",
  "night_flash",
  "overexposed",
  "underexposed_shadow_clip",
  "duplicate_same_outlet",
  "metadata_stripped",
  "resolution_too_low",
  "content_mismatch_sku",
];

function buildTopReasons() {
  return REASON_CODES.map((code, i) => {
    const isLong = i < LONG_LABELS.length;
    return {
      reason_code: code,
      reason: isLong
        ? `Verdict: ${LONG_LABELS[i]}. This sentence is intentionally long to stress-test the tooltip and any wrapping behavior in the row.`
        : `Verdict: flagged for ${SHORT_LABELS[i - LONG_LABELS.length] ?? code}.`,
      short_label: isLong ? LONG_LABELS[i] : (SHORT_LABELS[i - LONG_LABELS.length] ?? code),
      // Descending counts so rank ordering is stable and bar widths vary.
      count: (REASON_CODES.length - i) * 7 + 3,
    };
  });
}

function buildBuckets() {
  const buckets = [];
  const start = new Date("2026-06-09T00:00:00Z");
  for (let i = 0; i < 30; i++) {
    const d = new Date(start.getTime() + i * 86400000);
    const iso = d.toISOString().slice(0, 10);
    const total = 20 + ((i * 7) % 15);
    const suspect = Math.round(total * 0.15);
    const doubtful = Math.round(total * 0.25);
    const clear = total - suspect - doubtful;
    buckets.push({
      bucket_label: iso,
      start: iso,
      end: iso,
      clear,
      doubtful,
      suspect,
      total,
      avg_score: 72.5,
      incomplete: false,
    });
  }
  return buckets;
}

function buildAnalyticsSummary() {
  const topReasons = buildTopReasons();
  const buckets = buildBuckets();
  const total = buckets.reduce((s, b) => s + b.total, 0);
  const suspect = buckets.reduce((s, b) => s + b.suspect, 0);
  const doubtful = buckets.reduce((s, b) => s + b.doubtful, 0);
  const clear = total - suspect - doubtful;

  return {
    total,
    images_today: 42,
    band_distribution: { Clear: clear, Doubtful: doubtful, Suspect: suspect },
    suspect_pct: (suspect / total) * 100,
    avg_score: 74.3,
    avg_processing_ms: 812,
    duplicates_caught: 17,
    top_reasons: topReasons,
    series: [],
    buckets,
    incomplete: false,
    previous: { clear: clear - 10, doubtful: doubtful - 5, suspect: suspect - 2, total: total - 17, avg_score: 73.1 },
    period: { from: "2026-06-09", to: "2026-07-08" },
    previous_period: { from: "2026-05-10", to: "2026-06-08" },
    groups: [],
  };
}

async function mockAnalytics(page: Page) {
  const payload = buildAnalyticsSummary();
  await page.route("**/v1/analytics/summary**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
}

async function setTheme(page: Page, theme: "light" | "dark") {
  // Match app's next-themes wiring: `attribute="class"` on <html>, toggled via
  // ThemeToggle -> useTheme().setTheme(). Driving localStorage before navigation
  // is the simplest reliable way to land directly in the target theme (next-themes
  // reads `theme` from localStorage on mount with defaultTheme="light").
  await page.addInitScript((t) => {
    window.localStorage.setItem("theme", t);
  }, theme);
}

interface OverflowResult {
  selector: string;
  scrollWidth: number;
  clientWidth: number;
  scrollHeight: number;
  clientHeight: number;
  overflowsX: boolean;
  overflowsY: boolean;
  text: string | null;
}

async function checkCardOverflow(page: Page): Promise<OverflowResult[]> {
  return page.evaluate(() => {
    const results: OverflowResult[] = [];
    // Every analytics card is a `Card` (see src/components/ui/Card.tsx, class="card").
    // Check all of them, not just TopFlagReasons, per the task brief.
    const cards = document.querySelectorAll("main .card");
    const seen = new Set<Element>();
    cards.forEach((el) => {
      if (seen.has(el)) return;
      seen.add(el);
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      const overflowsX = el.scrollWidth > el.clientWidth + 1;
      const overflowsY = el.scrollHeight > el.clientHeight + 1;
      if (overflowsX || overflowsY) {
        results.push({
          selector: el.className.toString().slice(0, 80),
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
          overflowsX,
          overflowsY,
          text: el.textContent?.slice(0, 60) ?? null,
        });
      }
    });
    return results;
  });
}

for (const theme of THEMES) {
  for (const vp of VIEWPORTS) {
    test(`TopFlagReasons + analytics cards do not overflow — ${theme} @ ${vp.name}`, async ({ page }) => {
      await setTheme(page, theme);
      await mockAnalytics(page);
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/analytics");

      // Wait for the real content to replace the loading skeleton.
      await expect(page.getByText("Top flag reasons")).toBeVisible({ timeout: 15_000 });

      // Default state (limit=5) screenshot.
      await page.waitForTimeout(400); // let chart draw-in animations (≤400ms) settle
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${theme}-${vp.name}-default.png`),
        fullPage: true,
      });

      // Switch to "Show all" (20 reasons) to force the worst-case row count.
      const select = page.getByLabel("Number of flag reasons to show");
      await select.selectOption("all");
      await page.waitForTimeout(200);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${theme}-${vp.name}-show-all.png`),
        fullPage: true,
      });

      // Also screenshot just the TopFlagReasons card region, cropped, for close review.
      const cardLocator = page.locator(".card", { has: page.getByText("Top flag reasons") });
      if (await cardLocator.count()) {
        await cardLocator.first().screenshot({
          path: path.join(SCREENSHOT_DIR, `${theme}-${vp.name}-card-only.png`),
        }).catch(() => {});
      }

      // --- Assertions: outer Card element must not scroll-overflow ---
      const cardEl = cardLocator.first();
      const cardBox = await cardEl.evaluate((el) => ({
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
      }));
      expect(cardBox.scrollHeight, `Card scrollHeight (${cardBox.scrollHeight}) should be <= clientHeight (${cardBox.clientHeight})`).toBeLessThanOrEqual(cardBox.clientHeight + 1);
      expect(cardBox.scrollWidth, `Card scrollWidth (${cardBox.scrollWidth}) should be <= clientWidth (${cardBox.clientWidth})`).toBeLessThanOrEqual(cardBox.clientWidth + 1);

      // --- Assertions: every row's short_label span must not overflow horizontally ---
      //
      // NOTE on methodology: for an element with `overflow: hidden; text-overflow:
      // ellipsis; white-space: nowrap` (Tailwind's `.truncate`, used here by design),
      // `scrollWidth > clientWidth` is EXPECTED whenever the label text is long enough
      // to truncate — `scrollWidth` reports the untruncated intrinsic content width,
      // it does not mean the content is visually escaping anything. So this spec
      // captures both:
      //   (a) the literal scrollWidth/clientWidth check the task brief asked for
      //       (kept for the record — see task-1-report.md for why it always "fails"
      //       on any truncated long label and should not gate a real fix), and
      //   (b) the check that actually matters: does the rendered label's bounding
      //       box stay within its card's right edge (no visual escape)?
      const rowSpanBoxes = await page.evaluate(() => {
        const lists = Array.from(document.querySelectorAll("ol"));
        const out: {
          scrollWidth: number;
          clientWidth: number;
          text: string;
          spanRight: number;
          cardRight: number;
        }[] = [];
        for (const ol of lists) {
          const card = ol.closest(".card");
          const cardRight = card ? card.getBoundingClientRect().right : Infinity;
          const spans = ol.querySelectorAll("li span.truncate");
          spans.forEach((s) => {
            out.push({
              scrollWidth: s.scrollWidth,
              clientWidth: s.clientWidth,
              text: s.textContent ?? "",
              spanRight: s.getBoundingClientRect().right,
              cardRight,
            });
          });
        }
        return out;
      });

      // (b) Real visual-overflow check: the rendered (post-ellipsis) box must not
      // extend past its card's right edge. This is the one that should gate a fix.
      for (const box of rowSpanBoxes) {
        expect(
          box.spanRight,
          `Row label "${box.text}" right edge (${box.spanRight}) escapes its card's right edge (${box.cardRight})`,
        ).toBeLessThanOrEqual(box.cardRight + 1);
      }

      // (a) Literal brief assertion, recorded but not treated as the source of truth
      // for "is there a bug" — see NOTE above. Logged rather than asserted so a
      // long-label test fixture doesn't perpetually fail this spec for expected
      // ellipsis behavior; Task 2 should read task-1-report.md before deciding
      // whether/how to act on any logged mismatches here.
      const literalMismatches = rowSpanBoxes.filter((b) => b.scrollWidth > b.clientWidth + 1);
      if (literalMismatches.length > 0) {
        // eslint-disable-next-line no-console
        console.log(
          `[info, expected for truncated labels] scrollWidth>clientWidth on ${literalMismatches.length} row(s) at ${theme} @ ${vp.name} — this is normal ellipsis behavior, not visual overflow (see spanRight/cardRight above).`,
        );
      }

      // --- Assertions: no card anywhere on the page overflows ---
      const overflows = await checkCardOverflow(page);
      if (overflows.length > 0) {
        // eslint-disable-next-line no-console
        console.log(`Overflow detected (${theme} @ ${vp.name}):`, JSON.stringify(overflows, null, 2));
      }
      expect(overflows, `One or more cards overflow at ${theme} @ ${vp.name}`).toEqual([]);
    });
  }
}
