// Targeted re-capture for the mobile workspace views against an already-
// resolved session (no extra Gemini calls) — run after capture-screenshots.mjs
// printed a workspace URL. Usage: node scripts/capture-mobile-workspace.mjs <url>
import { chromium } from "@playwright/test";

const url = process.argv[2];
if (!url) {
  console.error("usage: node scripts/capture-mobile-workspace.mjs <workspace-url>");
  process.exit(1);
}

const OUT_DIR = new URL("../screenshots/", import.meta.url).pathname;

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

  await page.goto(url, { timeout: 60000, waitUntil: "domcontentloaded" });
  await page.getByText(/resolved!/i).waitFor({ timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT_DIR}workspace-mobile-resolved.png`, fullPage: true });
  console.log("captured workspace-mobile-resolved");

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
