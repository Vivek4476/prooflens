import { test, expect } from "@playwright/test";

/**
 * Mobile smoke test (375px). Guards the class of regression that shipped
 * invisibly once — nothing below the `md` breakpoint had e2e coverage:
 *
 *  1. No route scrolls horizontally at phone width (the universal "something
 *     overflowed" signal).
 *  2. The mobile nav drawer opens as a FULL-HEIGHT viewport-relative panel and
 *     closes on Escape. This directly guards the backdrop-blur containing-block
 *     bug: the Topbar <header> has a backdrop-filter, which makes `fixed`
 *     descendants clip to the 64px header unless the overlay is portaled to
 *     <body>. If the portal regresses, the drawer height collapses (~63px) and
 *     this test fails.
 *  3. The Review keyboard-shortcuts bar is hidden on touch (no keyboard).
 *
 * Assumes `npm run dev` (or an equivalent server) is running at the config's
 * baseURL, same as analytics-overflow.spec.ts.
 */

const MOBILE = { width: 375, height: 812 };

test.use({ viewport: MOBILE });

// Every app route + its <h1> (from PageHeader), which renders immediately and
// independently of data, so waiting on it is a stable "page mounted" signal.
const ROUTES: { path: string; heading: string }[] = [
  { path: "/", heading: "Dashboard" },
  { path: "/analytics", heading: "Analytics" },
  { path: "/history", heading: "Upload history" },
  { path: "/review", heading: "Review queue" },
  { path: "/settings", heading: "Settings" },
  { path: "/dse", heading: "DSE scorecard" },
  { path: "/bulk", heading: "Bulk upload" },
];

for (const route of ROUTES) {
  test(`no horizontal overflow at 375px — ${route.path}`, async ({ page }) => {
    await page.goto(route.path);
    await expect(page.getByRole("heading", { level: 1, name: route.heading })).toBeVisible({
      timeout: 15_000,
    });
    await page.waitForTimeout(400); // let any chart/skeleton settle into final layout

    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(
      scrollWidth,
      `${route.path} scrolls horizontally at 375px (scrollWidth ${scrollWidth} > clientWidth ${clientWidth})`,
    ).toBeLessThanOrEqual(clientWidth + 1);
  });
}

test("mobile nav drawer opens full-height and closes on Escape", async ({ page }) => {
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Open navigation" });
  await expect(trigger).toBeVisible();
  await trigger.click();

  const drawer = page.getByRole("dialog", { name: "Navigation" });
  await expect(drawer).toBeVisible();

  // Regression guard for the backdrop-blur containing-block bug: the drawer must
  // fill the viewport height, not clip to the ~64px header. A collapsed drawer
  // (the bug) measured ~63px tall.
  const box = await drawer.boundingBox();
  expect(box).not.toBeNull();
  expect(
    box!.height,
    `drawer height ${box!.height} should ~fill the ${MOBILE.height}px viewport (not clip to the header)`,
  ).toBeGreaterThan(MOBILE.height - 40);
  expect(box!.y, "drawer should start at the top of the viewport").toBeLessThanOrEqual(1);

  // Its nav links are present (SidebarInner rendered inside the drawer).
  await expect(drawer.getByRole("link", { name: "Analytics" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});

test("review keyboard-shortcuts bar is hidden on mobile", async ({ page }) => {
  await page.goto("/review");
  await expect(page.getByRole("heading", { level: 1, name: "Review queue" })).toBeVisible({
    timeout: 15_000,
  });
  // Hidden below `sm` (no keyboard on touch); present in the DOM but display:none.
  await expect(page.getByText("Keyboard:")).toBeHidden();
});
