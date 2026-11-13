// Renders docs/report/report.html to report.pdf with Playwright's bundled Chromium (no pandoc/LaTeX needed).
import { chromium } from "/Users/mekkialbilal/Downloads/Agentic assignment 2/gigbid/apps/web/node_modules/@playwright/test/index.mjs";
import path from "path";
const html = path.resolve("docs/report/report.html");
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto("file://" + html, { waitUntil: "load" });
await page.pdf({ path: "docs/report/report.pdf", format: "A4", printBackground: true, margin: { top: "16mm", bottom: "16mm", left: "15mm", right: "15mm" } });
await browser.close();
console.log("wrote docs/report/report.pdf");
