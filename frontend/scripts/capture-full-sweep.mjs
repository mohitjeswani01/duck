// Full visual sweep for the final polish pass: every landing section at
// desktop + mobile, then one real live-Gemini session driven end to end
// through the actual UI, screenshotting every workspace phase (including
// clarifying, best-effort, since Duck may skip it). Run with:
//   node scripts/capture-full-sweep.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

const BASE_URL = "http://localhost:3000";
const OUT_DIR = new URL("../screenshots/", import.meta.url).pathname;
mkdirSync(OUT_DIR, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

async function shot(page, name, opts = {}) {
  await page.screenshot({ path: `${OUT_DIR}${name}.png`, fullPage: true, ...opts });
  console.log(`captured ${name}`);
}

async function shotSection(page, selector, name) {
  const el = page.locator(selector).first();
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await el.screenshot({ path: `${OUT_DIR}${name}.png` });
  console.log(`captured ${name}`);
}

async function captureLandingSections(page, suffix) {
  await page.goto(BASE_URL, { timeout: 60000, waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /explain the bug/i }).waitFor({ timeout: 30000 });
  await page.waitForTimeout(1500); // let the mini-demo animate in

  await shot(page, `landing-full-${suffix}`);
  await shotSection(page, "header", `landing-nav-${suffix}`);
  await shotSection(page, "#hero", `landing-hero-${suffix}`);
  await shotSection(page, "#try-a-bug", `landing-bug-picker-${suffix}`);
  await shotSection(page, "#how-it-works", `landing-how-it-works-${suffix}`);
  await shotSection(page, "#product-showcase", `landing-product-showcase-${suffix}`);
  await shotSection(page, "#why-voice", `landing-why-voice-${suffix}`);
  await shotSection(page, "#stats", `landing-stats-${suffix}`);
  await shotSection(page, "#wispr", `landing-wispr-${suffix}`);
  await shotSection(page, "#faq", `landing-faq-${suffix}`);
  await shotSection(page, "#final-cta", `landing-final-cta-${suffix}`);
  await shotSection(page, "footer", `landing-footer-${suffix}`);
}

async function main() {
  const browser = await chromium.launch();
  const desktopCtx = await browser.newContext({ viewport: DESKTOP });
  const mobileCtx = await browser.newContext({ viewport: MOBILE });
  const desktop = await desktopCtx.newPage();
  const mobile = await mobileCtx.newPage();

  console.log("=== landing page sections (desktop) ===");
  await captureLandingSections(desktop, "desktop");

  console.log("=== landing page sections (mobile) ===");
  await captureLandingSections(mobile, "mobile");

  console.log("=== own-repo FAQ entry check ===");
  await desktop.locator("details", { hasText: "What is taskboard?" }).click();
  await desktop.waitForTimeout(300);
  await shotSection(desktop, "#faq", "landing-faq-expanded-desktop");

  console.log("=== live session: clicking the pagination bug chip ===");
  await desktop.goto(BASE_URL, { timeout: 60000, waitUntil: "domcontentloaded" });
  await desktop.getByRole("button", { name: /task list skips items/i }).click();
  await desktop.waitForURL(/\/workspace\//, { timeout: 60000 });
  console.log("workspace URL:", desktop.url());

  await desktop.waitForTimeout(2500);
  await shot(desktop, "workspace-desktop-investigating");

  console.log("watching for a clarifying question (best-effort, Duck may skip it)...");
  try {
    await desktop.getByText(/\?/).first().waitFor({ timeout: 20000 });
    await shot(desktop, "workspace-desktop-clarifying");
    console.log("captured a clarifying moment");
  } catch {
    console.log("no clarifying question observed in the window — Duck skipped straight to investigating/hypothesis");
  }

  console.log("waiting for a hypothesis card...");
  await desktop.getByText(/confidence$/i).first().waitFor({ timeout: 150000 });
  await desktop.waitForTimeout(1000);
  await shot(desktop, "workspace-desktop-hypothesis");

  console.log("waiting for a fix proposal...");
  await desktop.getByRole("button", { name: /accept fix/i }).waitFor({ timeout: 150000 });
  await desktop.waitForTimeout(1000);
  await shot(desktop, "workspace-desktop-fix-proposed");

  const sessionUrl = desktop.url();
  await mobile.goto(sessionUrl, { timeout: 60000, waitUntil: "domcontentloaded" });
  await mobile.waitForTimeout(2000);
  await shot(mobile, "workspace-mobile-fix-proposed");

  console.log("accepting the fix...");
  await desktop.getByRole("button", { name: /accept fix/i }).click();

  console.log("waiting for resolution...");
  await desktop.getByText(/resolved!/i).waitFor({ timeout: 150000 });
  await desktop.waitForTimeout(2000); // let the one-shot confetti settle
  await shot(desktop, "workspace-desktop-resolved");

  await mobile.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await mobile.waitForTimeout(2000);
  await shot(mobile, "workspace-mobile-resolved");

  console.log("=== new-session (bring your own repo) empty-input screen ===");
  await desktop.goto(`${BASE_URL}/#try-a-bug`, { timeout: 60000, waitUntil: "domcontentloaded" });
  await desktop.getByPlaceholder("https://github.com/owner/repo").fill("https://github.com/mohitjeswani01/taskboard");
  await desktop.getByRole("button", { name: /connect/i }).click();
  await desktop.waitForURL(/\/workspace\/new/, { timeout: 60000 });
  await desktop.getByText(/now explain your bug out loud/i).waitFor({ timeout: 30000 });
  await desktop.waitForTimeout(500);
  await shot(desktop, "workspace-new-session-desktop");

  await mobile.goto(desktop.url(), { timeout: 60000, waitUntil: "domcontentloaded" });
  await mobile.getByText(/now explain your bug out loud/i).waitFor({ timeout: 30000 });
  await mobile.waitForTimeout(500);
  await shot(mobile, "workspace-new-session-mobile");

  await browser.close();
  console.log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
