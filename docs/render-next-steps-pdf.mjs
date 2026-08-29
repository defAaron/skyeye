#!/usr/bin/env node
/**
 * Render docs/skyeye-next-steps.html → docs/skyeye-next-steps.pdf
 * Requires Playwright Chromium: npx playwright install chromium
 */
import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(here, "skyeye-next-steps.html");
const pdfPath = path.join(here, "skyeye-next-steps.pdf");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 816, height: 1056 } });
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle", timeout: 60000 });
await page.evaluate(async () => {
  await document.fonts.ready;
  await new Promise((r) => setTimeout(r, 300));
});
await page.pdf({
  path: pdfPath,
  printBackground: true,
  preferCSSPageSize: true,
  margin: { top: 0, right: 0, bottom: 0, left: 0 },
});
await browser.close();
console.log(pdfPath);
