// Drives the real app through Playwright: landing + mobile screenshots, then
// clicks the pagination bug chip for real (one live Gemini-backed session),
// screenshotting the workspace as it progresses and clicking Accept fix when
// it appears. Run with: node scripts/capture-screenshots.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

const BASE_URL = "http://localhost:3000";
const OUT_DIR = new URL("../screenshots/", import.meta.url).pathname;
mkdirSync(OUT_DIR, { recursive: true });

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

async function shot(page, name) {
  await page.screenshot({ path: `${OUT_DIR}${name}.png`, fullPage: true });
  console.log(`captured ${name}`);
}

async function main() {
  const browser = await chromium.launch();

  const desktopCtx = await browser.newContext({ viewport: DESKTOP });
  const mobileCtx = await browser.newContext({ viewport: MOBILE });
  const desktop = await desktopCtx.newPage();
  const mobile = await mobileCtx.newPage();

  console.log("loading landing page (desktop)...");
  await desktop.goto(BASE_URL, { timeout: 60000, waitUntil: "domcontentloaded" });
  await desktop.getByRole("heading", { name: /explain the bug/i }).waitFor({ timeout: 30000 });
  await desktop.waitForTimeout(1500); // let the mini-demo animate in
  await shot(desktop, "landing-desktop");

  console.log("loading landing page (mobile)...");
  await mobile.goto(BASE_URL, { timeout: 60000, waitUntil: "domcontentloaded" });
  await mobile.getByRole("heading", { name: /explain the bug/i }).waitFor({ timeout: 30000 });
  await mobile.waitForTimeout(1500);
  await shot(mobile, "landing-mobile");

  console.log("clicking the pagination bug chip...");
  await desktop.getByRole("button", { name: /task list skips items/i }).click();
  await desktop.waitForURL(/\/workspace\//, { timeout: 60000 });
  console.log("workspace URL:", desktop.url());

  await desktop.waitForTimeout(2000);
  await shot(desktop, "workspace-desktop-investigating");

  console.log("waiting for a hypothesis to appear...");
  await desktop.getByText(/hypothesis/i).first().waitFor({ timeout: 120000 });
  await desktop.waitForTimeout(1000);
  await shot(desktop, "workspace-desktop-hypothesis");

  console.log("waiting for a fix proposal...");
  await desktop.getByRole("button", { name: /accept fix/i }).waitFor({ timeout: 120000 });
  await desktop.waitForTimeout(1000);
  await shot(desktop, "workspace-desktop-fix-proposed");

  // mobile screenshot of the same in-progress session, before we resolve it
  const sessionUrl = desktop.url();
  await mobile.goto(sessionUrl, { timeout: 60000, waitUntil: "domcontentloaded" });
  await mobile.waitForTimeout(2000);
  await shot(mobile, "workspace-mobile-fix-proposed");

  console.log("accepting the fix...");
  await desktop.getByRole("button", { name: /accept fix/i }).click();

  console.log("waiting for resolution...");
  await desktop.getByText(/resolved!/i).waitFor({ timeout: 120000 });
  await desktop.waitForTimeout(1500);
  await shot(desktop, "workspace-desktop-resolved");

  await mobile.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await mobile.waitForTimeout(1500);
  await shot(mobile, "workspace-mobile-resolved");

  await browser.close();
  console.log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
